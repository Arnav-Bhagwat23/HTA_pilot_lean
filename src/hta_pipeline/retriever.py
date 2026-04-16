from __future__ import annotations

from datetime import datetime, timezone

from .http import build_session, download_file
from .models import RetrievalCandidate, RetrievalRun, SearchRequest
from .selector import select_sources_for_country
from .storage import build_download_path
from .sources.aemps import search_aemps
from .sources.aifa import search_aifa
from .sources.gba import search_gba
from .sources.has import search_has
from .sources.nice import search_nice
from .sources.pbac import search_pbac
from .sources.smc import search_smc


SUPPORTED_SOURCE_HANDLERS = {
    "aemps_spain": search_aemps,
    "aifa_italy": search_aifa,
    "gba_germany": search_gba,
    "has_france": search_has,
    "nice_uk": search_nice,
    "pbac_australia": search_pbac,
    "smc_uk": search_smc,
}


def plan_retrieval(request: SearchRequest) -> list[RetrievalCandidate]:
    candidates: list[RetrievalCandidate] = []

    for source in select_sources_for_country(request.country):
        format_hint = "pdf_preferred" if source.pdf_expected else "non_pdf_allowed"
        candidates.append(
            RetrievalCandidate(
                source_id=source.id,
                source_name=source.name,
                source_type=source.source_type,
                title=f"{request.product_name} - search plan for {source.name}",
                url=source.base_url,
                country=request.country,
                format_hint=format_hint,
                years_back_limit=source.years_back_limit,
                notes=(
                    "Initial retrieval plan only. Source-specific querying and download "
                    "logic will be implemented next."
                ),
            )
        )

    return candidates


def run_retrieval(request: SearchRequest) -> RetrievalRun:
    documents = []
    sources_considered: list[str] = []
    notes: list[str] = []
    scan_log: list[str] = []
    session = build_session()

    for source in select_sources_for_country(request.country):
        sources_considered.append(source.id)
        handler = SUPPORTED_SOURCE_HANDLERS.get(source.id)
        if handler is None:
            notes.append(
                f"No live retriever is implemented yet for source '{source.id}'."
            )
            continue

        try:
            result = handler(source, request)
            if isinstance(result, tuple):
                source_documents, source_scan_log = result
                documents.extend(source_documents)
                scan_log.extend(source_scan_log)
            else:
                documents.extend(result)
        except Exception as error:  # pragma: no cover - operational path
            notes.append(f"Source '{source.id}' failed during retrieval: {error}")

    for document in documents:
        if document.format != "pdf":
            continue

        try:
            destination = build_download_path(
                request.country, document.source_id, document.document_url
            )
            download_file(session, document.document_url, destination)
            document.local_path = str(destination)
        except Exception as error:  # pragma: no cover - operational path
            notes.append(
                f"Download failed for '{document.document_url}' from '{document.source_id}': {error}"
            )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return RetrievalRun(
        request=request,
        generated_at=generated_at,
        documents=documents,
        sources_considered=sources_considered,
        notes=notes,
        scan_log=scan_log,
    )
