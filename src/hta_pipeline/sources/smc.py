from __future__ import annotations

import re
from urllib.parse import urljoin
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..http import build_session
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


def _extract_publication_date(card_text: str) -> str | None:
    match = re.search(r"(20\d{2})", card_text)
    if not match:
        return None
    return f"{match.group(1)}-01-01"


def _extract_publication_date_from_url(url: str | None) -> str | None:
    if not url:
        return None
    basename = urlparse(url).path.rsplit("/", 1)[-1]
    match = re.search(r"(20\d{2})", basename)
    if not match:
        return None
    return f"{match.group(1)}-01-01"


def _extract_pdf_url(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "lxml")
    link = soup.find("a", href=re.compile(r"\.pdf($|\?)", re.IGNORECASE))
    if link and link.get("href"):
        return urljoin("https://scottishmedicines.org.uk", link["href"])
    return None


def search_smc(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    response = session.get(
        "https://scottishmedicines.org.uk/search/",
        params={"keywords": request.product_name},
        timeout=60,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")
    cards = soup.select("a.search-results__link")
    seen_urls: set[str] = set()
    documents: list[RetrievedDocument] = []

    for card in cards:
        href = card.get("href")
        title = card.get("title") or card.get_text(" ", strip=True)
        if not href or "/medicines-advice/" not in href:
            continue

        page_url = urljoin("https://scottishmedicines.org.uk", href)
        if page_url in seen_urls:
            continue
        seen_urls.add(page_url)

        page_response = session.get(page_url, timeout=60)
        page_response.raise_for_status()
        pdf_url = _extract_pdf_url(page_response.text)
        surrounding_text = card.parent.get_text(" ", strip=True)
        publication_date = _extract_publication_date(surrounding_text)
        if publication_date is None:
            publication_date = _extract_publication_date_from_url(pdf_url)
        if not published_within_year_limit(publication_date, source.years_back_limit):
            continue

        documents.append(
            RetrievedDocument(
                source_id=source.id,
                source_name=source.name,
                source_type=source.source_type,
                country=request.country,
                title=title,
                page_url=page_url,
                document_url=pdf_url or page_url,
                format="pdf" if pdf_url else "html",
                document_type="medicine_advice",
                publication_date=publication_date,
                revision_date=None,
                years_back_limit=source.years_back_limit,
                match_term=request.product_name,
                notes="SMC result from official keyword search.",
            )
        )

    return documents
