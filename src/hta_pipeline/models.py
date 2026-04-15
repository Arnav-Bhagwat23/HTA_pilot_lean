from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class SearchRequest:
    product_name: str
    country: str


@dataclass(slots=True)
class SourceDefinition:
    id: str
    name: str
    country: str | None
    region: str
    source_type: str
    base_url: str
    supported_countries: list[str]
    search_strategy: str
    pdf_expected: bool
    mvp_include: bool
    years_back_limit: int
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SourceDefinition":
        return cls(
            id=payload["id"],
            name=payload["name"],
            country=payload.get("country"),
            region=payload["region"],
            source_type=payload["source_type"],
            base_url=payload["base_url"],
            supported_countries=payload.get("supported_countries", []),
            search_strategy=payload["search_strategy"],
            pdf_expected=payload["pdf_expected"],
            mvp_include=payload.get("mvp_include", False),
            years_back_limit=payload["years_back_limit"],
            raw=payload,
        )


@dataclass(slots=True)
class RetrievalCandidate:
    source_id: str
    source_name: str
    source_type: str
    title: str
    url: str
    country: str
    format_hint: str
    years_back_limit: int
    notes: str = ""


@dataclass(slots=True)
class RetrievedDocument:
    source_id: str
    source_name: str
    source_type: str
    country: str
    title: str
    page_url: str
    document_url: str
    format: str
    document_type: str
    publication_date: str | None
    revision_date: str | None
    years_back_limit: int
    match_term: str
    match_confidence: str = "unknown"
    local_path: str | None = None
    notes: str = ""


@dataclass(slots=True)
class RetrievalRun:
    request: SearchRequest
    generated_at: str
    documents: list[RetrievedDocument]
    sources_considered: list[str]
    notes: list[str] = field(default_factory=list)
    scan_log: list[str] = field(default_factory=list)


def published_within_year_limit(
    publication_date: str | None, years_back_limit: int, today: date | None = None
) -> bool:
    if publication_date is None:
        return True

    reference_date = today or date.today()
    cutoff_year = reference_date.year - years_back_limit

    try:
        published_year = int(publication_date[:4])
    except (TypeError, ValueError):
        return True

    return published_year >= cutoff_year
