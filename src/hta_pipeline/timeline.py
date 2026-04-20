from __future__ import annotations

from dataclasses import dataclass
import re

from .models import RetrievedDocument


@dataclass(slots=True)
class TimelineDocument:
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
    event_date: str | None
    document_stage: str
    document_family: str
    timeline_priority: int
    years_back_limit: int
    match_term: str
    match_confidence: str
    document_lineage_id: str | None = None
    version_rank: int | None = None
    is_latest_version: bool = False
    lineage_confidence: str = "weak"
    lineage_basis: str = "unassigned"
    local_path: str | None = None
    status: str = "unknown"
    notes: str = ""


def _derive_event_date(document: RetrievedDocument) -> str | None:
    return document.publication_date or document.revision_date


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _normalize_free_text(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"\.(pdf|zip|html)$", "", lowered)
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _extract_nice_key(document: TimelineDocument) -> tuple[str, str]:
    match = re.search(r"/guidance/([a-z]{2}\d+)", document.page_url.lower())
    if match:
        return f"nice_uk::{match.group(1)}", "strong"
    slug = document.page_url.rstrip("/").split("/")[-1]
    return f"nice_uk::{_normalize_free_text(slug)}", "moderate"


def _extract_smc_key(document: TimelineDocument) -> tuple[str, str]:
    slug = document.page_url.rstrip("/").split("/")[-1]
    return f"smc_uk::{_normalize_free_text(slug)}", "strong"


def _extract_has_key(document: TimelineDocument) -> tuple[str, str]:
    slug = document.page_url.rstrip("/").split("/")[-1]
    subtype = document.document_stage
    return f"has_france::{_normalize_free_text(slug)}::{subtype}", "moderate"


def _extract_gba_key(document: TimelineDocument) -> tuple[str, str]:
    match = re.search(r"/nutzenbewertung/(\d+)/", document.page_url.lower())
    page_key = match.group(1) if match else _normalize_free_text(document.page_url.rstrip("/").split("/")[-1])
    combined = " ".join([document.title, document.document_type]).lower()
    if "iqwig" in combined:
        series = "iqwig"
    elif "wortprotokoll" in combined:
        series = "wortprotokoll"
    elif "modul" in combined:
        modul_match = re.search(r"modul\s*([0-9]+)", combined)
        series = f"modul_{modul_match.group(1)}" if modul_match else "modul"
    elif "anhang" in combined:
        series = "anhang"
    else:
        series = _normalize_free_text(document.document_type)
    return f"gba_germany::{page_key}::{series}", "strong"


def _extract_aifa_key(document: TimelineDocument) -> tuple[str, str]:
    title_key = _normalize_free_text(document.title)
    if document.document_family == "registry" or document.format == "zip":
        url_name = document.document_url.rstrip("/").split("/")[-1]
        return f"aifa_italy::{_normalize_free_text(url_name)}::registry", "moderate"
    return f"aifa_italy::{title_key}::{document.document_family}", "weak"


def _extract_aemps_key(document: TimelineDocument) -> tuple[str, str]:
    match = re.search(r"ipt[-_]?([0-9]+)", document.document_url.lower())
    if not match:
        match = re.search(r"ipt[-_]?([0-9]+)", document.title.lower())
    if match:
        return f"aemps_spain::ipt_{match.group(1)}", "strong"
    return f"aemps_spain::{_normalize_free_text(document.title)}", "moderate"


def _extract_pbac_key(document: TimelineDocument) -> tuple[str, str]:
    title_key = _normalize_free_text(document.title)
    return f"pbac_australia::{title_key}", "moderate"


def derive_document_lineage(document: TimelineDocument) -> tuple[str, str, str]:
    lineage_extractors = {
        "nice_uk": (_extract_nice_key, "same_source_same_guidance"),
        "smc_uk": (_extract_smc_key, "same_source_same_advice_slug"),
        "has_france": (_extract_has_key, "same_source_same_history_subtype"),
        "gba_germany": (_extract_gba_key, "same_source_same_nutzenbewertung_series"),
        "aifa_italy": (_extract_aifa_key, "same_source_same_aifa_series"),
        "aemps_spain": (_extract_aemps_key, "same_source_same_ipt_series"),
        "pbac_australia": (_extract_pbac_key, "same_source_same_psd_title"),
    }
    extractor, basis = lineage_extractors.get(
        document.source_id,
        (lambda doc: (f"{doc.source_id}::{_normalize_free_text(doc.title)}", "weak"), "same_source_same_title_normalized"),
    )
    lineage_id, confidence = extractor(document)
    return lineage_id, confidence, basis


def _normalize_nice(document: RetrievedDocument) -> tuple[str, str, int]:
    return "final_decision", "hta", 1


def _normalize_smc(document: RetrievedDocument) -> tuple[str, str, int]:
    return "final_decision", "hta", 1


def _normalize_has(document: RetrievedDocument) -> tuple[str, str, int]:
    combined = " ".join([document.title, document.document_type]).lower()
    if "transcription" in combined:
        return "committee_review", "hta", 4
    if "summary" in combined:
        return "supporting_material", "hta", 3
    if "avis" in combined:
        return "recommendation", "hta", 1
    return "supporting_material", "hta", 5


def _normalize_gba(document: RetrievedDocument) -> tuple[str, str, int]:
    combined = " ".join([document.title, document.document_type]).lower()
    if "iqwig" in combined:
        return "assessment", "hta", 2
    if "wortprotokoll" in combined:
        return "committee_review", "hta", 4
    if _contains_any(combined, ["modul", "anhang", "vergleichstherapie", "benennung kombinationen"]):
        return "supporting_material", "hta", 4
    return "assessment", "hta", 3


def _normalize_aifa(document: RetrievedDocument) -> tuple[str, str, int]:
    combined = " ".join([document.title, document.document_type]).lower()
    if document.format == "zip" or "registry" in combined:
        return "post_decision_update", "registry", 4
    if document.format == "html":
        return "supporting_material", "supporting", 5
    return "final_decision", "hta", 1


def _normalize_aemps(document: RetrievedDocument) -> tuple[str, str, int]:
    if document.format == "html":
        return "supporting_material", "hta", 4
    return "assessment", "hta", 1


def _normalize_pbac(document: RetrievedDocument) -> tuple[str, str, int]:
    if document.format == "html":
        return "supporting_material", "hta", 4
    return "recommendation", "hta", 1


def _normalize_default(document: RetrievedDocument) -> tuple[str, str, int]:
    return "unknown", "supporting", 5


def normalize_document(document: RetrievedDocument) -> TimelineDocument:
    normalizers = {
        "nice_uk": _normalize_nice,
        "smc_uk": _normalize_smc,
        "has_france": _normalize_has,
        "gba_germany": _normalize_gba,
        "aifa_italy": _normalize_aifa,
        "aemps_spain": _normalize_aemps,
        "pbac_australia": _normalize_pbac,
    }
    document_stage, document_family, timeline_priority = normalizers.get(
        document.source_id, _normalize_default
    )(document)

    return TimelineDocument(
        source_id=document.source_id,
        source_name=document.source_name,
        source_type=document.source_type,
        country=document.country,
        title=document.title,
        page_url=document.page_url,
        document_url=document.document_url,
        format=document.format,
        document_type=document.document_type,
        publication_date=document.publication_date,
        revision_date=document.revision_date,
        event_date=_derive_event_date(document),
        document_stage=document_stage,
        document_family=document_family,
        timeline_priority=timeline_priority,
        years_back_limit=document.years_back_limit,
        match_term=document.match_term,
        match_confidence=document.match_confidence,
        document_lineage_id=None,
        version_rank=None,
        is_latest_version=False,
        lineage_confidence="weak",
        lineage_basis="unassigned",
        local_path=document.local_path,
        status="unknown",
        notes=document.notes,
    )


def normalize_documents(documents: list[RetrievedDocument]) -> list[TimelineDocument]:
    return [normalize_document(document) for document in documents]


def assign_document_lineages(documents: list[TimelineDocument]) -> list[TimelineDocument]:
    lineage_groups: dict[str, list[TimelineDocument]] = {}

    for document in documents:
        lineage_id, confidence, basis = derive_document_lineage(document)
        document.document_lineage_id = lineage_id
        document.lineage_confidence = confidence
        document.lineage_basis = basis
        lineage_groups.setdefault(lineage_id, []).append(document)

    for group in lineage_groups.values():
        ordered = sorted(
            group,
            key=lambda document: (
                document.event_date or "0000-00-00",
                document.revision_date or "",
                _normalize_free_text(document.title),
                document.document_url,
            ),
        )
        for index, document in enumerate(ordered, start=1):
            document.version_rank = index
            document.is_latest_version = index == len(ordered)

    return documents


def sort_timeline_documents(documents: list[TimelineDocument]) -> list[TimelineDocument]:
    return sorted(
        documents,
        key=lambda document: (
            document.country,
            document.match_term.lower(),
            document.event_date or "9999-12-31",
            document.timeline_priority,
            document.source_name.lower(),
            document.document_type.lower(),
        ),
    )
