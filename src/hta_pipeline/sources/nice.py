from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from ..http import build_session
from ..models import RetrievedDocument, SearchRequest, SourceDefinition, published_within_year_limit


def _extract_next_data(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None or script.string is None:
        raise ValueError("NICE search page did not include __NEXT_DATA__.")
    return json.loads(script.string)


def _extract_pdf_url(page_html: str, page_url: str) -> str | None:
    soup = BeautifulSoup(page_html, "lxml")
    link = soup.find("a", href=re.compile(r"/guidance/.+/resources/.+pdf", re.IGNORECASE))
    if link and link.get("href"):
        href = link["href"]
        if href.startswith("http"):
            return href
        return f"https://www.nice.org.uk{href}"
    return None


def search_nice(
    source: SourceDefinition, request: SearchRequest
) -> list[RetrievedDocument]:
    session = build_session()
    response = session.get(
        source.base_url.replace("/guidance", "/search"),
        params={
            "q": request.product_name,
            "ps": 50,
            "gst": "Published",
            "ndt": "Guidance",
            "ngt": "Technology appraisal guidance",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = _extract_next_data(response.text)

    raw_results = (
        payload.get("props", {})
        .get("pageProps", {})
        .get("results", {})
        .get("documents", [])
    )

    documents: list[RetrievedDocument] = []

    for result in raw_results:
        page_url = result.get("url") or result.get("sourceUrl")
        publication_date = result.get("publicationDate")
        revision_date = result.get("lastUpdated")

        if not page_url:
            continue

        if not published_within_year_limit(publication_date, source.years_back_limit):
            continue

        if "guidance" not in page_url:
            continue

        page_response = session.get(page_url, timeout=60)
        page_response.raise_for_status()
        pdf_url = _extract_pdf_url(page_response.text, page_url)

        documents.append(
            RetrievedDocument(
                source_id=source.id,
                source_name=source.name,
                source_type=source.source_type,
                country=request.country,
                title=result.get("title", page_url),
                page_url=page_url,
                document_url=pdf_url or page_url,
                format="pdf" if pdf_url else "html",
                document_type=result.get("niceResultType", "technology_appraisal_guidance"),
                publication_date=publication_date,
                revision_date=revision_date,
                years_back_limit=source.years_back_limit,
                match_term=request.product_name,
                notes="NICE result from official filtered guidance search.",
            )
        )

    return documents
