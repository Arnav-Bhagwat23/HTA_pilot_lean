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
    split_pdf_into_chunks,
)
from hta_pipeline.models import RetrievedDocument, RetrievalRun, SearchRequest
from hta_pipeline.timeline import assign_document_lineages, normalize_documents


def _retrieved_document(
    title: str, date: str, local_path: str, source_id: str = "nice_uk"
) -> RetrievedDocument:
    return RetrievedDocument(
        source_id=source_id,
        source_name="NICE" if source_id == "nice_uk" else "SMC",
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
                "document_path": str(kwargs["document_path"]),
                "document_chunk_label": kwargs.get("document_chunk_label"),
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
                "document_path": str(kwargs["document_path"]),
                "document_chunk_label": kwargs.get("document_chunk_label"),
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

    def test_progressive_extraction_reads_only_latest_document(self) -> None:
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
        self.assertIsNone(record["hta_results"]["reimbursed_population"]["value"])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["fill_method"], "explicit_latest")
        self.assertEqual(client.calls[0]["title"], "Newer guidance")
        self.assertEqual(record["traceability"]["extraction_status"], "partial")

    def test_full_schema_extraction_reads_only_latest_document(self) -> None:
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
        self.assertIsNone(record["hta_results"]["reimbursed_population"]["value"])
        self.assertEqual(len(record["trial_results"]), 1)
        self.assertEqual(record["trial_results"][0]["row_id"], "trial-a")
        self.assertEqual(len(record["nma_itc_results"]), 0)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0]["fill_method"], "explicit_latest")
        self.assertEqual(client.calls[0]["title"], "Newer guidance")

    def test_full_schema_extraction_defaults_to_single_latest_document(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "doc.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            run = RetrievalRun(
                request=SearchRequest(product_name="Keytruda", country="United Kingdom"),
                generated_at="2026-01-01T00:00:00+00:00",
                documents=[
                    _retrieved_document("Older NICE guidance", "2024-01-01", str(pdf_path), "nice_uk"),
                    _retrieved_document("Newer NICE guidance", "2025-01-01", str(pdf_path), "nice_uk"),
                    _retrieved_document("Latest SMC advice", "2025-06-01", str(pdf_path), "smc_uk"),
                ],
                sources_considered=["nice_uk", "smc_uk"],
            )
            client = FakeFullSchemaExtractionClient()
            record = run_progressive_full_schema_extraction(
                run,
                client=client,
                model="test-model",
                allow_final_inference=False,
            )

        called_titles = [call["title"] for call in client.calls]
        considered_titles = [
            document["title"] for document in record["document_set"]["documents_considered"]
        ]
        self.assertNotIn("Older NICE guidance", called_titles)
        self.assertEqual(considered_titles, ["Latest SMC advice"])
        self.assertEqual(called_titles, ["Latest SMC advice"])
        self.assertTrue(record["progressive_fill"]["latest_per_source"])

    def test_pdf_chunking_splits_large_pdf_into_page_ranges(self) -> None:
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "large.pdf"
            writer = PdfWriter()
            for _ in range(5):
                writer.add_blank_page(width=72, height=72)
            with pdf_path.open("wb") as handle:
                writer.write(handle)

            chunk_dir = Path(temp_dir) / "chunks"
            chunk_dir.mkdir()
            chunks = split_pdf_into_chunks(pdf_path, chunk_dir, max_pages=2)

        self.assertEqual([label for _path, label in chunks], ["pages 1-2 of 5", "pages 3-4 of 5", "pages 5-5 of 5"])

    def test_full_schema_extraction_uses_pdf_chunks_for_large_documents(self) -> None:
        from pypdf import PdfWriter

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "large.pdf"
            writer = PdfWriter()
            for _ in range(13):
                writer.add_blank_page(width=72, height=72)
            with pdf_path.open("wb") as handle:
                writer.write(handle)

            run = RetrievalRun(
                request=SearchRequest(product_name="Keytruda", country="United Kingdom"),
                generated_at="2026-01-01T00:00:00+00:00",
                documents=[_retrieved_document("Large guidance", "2025-01-01", str(pdf_path))],
                sources_considered=["nice_uk"],
            )
            client = FakeFullSchemaExtractionClient()
            run_progressive_full_schema_extraction(
                run,
                client=client,
                model="test-model",
                allow_final_inference=False,
            )

        chunk_labels = [call["document_chunk_label"] for call in client.calls]
        self.assertIn("pages 1-12 of 13", chunk_labels)
        self.assertIn("pages 13-13 of 13", chunk_labels)


if __name__ == "__main__":
    unittest.main()
