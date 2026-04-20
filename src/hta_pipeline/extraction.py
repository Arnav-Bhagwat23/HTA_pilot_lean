from __future__ import annotations

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .env import get_openai_api_key
from .models import RetrievalRun
from .schema import (
    HTA_RESULT_FIELDS,
    SCHEMA_VERSION,
    build_empty_extraction_sections,
    empty_extracted_field,
)
from .storage import results_dir, slugify
from .timeline import (
    TimelineDocument,
    assign_document_lineages,
    normalize_documents,
    sort_timeline_documents,
)


DEFAULT_EXTRACTION_MODEL = "gpt-5.1"


class ExtractionClient(Protocol):
    def extract_hta_fields(
        self,
        *,
        document: TimelineDocument,
        document_path: Path,
        missing_fields: list[str],
        current_record: dict[str, Any],
        fill_method: str,
        model: str,
    ) -> dict[str, Any]:
        """Return a partial hta_results object keyed by missing field name."""


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def field_has_value(field: dict[str, Any]) -> bool:
    value = field.get("value")
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def missing_hta_fields(record: dict[str, Any]) -> list[str]:
    return [
        field_name
        for field_name in HTA_RESULT_FIELDS
        if not field_has_value(record["hta_results"][field_name])
    ]


def order_documents_for_extraction(documents: list[TimelineDocument]) -> list[TimelineDocument]:
    return sorted(
        documents,
        key=lambda document: (
            document.is_latest_version,
            document.event_date or "0000-00-00",
            -document.timeline_priority,
            document.lineage_confidence != "strong",
        ),
        reverse=True,
    )


def build_working_record(
    run: RetrievalRun, documents: list[TimelineDocument], model: str
) -> dict[str, Any]:
    now = utc_timestamp()
    ordered_documents = order_documents_for_extraction(documents)
    return {
        "schema_version": SCHEMA_VERSION,
        "document_set": {
            "product_name": run.request.product_name,
            "indication": None,
            "country": run.request.country,
            "documents_considered": [
                {
                    "document_id": document.document_lineage_id
                    or f"{document.source_id}::{document.document_url}",
                    "title": document.title,
                    "source_id": document.source_id,
                    "source_name": document.source_name,
                    "document_url": document.document_url,
                    "local_file_path": document.local_path,
                    "document_type": document.document_type,
                    "format": document.format,
                    "event_date": document.event_date,
                    "publication_date": document.publication_date,
                    "revision_date": document.revision_date,
                    "timeline_priority": document.timeline_priority,
                    "is_latest_version": document.is_latest_version,
                    "match_term": document.match_term,
                    "match_confidence": document.match_confidence,
                    "processing_order": index,
                }
                for index, document in enumerate(ordered_documents, start=1)
            ],
        },
        "progressive_fill": {
            "strategy": "newest_explicit_then_backfill_then_controlled_inference",
            "allow_final_inference": True,
            "overwrite_populated_fields": False,
            "missing_field_policy": "leave_null_when_not_supported",
        },
        **build_empty_extraction_sections(),
        "traceability": {
            "created_at": now,
            "updated_at": now,
            "extraction_model": model,
            "extraction_status": "not_started",
            "warnings": [],
            "audit_log": [],
        },
    }


def normalize_extracted_field(
    value: Any, *, document: TimelineDocument, fill_method: str
) -> dict[str, Any]:
    if isinstance(value, dict) and "value" in value:
        field = empty_extracted_field()
        field.update(value)
    else:
        field = empty_extracted_field()
        field["value"] = value

    field["fill_method"] = fill_method
    field.setdefault("confidence", "unknown")
    field.setdefault("warnings", [])
    field["source_document_id"] = (
        field.get("source_document_id")
        or document.document_lineage_id
        or f"{document.source_id}::{document.document_url}"
    )
    field["source_document_title"] = field.get("source_document_title") or document.title
    field["source_document_url"] = field.get("source_document_url") or document.document_url
    field["source_document_date"] = field.get("source_document_date") or document.event_date
    return field


def merge_extracted_fields(
    record: dict[str, Any],
    extracted: dict[str, Any],
    document: TimelineDocument,
    fill_method: str,
) -> list[str]:
    filled_fields: list[str] = []
    for field_name in HTA_RESULT_FIELDS:
        if field_name not in extracted:
            continue
        if field_has_value(record["hta_results"][field_name]):
            continue

        candidate = normalize_extracted_field(
            extracted[field_name], document=document, fill_method=fill_method
        )
        if not field_has_value(candidate):
            continue

        record["hta_results"][field_name] = candidate
        filled_fields.append(field_name)

    return filled_fields


def build_extraction_prompt(
    *,
    document: TimelineDocument,
    missing_fields: list[str],
    current_record: dict[str, Any],
    fill_method: str,
) -> str:
    inference_note = (
        "This is the final controlled inference pass. You may infer only when the "
        "inference is strongly supported by the provided document. Do not use external "
        "knowledge. Leave fields null if support is weak."
        if fill_method == "inferred_final_pass"
        else "This is an explicit extraction pass. Do not infer. Fill only values directly supported by the document."
    )

    return f"""
You are an HTA evidence analyst.

Extract only the requested fields from the attached document.

{inference_note}

Product: {current_record["document_set"]["product_name"]}
Country: {current_record["document_set"]["country"]}
Source: {document.source_name}
Document title: {document.title}
Document type: {document.document_type}
Document event date: {document.event_date}

Fields to fill:
{json.dumps(missing_fields, indent=2)}

Return valid JSON only. The JSON object must contain only keys from the requested
field list. Each field value must be an object with this shape:

{{
  "value": string | null,
  "source_page": string | null,
  "evidence_snippet": string | null,
  "confidence": "high" | "medium" | "low" | "unknown",
  "warnings": []
}}

Rules:
- If a field is not found, return that field with "value": null.
- Do not fill fields just to complete the schema.
- All output must be in English.
- Prefer concise bullet-style text for long narrative values.
- Include page references when visible in the document.
- Keep evidence snippets short and directly relevant.
""".strip()


class OpenAIExtractionClient:
    def __init__(
        self, *, retry_attempts: int = 4, retry_initial_delay_seconds: int = 25
    ) -> None:
        key = get_openai_api_key()
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        from openai import OpenAI

        self.client = OpenAI(api_key=key)
        self.retry_attempts = retry_attempts
        self.retry_initial_delay_seconds = retry_initial_delay_seconds

    @staticmethod
    def _is_retryable_openai_error(error: Exception) -> bool:
        error_name = type(error).__name__.lower()
        error_message = str(error).lower()
        return (
            "ratelimit" in error_name
            or "rate limit" in error_message
            or "429" in error_message
            or "timeout" in error_name
            or "timeout" in error_message
            or "temporarily" in error_message
            or "server error" in error_message
        )

    def extract_hta_fields(
        self,
        *,
        document: TimelineDocument,
        document_path: Path,
        missing_fields: list[str],
        current_record: dict[str, Any],
        fill_method: str,
        model: str,
    ) -> dict[str, Any]:
        prompt = build_extraction_prompt(
            document=document,
            missing_fields=missing_fields,
            current_record=current_record,
            fill_method=fill_method,
        )
        uploaded_file = self.client.files.create(
            file=document_path.open("rb"), purpose="user_data"
        )
        try:
            for attempt in range(1, self.retry_attempts + 1):
                try:
                    response = self.client.responses.create(
                        model=model,
                        input=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "input_file", "file_id": uploaded_file.id},
                                    {"type": "input_text", "text": prompt},
                                ],
                            }
                        ],
                        text={"format": {"type": "json_object"}},
                    )
                    return json.loads(response.output_text)
                except Exception as error:
                    if (
                        attempt >= self.retry_attempts
                        or not self._is_retryable_openai_error(error)
                    ):
                        raise
                    time.sleep(self.retry_initial_delay_seconds * attempt)
        finally:
            try:
                self.client.files.delete(uploaded_file.id)
            except Exception:
                pass


def run_progressive_hta_extraction(
    run: RetrievalRun,
    *,
    client: ExtractionClient | None = None,
    model: str = DEFAULT_EXTRACTION_MODEL,
    max_documents: int | None = None,
    allow_final_inference: bool = True,
) -> dict[str, Any]:
    normalized_documents = normalize_documents(run.documents)
    assign_document_lineages(normalized_documents)
    ordered_documents = order_documents_for_extraction(
        sort_timeline_documents(normalized_documents)
    )
    if max_documents is not None:
        ordered_documents = ordered_documents[:max_documents]

    record = build_working_record(run, ordered_documents, model)
    record["progressive_fill"]["allow_final_inference"] = allow_final_inference
    record["traceability"]["extraction_status"] = "in_progress"
    extraction_client = client or OpenAIExtractionClient()

    for index, document in enumerate(ordered_documents, start=1):
        missing_fields = missing_hta_fields(record)
        if not missing_fields:
            break
        if document.format != "pdf" or not document.local_path:
            record["traceability"]["warnings"].append(
                f"Skipped non-PDF or missing local file for document: {document.title}"
            )
            continue

        document_path = Path(document.local_path)
        if not document_path.exists():
            record["traceability"]["warnings"].append(
                f"Skipped missing local file: {document.local_path}"
            )
            continue

        fill_method = "explicit_latest" if index == 1 else "explicit_backfill"
        extracted = extraction_client.extract_hta_fields(
            document=document,
            document_path=document_path,
            missing_fields=missing_fields,
            current_record=record,
            fill_method=fill_method,
            model=model,
        )
        filled_fields = merge_extracted_fields(record, extracted, document, fill_method)
        record["traceability"]["audit_log"].append(
            {
                "timestamp": utc_timestamp(),
                "action": fill_method,
                "document_id": document.document_lineage_id
                or f"{document.source_id}::{document.document_url}",
                "fields_attempted": missing_fields,
                "fields_filled": filled_fields,
                "notes": None,
            }
        )

    if allow_final_inference and missing_hta_fields(record):
        for document in ordered_documents:
            missing_fields = missing_hta_fields(record)
            if not missing_fields:
                break
            if document.format != "pdf" or not document.local_path:
                continue
            document_path = Path(document.local_path)
            if not document_path.exists():
                continue

            extracted = extraction_client.extract_hta_fields(
                document=document,
                document_path=document_path,
                missing_fields=missing_fields,
                current_record=record,
                fill_method="inferred_final_pass",
                model=model,
            )
            filled_fields = merge_extracted_fields(
                record, extracted, document, "inferred_final_pass"
            )
            record["traceability"]["audit_log"].append(
                {
                    "timestamp": utc_timestamp(),
                    "action": "inferred_final_pass",
                    "document_id": document.document_lineage_id
                    or f"{document.source_id}::{document.document_url}",
                    "fields_attempted": missing_fields,
                    "fields_filled": filled_fields,
                    "notes": None,
                }
            )

    missing = missing_hta_fields(record)
    for field_name in missing:
        record["hta_results"][field_name]["warnings"].append(
            "Field was not found after progressive extraction."
        )
    record["traceability"]["updated_at"] = utc_timestamp()
    record["traceability"]["extraction_status"] = "success" if not missing else "partial"
    return record


def save_extraction_record(record: dict[str, Any]) -> Path:
    document_set = record["document_set"]
    timestamp = utc_timestamp().replace(":", "-")
    destination = (
        results_dir()
        / "extractions"
        / slugify(document_set["country"])
        / f"{slugify(document_set['product_name'])}__{timestamp}.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return destination
