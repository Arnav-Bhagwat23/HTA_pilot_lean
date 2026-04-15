from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..config import project_root
from ..matching import build_product_aliases, classify_match_confidence, text_contains_any_alias
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


BASE_URL = "https://www.cda-amc.ca"


@dataclass(slots=True)
class CadthListingEntry:
    title: str
    brand_name: str
    generic_name: str
    therapeutic_area: str
    recommendation_type: str
    status: str
    submission_date: str | None
    recommendation_date: str | None
    project_number: str
    detail_url: str | None
    file_links: list[tuple[str, str]]

    @property
    def listing_text(self) -> str:
        return " ".join(
            [
                self.title,
                self.brand_name,
                self.generic_name,
                self.therapeutic_area,
                self.recommendation_type,
                self.status,
                self.project_number,
            ]
        )


def _parse_date(text: str) -> str | None:
    match = re.search(r"([A-Z][a-z]{2} \d{1,2}, \d{4})", text)
    if not match:
        return None
    month_map = {
        "Jan": "01",
        "Feb": "02",
        "Mar": "03",
        "Apr": "04",
        "May": "05",
        "Jun": "06",
        "Jul": "07",
        "Aug": "08",
        "Sep": "09",
        "Oct": "10",
        "Nov": "11",
        "Dec": "12",
    }
    month, day, year = match.group(1).replace(",", "").split()
    return f"{year}-{month_map[month]}-{int(day):02d}"


def parse_find_reports_listing(html: str) -> list[CadthListingEntry]:
    soup = BeautifulSoup(html, "lxml")
    entries: list[CadthListingEntry] = []

    candidate_rows = soup.find_all("tr")
    for row in candidate_rows:
        cells = row.find_all("td")
        if len(cells) < 10:
            continue

        title_link = cells[0].find("a")
        title = cells[0].get_text(" ", strip=True)
        detail_url = (
            urljoin(BASE_URL, title_link.get("href"))
            if title_link and title_link.get("href")
            else None
        )
        brand_name = cells[1].get_text(" ", strip=True)
        generic_name = cells[2].get_text(" ", strip=True)
        file_links = []
        for link in cells[3].find_all("a", href=True):
            file_links.append((link.get_text(" ", strip=True), urljoin(BASE_URL, link["href"])))

        entry = CadthListingEntry(
            title=title,
            brand_name=brand_name,
            generic_name=generic_name,
            therapeutic_area=cells[4].get_text(" ", strip=True),
            recommendation_type=cells[5].get_text(" ", strip=True),
            status=cells[6].get_text(" ", strip=True),
            submission_date=_parse_date(cells[7].get_text(" ", strip=True)),
            recommendation_date=_parse_date(cells[8].get_text(" ", strip=True)),
            project_number=cells[9].get_text(" ", strip=True),
            detail_url=detail_url,
            file_links=file_links,
        )
        entries.append(entry)

    return entries


def parse_detail_pdf_links(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "lxml")
    links: list[tuple[str, str]] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        links.append((link.get_text(" ", strip=True), urljoin(BASE_URL, href)))
    return links


def fixture_dir() -> Path:
    return project_root() / "tests" / "fixtures" / "cadth"


def search_cadth(
    source: SourceDefinition, request: SearchRequest
) -> tuple[list[RetrievedDocument], list[str]]:
    aliases = build_product_aliases(request.product_name)
    listing_path = fixture_dir() / "find_reports_reimbursement_review.html"
    if not listing_path.exists():
        raise FileNotFoundError("CADTH fixture listing page is missing.")

    listing_html = listing_path.read_text(encoding="utf-8")
    entries = parse_find_reports_listing(listing_html)
    detail_cache = {
        "pembrolizumab-14": (fixture_dir() / "pembrolizumab-14.html"),
        "nivolumab-4": (fixture_dir() / "nivolumab-4.html"),
        "dostarlimab-jemperli": (fixture_dir() / "dostarlimab-jemperli.html"),
    }

    documents: list[RetrievedDocument] = []
    scan_log: list[str] = []

    for entry in entries:
        if not text_contains_any_alias(entry.listing_text, aliases):
            continue

        if not published_within_year_limit(
            entry.recommendation_date or entry.submission_date, source.years_back_limit
        ):
            scan_log.append(
                f"Skipped {entry.project_number} because it is older than {source.years_back_limit} years."
            )
            continue

        detail_text = ""
        detail_pdf_links: list[tuple[str, str]] = list(entry.file_links)

        if entry.detail_url:
            slug = entry.detail_url.rstrip("/").split("/")[-1]
            detail_path = detail_cache.get(slug) or (fixture_dir() / f"{slug}.html")
            if detail_path.exists():
                detail_html = detail_path.read_text(encoding="utf-8")
                detail_text = BeautifulSoup(detail_html, "lxml").get_text(" ", strip=True)
                detail_pdf_links.extend(parse_detail_pdf_links(detail_html))

        deduped_urls: dict[str, str] = {}
        for label, url in detail_pdf_links:
            deduped_urls[url] = label

        confidence = classify_match_confidence(
            entry.listing_text, detail_text, list(deduped_urls.keys()), aliases
        )
        if confidence == "no_match":
            continue

        for url, label in deduped_urls.items():
            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=entry.title,
                    page_url=entry.detail_url or source.base_url,
                    document_url=url,
                    format="pdf" if ".pdf" in url.lower() else "html",
                    document_type=label or "cadth_report",
                    publication_date=entry.recommendation_date or entry.submission_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes=f"CADTH listing/detail fixture match for {entry.project_number}.",
                )
            )

        scan_log.append(
            f"Matched {entry.project_number} via {confidence} with {len(deduped_urls)} files."
        )

    return documents, scan_log
