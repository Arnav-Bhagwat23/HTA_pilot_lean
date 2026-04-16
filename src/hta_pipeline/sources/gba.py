from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import build_session
from ..matching import build_product_aliases, classify_match_confidence, text_contains_any_alias
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


BASE_URL = "https://www.g-ba.de"
SEARCH_URL = "https://www.g-ba.de/sys/suche/"


def _extract_result_links(search_html: str, aliases: list[str]) -> list[tuple[str, str]]:
    soup = BeautifulSoup(search_html, "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = link["href"]
        if "/bewertungsverfahren/nutzenbewertung/" not in href:
            continue
        if href.rstrip("/").split("/")[-1] == "nutzenbewertung":
            continue
        if not text_contains_any_alias(text, aliases):
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append((text, full_url))
    return links


def _extract_pdf_links(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if ".pdf" not in href.lower():
            continue
        text = " ".join(link.get_text(" ", strip=True).split()) or "g_ba_document"
        full_url = urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append((text, full_url))
    return links


def _extract_publication_date(page_html: str, pdf_urls: list[str]) -> str | None:
    matches: list[str] = []
    for url in pdf_urls:
        for match in re.findall(r"(20\d{2})-(\d{2})-(\d{2})", url):
            matches.append(f"{match[0]}-{match[1]}-{match[2]}")
    if matches:
        return max(matches)

    text = BeautifulSoup(page_html, "lxml").get_text(" ", strip=True)
    for match in re.findall(r"(20\d{2})", text):
        matches.append(f"{match}-01-01")
    if matches:
        return max(matches)
    return None


def search_gba(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    aliases = build_product_aliases(request.product_name)
    result_links: list[tuple[str, str]] = []
    seen_result_urls: set[str] = set()
    for query in aliases:
        response = session.get(SEARCH_URL, params={"suchbegriff": query}, timeout=60)
        response.raise_for_status()
        for title, page_url in _extract_result_links(response.text, aliases):
            if page_url in seen_result_urls:
                continue
            seen_result_urls.add(page_url)
            result_links.append((title, page_url))
    documents: list[RetrievedDocument] = []
    seen_document_urls: set[str] = set()

    for title, page_url in result_links:
        page_response = session.get(page_url, timeout=60)
        page_response.raise_for_status()
        page_html = page_response.text
        pdf_links = _extract_pdf_links(page_html)
        publication_date = _extract_publication_date(page_html, [url for _, url in pdf_links])
        if not published_within_year_limit(publication_date, source.years_back_limit):
            continue

        detail_text = BeautifulSoup(page_html, "lxml").get_text(" ", strip=True)
        if not pdf_links:
            confidence = classify_match_confidence(title, detail_text, [], aliases)
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
                    document_type="benefit_assessment",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence if confidence != "no_match" else "title_match",
                    notes="G-BA Nutzenbewertung detail page.",
                )
            )
            continue

        for label, document_url in pdf_links:
            if document_url in seen_document_urls:
                continue
            seen_document_urls.add(document_url)
            confidence = classify_match_confidence(title, detail_text, [document_url], aliases)
            if confidence == "no_match":
                confidence = "detail_page_match"

            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=title,
                    page_url=page_url,
                    document_url=document_url,
                    format="pdf",
                    document_type=label,
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes="G-BA Nutzenbewertung document.",
                )
            )

    return documents
