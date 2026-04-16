from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import build_session
from ..matching import build_product_aliases, classify_match_confidence, text_contains_any_alias
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


DATA_URL = "https://www.aemps.gob.es/assets/data/IPT/ddbb.json"
BASE_URL = "https://www.aemps.gob.es"


def _extract_detail_documents(page_html: str, aliases: list[str]) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])
        if not href.lower().endswith(".pdf"):
            continue
        if "aemps.gob.es" not in href.lower():
            continue
        link_text = " ".join(link.get_text(" ", strip=True).split())
        if not text_contains_any_alias(" ".join([link_text, href]), aliases):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append((link_text, href))

    return links


def search_aemps(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    aliases = build_product_aliases(request.product_name)
    response = session.get(DATA_URL, timeout=60)
    response.raise_for_status()
    items = response.json()

    documents: list[RetrievedDocument] = []
    seen_document_urls: set[str] = set()
    seen_page_urls: set[str] = set()

    for item in items:
        title = str(item.get("title", "")).strip()
        page_url = str(item.get("link", "")).strip()
        publication_date = str(item.get("date", "")).replace("/", "-") or None
        version = str(item.get("version", "")).strip()
        listing_text = " ".join(
            part
            for part in [title, page_url, str(item.get("group", "")), str(item.get("subgroup", ""))]
            if part
        )

        if not page_url or not text_contains_any_alias(listing_text, aliases):
            continue
        if not published_within_year_limit(publication_date, source.years_back_limit):
            continue

        if page_url.lower().endswith(".pdf"):
            if page_url in seen_document_urls:
                continue
            seen_document_urls.add(page_url)
            confidence = classify_match_confidence(listing_text, title, [page_url], aliases)
            if confidence == "no_match":
                confidence = "title_match"

            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=title,
                    page_url=page_url,
                    document_url=page_url,
                    format="pdf",
                    document_type="therapeutic_positioning_report",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes=f"AEMPS IPT dataset record. Version {version or 'unknown'}.",
                )
            )
            continue

        if page_url in seen_page_urls:
            continue
        seen_page_urls.add(page_url)

        detail_response = session.get(page_url, timeout=60)
        detail_response.raise_for_status()
        detail_html = detail_response.text
        detail_text = BeautifulSoup(detail_html, "lxml").get_text(" ", strip=True)
        detail_links = _extract_detail_documents(detail_html, aliases)

        if not detail_links:
            confidence = classify_match_confidence(listing_text, detail_text, [], aliases)
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
                    document_type="therapeutic_positioning_page",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence if confidence != "no_match" else "title_match",
                    notes=f"AEMPS IPT dataset page record. Version {version or 'unknown'}.",
                )
            )
            continue

        for label, document_url in detail_links:
            if document_url in seen_document_urls:
                continue
            seen_document_urls.add(document_url)
            confidence = classify_match_confidence(listing_text, detail_text, [document_url], aliases)
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
                    document_type=label or "therapeutic_positioning_report",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes=f"AEMPS IPT dataset page attachment. Version {version or 'unknown'}.",
                )
            )

    return documents
