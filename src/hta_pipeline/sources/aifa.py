from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ..http import build_session
from ..matching import build_product_aliases, classify_match_confidence, text_contains_any_alias
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


BASE_URL = "https://www.aifa.gov.it"
SEARCH_URL = "https://www.aifa.gov.it/ricerca-aifa"
ALLOWED_EXTENSIONS = {".pdf": "pdf", ".zip": "zip"}
EXCLUDED_EXTENSIONS = {".csv", ".ods", ".xlsx", ".xls"}


def _extract_publication_date(text: str) -> str | None:
    cleaned = " ".join(text.split())
    for pattern in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %z %Y"):
        try:
            parsed = datetime.strptime(cleaned, pattern)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    match = re.search(r"(\d{2})[./-](\d{2})[./-](20\d{2})", cleaned)
    if match:
        return f"{match.group(3)}-{match.group(2)}-{match.group(1)}"

    return None


def _infer_format(url: str) -> str:
    lowered = url.lower()
    for extension, file_format in ALLOWED_EXTENSIONS.items():
        if lowered.endswith(extension):
            return file_format
    return "html"


def _is_allowed_document_url(url: str) -> bool:
    lowered = url.lower()
    parsed = urlparse(url)
    if parsed.netloc and "aifa.gov.it" not in parsed.netloc:
        return False
    if any(lowered.endswith(extension) for extension in EXCLUDED_EXTENSIONS):
        return False
    if lowered.endswith(".pdf") or lowered.endswith(".zip"):
        return True
    return parsed.netloc.endswith("aifa.gov.it") and parsed.path.startswith("/-/")


def _extract_embedded_document_urls(text: str) -> list[str]:
    matches = re.findall(
        r"/documents/[^\s;]+?\.(?:pdf|zip)",
        text,
        flags=re.IGNORECASE,
    )
    return [urljoin(BASE_URL, match) for match in matches]


def _extract_result_cards(search_html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(search_html, "lxml")
    cards: list[dict[str, object]] = []

    for card in soup.select("div.card.smooth"):
        link = card.select_one("a.asset-link[href]")
        if not link:
            continue

        href = urljoin(BASE_URL, link["href"])
        raw_card_text = " ".join(card.get_text(" ", strip=True).split())
        embedded_urls = [
            url
            for url in _extract_embedded_document_urls(raw_card_text)
            if _is_allowed_document_url(url)
        ]
        if not _is_allowed_document_url(href) and not embedded_urls:
            continue

        summary = ""
        summary_tag = link.find_parent("h3")
        if summary_tag and summary_tag.parent:
            paragraph = summary_tag.parent.find("p")
            if paragraph:
                summary = " ".join(paragraph.get_text(" ", strip=True).split())

        meta_text = ""
        meta_tag = card.select_one("span.u-color-blu")
        if meta_tag:
            meta_text = " ".join(meta_tag.get_text(" ", strip=True).split())

        cards.append(
            {
                "title": " ".join(link.get_text(" ", strip=True).split()),
                "page_url": href,
                "summary": summary,
                "meta_text": meta_text,
                "embedded_urls": embedded_urls,
            }
        )

    return cards


def _extract_detail_documents(page_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(page_html, "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = urljoin(BASE_URL, link["href"])
        lowered = href.lower()
        if not (lowered.endswith(".pdf") or lowered.endswith(".zip")):
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append((" ".join(link.get_text(" ", strip=True).split()), href))

    return links


def search_aifa(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    aliases = build_product_aliases(
        request.product_name,
        generic_name=request.generic_name,
        extra_aliases=request.aliases,
    )

    documents: list[RetrievedDocument] = []
    seen_document_urls: set[str] = set()
    seen_page_urls: set[str] = set()

    for alias in aliases:
        response = session.get(
            SEARCH_URL,
            params={"searchKeywords": alias},
            timeout=60,
        )
        response.raise_for_status()

        for card in _extract_result_cards(response.text):
            title = str(card["title"])
            page_url = str(card["page_url"])
            summary = str(card["summary"] or "")
            meta_text = str(card["meta_text"] or "")
            embedded_urls = [str(url) for url in card.get("embedded_urls", [])]
            listing_text = " ".join(part for part in [title, summary, page_url] if part)

            if not text_contains_any_alias(listing_text, aliases):
                continue

            publication_date = _extract_publication_date(meta_text) or _extract_publication_date(page_url)
            if not published_within_year_limit(publication_date, source.years_back_limit):
                continue

            file_format = _infer_format(page_url)
            if file_format != "html":
                if page_url in seen_document_urls:
                    continue
                seen_document_urls.add(page_url)
                confidence = classify_match_confidence(listing_text, summary, [page_url], aliases)
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
                        format=file_format,
                        document_type="pricing_or_reimbursement_document",
                        publication_date=publication_date,
                        revision_date=None,
                        years_back_limit=source.years_back_limit,
                        match_term=request.product_name,
                        match_confidence=confidence,
                        notes="AIFA search result document.",
                    )
                )
                continue

            embedded_urls = [
                url for url in embedded_urls if text_contains_any_alias(url, aliases)
            ]
            if not _is_allowed_document_url(page_url) and not embedded_urls:
                continue

            if embedded_urls:
                confidence = classify_match_confidence(listing_text, summary, embedded_urls, aliases)
                if confidence == "no_match":
                    confidence = "detail_page_match"

                for document_url in embedded_urls:
                    if document_url in seen_document_urls:
                        continue
                    seen_document_urls.add(document_url)
                    documents.append(
                        RetrievedDocument(
                            source_id=source.id,
                            source_name=source.name,
                            source_type=source.source_type,
                            country=request.country,
                            title=title,
                            page_url=page_url,
                            document_url=document_url,
                            format=_infer_format(document_url),
                            document_type="registry_document",
                            publication_date=publication_date,
                            revision_date=None,
                            years_back_limit=source.years_back_limit,
                            match_term=request.product_name,
                            match_confidence=confidence,
                            notes="AIFA result card embedded document reference.",
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
            confidence = classify_match_confidence(listing_text, detail_text, [], aliases)
            detail_links = _extract_detail_documents(detail_html)

            if not detail_links:
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
                        document_type="pricing_or_reimbursement_page",
                        publication_date=publication_date,
                        revision_date=None,
                        years_back_limit=source.years_back_limit,
                        match_term=request.product_name,
                        match_confidence=confidence if confidence != "no_match" else "title_match",
                        notes="AIFA result page without direct attachment.",
                    )
                )
                continue

            for label, document_url in detail_links:
                if document_url in seen_document_urls:
                    continue
                seen_document_urls.add(document_url)
                detail_confidence = classify_match_confidence(
                    listing_text,
                    detail_text,
                    [document_url],
                    aliases,
                )
                if detail_confidence == "no_match":
                    detail_confidence = confidence if confidence != "no_match" else "detail_page_match"

                documents.append(
                    RetrievedDocument(
                        source_id=source.id,
                        source_name=source.name,
                        source_type=source.source_type,
                        country=request.country,
                        title=title,
                        page_url=page_url,
                        document_url=document_url,
                        format=_infer_format(document_url),
                        document_type=label or "pricing_or_reimbursement_document",
                        publication_date=publication_date,
                        revision_date=None,
                        years_back_limit=source.years_back_limit,
                        match_term=request.product_name,
                        match_confidence=detail_confidence,
                        notes="AIFA result page attachment.",
                    )
                )

    return documents
