from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import build_session
from ..matching import build_product_aliases, classify_match_confidence, text_contains_any_alias
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


BASE_URL = "https://www.pbs.gov.au"
BY_PRODUCT_URL = (
    "https://www.pbs.gov.au/info/industry/listing/elements/pbac-meetings/psd/"
    "public-summary-documents-by-product"
)
MONTH_MAP = {
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
}


def _extract_publication_date(text: str) -> str | None:
    match = re.search(
        r"\b("
        + "|".join(MONTH_MAP)
        + r")\s+(20\d{2})\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    month = MONTH_MAP[match.group(1).lower()]
    year = match.group(2)
    return f"{year}-{month}-01"


def _extract_publication_date_from_url(url: str) -> str | None:
    match = re.search(r"/(20\d{2})-(0[1-9]|1[0-2])/", url)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-01"


def _extract_pdf_links(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "lxml")
    links: list[tuple[str, str]] = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        links.append((link.get_text(" ", strip=True), urljoin(BASE_URL, href)))
    return links


def search_pbac(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    aliases = build_product_aliases(
        request.product_name,
        generic_name=request.generic_name,
        extra_aliases=request.aliases,
    )

    response = session.get(BY_PRODUCT_URL, timeout=60)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    documents: list[RetrievedDocument] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        title = " ".join(link.get_text(" ", strip=True).split())
        href = link["href"]
        if not title or "/psd/" not in href.lower():
            continue
        if href.endswith("/public-summary-documents-by-product"):
            continue
        if not text_contains_any_alias(title, aliases):
            continue

        publication_date = _extract_publication_date(title) or _extract_publication_date_from_url(href)
        if not published_within_year_limit(publication_date, source.years_back_limit):
            continue

        page_url = urljoin(BASE_URL, href)
        if page_url in seen_urls:
            continue
        seen_urls.add(page_url)

        page_response = session.get(page_url, timeout=60)
        page_response.raise_for_status()
        pdf_links = _extract_pdf_links(page_response.text)
        detail_text = BeautifulSoup(page_response.text, "lxml").get_text(" ", strip=True)
        confidence = classify_match_confidence(title, detail_text, [url for _, url in pdf_links], aliases)
        if confidence == "no_match":
            confidence = "title_match"

        if not pdf_links:
            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=title,
                    page_url=page_url,
                    document_url=page_url,
                    format="html",
                    document_type="public_summary_document",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes="PBAC PSD result from official by-product index.",
                )
            )
            continue

        for label, url in pdf_links:
            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=title,
                    page_url=page_url,
                    document_url=url,
                    format="pdf",
                    document_type=label or "public_summary_document",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes="PBAC PSD result from official by-product index.",
                )
            )

    return documents
