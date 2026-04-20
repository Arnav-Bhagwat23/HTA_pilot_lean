from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hta_pipeline.extraction import (
    HTA_RESULT_FIELDS,
    build_working_record,
    missing_hta_fields,
    run_progressive_full_schema_extraction,
    run_progressive_hta_extraction,
)
from hta_pipeline.models import RetrievedDocument, RetrievalRun, SearchRequest
from hta_pipeline.timeline import assign_document_lineages, normalize_documents


def _retrieved_document(title: str, date: str, local_path: str) -> RetrievedDocument:
    return RetrievedDocument(
        source_id="nice_uk",
        source_name="NICE",
        source_type="hta_agency",
        country="United Kingdom",
        title=title,
        page_url="https://www.nice.org.uk/guidance/ta123",
        document_url="https://www.nice.org.uk/guidance/ta123/resources/doc.pdf",
        format="pdf",
        document_type="Technology appraisal guidance",
        publication_date=date,
        revision_date=None,
        years_back_limit=4,
        match_term="Keytruda",
        match_confidence="title_match",
        local_path=local_path,
    )


class FakeExtractionClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def extract_hta_fields(self, **kwargs):
        missing_fields = kwargs["missing_fields"]
        fill_method = kwargs["fill_method"]
        document = kwargs["document"]
        self.calls.append(
            {
                "missing_fields": list(missing_fields),
                "fill_method": fill_method,
                "title": document.title,
            }
        )
        if fill_method == "explicit_latest":
            return {
                "hta_outcome": {
                    "value": "Recommended with restrictions.",
                    "source_page": "1",
                    "evidence_snippet": "The committee recommended...",
                    "confidence": "high",
                    "warnings": [],
                }
            }
        if fill_method == "explicit_backfill":
            return {
                "reimbursed_population": {
                    "value": "Adults with previously treated disease.",
                    "source_page": "2",
                    "evidence_snippet": "Adults with...",
                    "confidence": "medium",
                    "warnings": [],
                }
            }
        return {}


class FakeFullSchemaExtractionClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def extract_hta_fields(self, **kwargs):
        raise AssertionError("HTA-only extraction should not be called.")

    def extract_full_schema(self, **kwargs):
        fill_method = kwargs["fill_method"]
        document = kwargs["document"]
        self.calls.append(
            {
                "fill_method": fill_method,
                "title": document.title,
                "targets": kwargs["extraction_targets"],
            }
        )
        if fill_method == "explicit_latest":
            return {
                "hta_results": {
                    "hta_outcome": {
                        "value": "Recommended with restrictions.",
                        "source_page": "1",
                        "evidence_snippet": "recommended with restrictions",
                        "confidence": "high",
                        "warnings": [],
                    }
                },
                "trial_results": [
                    {
                        "row_id": "trial-a",
                        "row_label": "Trial A",
                        "row_type": "pivotal_trial",
                        "fields": {
                            "pivotal_trial": {
                                "value": "Trial A",
                                "source_page": "3",
                                "evidence_snippet": "Trial A",
                                "confidence": "high",
                                "warnings": [],
                            },
                            "design": {
                                "value": "Randomised controlled trial.",
                                "source_page": "4",
                                "evidence_snippet": "randomised",
                                "confidence": "high",
                                "warnings": [],
                            },
                        },
                    }
                ],
                "nma_itc_results": [],
                "economic_evaluation": [],
                "guideline_results": [],
            }
        if fill_method == "explicit_backfill":
            return {
                "hta_results": {
                    "hta_outcome": {
                        "value": "This should not overwrite.",
                        "source_page": "1",
                        "evidence_snippet": "overwrite",
                        "confidence": "high",
                        "warnings": [],
                    },
                    "reimbursed_population": {
                        "value": "Adults with eligible disease.",
                        "source_page": "2",
                        "evidence_snippet": "Adults",
                        "confidence": "medium",
                        "warnings": [],
                    },
                },
                "trial_results": [
                    {
                        "row_id": "trial-b",
                        "row_label": "Trial B",
                        "row_type": "supporting_trial",
                        "fields": {
                            "pivotal_trial": {
                                "value": "Trial B",
                                "source_page": "5",
                                "evidence_snippet": "Trial B",
                                "confidence": "medium",
                                "warnings": [],
                            }
                        },
                    }
                ],
                "nma_itc_results": [
                    {
                        "row_id": "nma-1",
                        "row_label": "NMA 1",
                        "row_type": "NMA",
                        "fields": {
                            "key_results": {
                                "value": "Mixed indirect comparison results.",
                                "source_page": "8",
                                "evidence_snippet": "mixed results",
                                "confidence": "medium",
                                "warnings": [],
                            }
                        },
                    }
                ],
                "economic_evaluation": [],
                "guideline_results": [],
            }
        return {}


class ExtractionEngineTests(unittest.TestCase):
    def test_working_record_starts_with_all_hta_fields_missing(self) -> None:
        run = RetrievalRun(
            request=SearchRequest(product_name="Keytruda", country="United Kingdom"),
            generated_at="2026-01-01T00:00:00+00:00",
            documents=[],
            sources_considered=[],
        )
        record = build_working_record(run, [], "test-model")
        self.assertEqual(set(missing_hta_fields(record)), set(HTA_RESULT_FIELDS))

    def test_progressive_extraction_fills_missing_fields_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "doc.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            run = RetrievalRun(
                request=SearchRequest(product_name="Keytruda", country="United Kingdom"),
                generated_at="2026-01-01T00:00:00+00:00",
                documents=[
                    _retrieved_document("Older guidance", "2024-01-01", str(pdf_path)),
                    _retrieved_document("Newer guidance", "2025-01-01", str(pdf_path)),
                ],
                sources_considered=["nice_uk"],
            )
            client = FakeExtractionClient()
            record = run_progressive_hta_extraction(
                run,
                client=client,
                model="test-model",
                allow_final_inference=False,
            )

        self.assertEqual(
            record["hta_results"]["hta_outcome"]["value"],
            "Recommended with restrictions.",
        )
        self.assertEqual(
            record["hta_results"]["hta_outcome"]["fill_method"], "explicit_latest"
        )
        self.assertEqual(
            record["hta_results"]["reimbursed_population"]["value"],
            "Adults with previously treated disease.",
        )
        self.assertEqual(
            record["hta_results"]["reimbursed_population"]["fill_method"],
            "explicit_backfill",
        )
        self.assertEqual(client.calls[0]["fill_method"], "explicit_latest")
        self.assertNotIn(
            "hta_outcome",
            client.calls[1]["missing_fields"],
            "Backfill calls should only request fields still missing.",
        )
        self.assertEqual(record["traceability"]["extraction_status"], "partial")

    def test_full_schema_extraction_appends_repeatable_rows_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "doc.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            run = RetrievalRun(
                request=SearchRequest(product_name="Keytruda", country="United Kingdom"),
                generated_at="2026-01-01T00:00:00+00:00",
                documents=[
                    _retrieved_document("Older guidance", "2024-01-01", str(pdf_path)),
                    _retrieved_document("Newer guidance", "2025-01-01", str(pdf_path)),
                ],
                sources_considered=["nice_uk"],
            )
            client = FakeFullSchemaExtractionClient()
            record = run_progressive_full_schema_extraction(
                run,
                client=client,
                model="test-model",
                allow_final_inference=False,
            )

        self.assertEqual(
            record["hta_results"]["hta_outcome"]["value"],
            "Recommended with restrictions.",
        )
        self.assertEqual(
            record["hta_results"]["reimbursed_population"]["value"],
            "Adults with eligible disease.",
        )
        self.assertEqual(len(record["trial_results"]), 2)
        self.assertEqual(record["trial_results"][0]["row_id"], "trial-a")
        self.assertEqual(record["trial_results"][1]["row_id"], "trial-b")
        self.assertEqual(len(record["nma_itc_results"]), 1)
        self.assertEqual(
            record["nma_itc_results"][0]["fields"]["key_results"]["value"],
            "Mixed indirect comparison results.",
        )
        self.assertEqual(client.calls[0]["fill_method"], "explicit_latest")
        self.assertEqual(client.calls[1]["fill_method"], "explicit_backfill")


if __name__ == "__main__":
    unittest.main()
