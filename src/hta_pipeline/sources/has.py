from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from ..http import build_session
from ..matching import build_product_aliases, classify_match_confidence, text_contains_any_alias
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


BASE_URL = "https://www.has-sante.fr/"
SEARCH_URL = "https://www.has-sante.fr/jcms/fc_2875171/fr/resultat-de-recherche"
FRENCH_MONTHS = {
    "janvier": "01",
    "fevrier": "02",
    "mars": "03",
    "avril": "04",
    "mai": "05",
    "juin": "06",
    "juillet": "07",
    "aout": "08",
    "septembre": "09",
    "octobre": "10",
    "novembre": "11",
    "decembre": "12",
}


def _normalize_french_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _extract_publication_date(text: str) -> str | None:
    normalized_text = _normalize_french_text(text)
    match = re.search(
        r"(\d{1,2})\s+("
        + "|".join(FRENCH_MONTHS)
        + r")\s+(20\d{2})",
        normalized_text,
        re.IGNORECASE,
    )
    if not match:
        return None
    day = int(match.group(1))
    month = FRENCH_MONTHS[match.group(2).lower()]
    year = match.group(3)
    return f"{year}-{month}-{day:02d}"


def _extract_product_page_url(search_html: str, aliases: list[str]) -> str | None:
    soup = BeautifulSoup(search_html, "lxml")
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = link["href"]
        normalized_text = _normalize_french_text(text)
        if "jcms/pprd_" not in href and "jcms/p_" not in href:
            continue
        if normalized_text.startswith("decision n"):
            continue
        if not text_contains_any_alias(text, aliases):
            continue
        return urljoin(BASE_URL, href)
    return None


def _extract_history_links(product_html: str, aliases: list[str]) -> list[tuple[str, str]]:
    soup = BeautifulSoup(product_html, "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = link["href"]
        if "jcms/p_" not in href:
            continue
        normalized_text = _normalize_french_text(text)
        if "historique des avis" in normalized_text or "avis economiques" in normalized_text:
            continue
        if not text_contains_any_alias(text, aliases):
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append((text, full_url))
    return links


def _extract_document_links(detail_html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(detail_html, "lxml")
    links: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        text = " ".join(link.get_text(" ", strip=True).split())
        href = link["href"]
        normalized_text = _normalize_french_text(text)
        if not text:
            continue
        if "avis economiques" in normalized_text:
            continue
        if not any(keyword in normalized_text for keyword in ["avis", "transcription", "summary"]):
            continue
        full_url = urljoin(BASE_URL, href)
        if full_url in seen:
            continue
        seen.add(full_url)
        links.append((text, full_url))
    return links


def _resolve_document_url(session, url: str) -> tuple[str, str]:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if "pdf" in content_type and response.url.lower().endswith(".pdf"):
        return response.url, "pdf"

    html = response.text
    meta_match = re.search(r"URL='([^']+)'", html, re.IGNORECASE)
    if meta_match:
        resolved = urljoin(response.url, meta_match.group(1))
        return resolved, "pdf" if resolved.lower().endswith(".pdf") else "html"

    if response.url.lower().endswith(".pdf"):
        return response.url, "pdf"
    return response.url, "html"


def search_has(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    aliases = build_product_aliases(request.product_name)
    params = {
        "liaison_word-empty": "and",
        "expression": "exact",
        "text": request.product_name,
        "searchOn": "vTitleAndAbstract",
        "catMode": "or",
        "dateMiseEnLigne": "indexDateFrom",
        "dateDebutDisplay": "",
        "dateDebut": "",
        "dateFinDisplay": "",
        "dateFin": "",
        "search_antidot": "OK",
    }
    search_response = session.get(SEARCH_URL, params=params, timeout=60)
    search_response.raise_for_status()

    product_page_url = _extract_product_page_url(search_response.text, aliases)
    if not product_page_url:
        return []

    product_response = session.get(product_page_url, timeout=60)
    product_response.raise_for_status()
    history_links = _extract_history_links(product_response.text, aliases)

    documents: list[RetrievedDocument] = []
    seen_document_urls: set[str] = set()

    for history_title, detail_url in history_links:
        try:
            detail_response = session.get(detail_url, timeout=60)
            detail_response.raise_for_status()
        except Exception:
            continue
        detail_html = detail_response.text
        detail_text = BeautifulSoup(detail_html, "lxml").get_text(" ", strip=True)
        publication_date = _extract_publication_date(detail_text)
        if not published_within_year_limit(publication_date, source.years_back_limit):
            continue

        document_links = _extract_document_links(detail_html)
        if not document_links:
            confidence = classify_match_confidence(history_title, detail_text, [], aliases)
            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=history_title,
                    page_url=detail_url,
                    document_url=detail_url,
                    format="html",
                    document_type="hta_opinion",
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence if confidence != "no_match" else "title_match",
                    notes="HAS detail page from product evaluation history.",
                )
            )
            continue

        for label, raw_document_url in document_links:
            try:
                resolved_url, doc_format = _resolve_document_url(session, raw_document_url)
            except Exception:
                continue
            if resolved_url in seen_document_urls:
                continue
            seen_document_urls.add(resolved_url)

            confidence = classify_match_confidence(history_title, detail_text, [resolved_url], aliases)
            if confidence == "no_match":
                confidence = "detail_page_match"

            documents.append(
                RetrievedDocument(
                    source_id=source.id,
                    source_name=source.name,
                    source_type=source.source_type,
                    country=request.country,
                    title=history_title,
                    page_url=detail_url,
                    document_url=resolved_url,
                    format=doc_format,
                    document_type=label,
                    publication_date=publication_date,
                    revision_date=None,
                    years_back_limit=source.years_back_limit,
                    match_term=request.product_name,
                    match_confidence=confidence,
                    notes="HAS document from product evaluation history.",
                )
            )

    return documents
