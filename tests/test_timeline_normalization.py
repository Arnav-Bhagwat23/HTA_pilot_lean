from __future__ import annotations

import unittest

from hta_pipeline.models import RetrievedDocument
from hta_pipeline.timeline import (
    assign_document_lineages,
    derive_document_lineage,
    normalize_document,
    sort_timeline_documents,
)


def _doc(
    source_id: str,
    title: str,
    document_type: str,
    format: str = "pdf",
    publication_date: str | None = "2025-01-01",
) -> RetrievedDocument:
    return RetrievedDocument(
        source_id=source_id,
        source_name=source_id,
        source_type="hta_agency",
        country="Testland",
        title=title,
        page_url="https://example.com/page",
        document_url="https://example.com/doc.pdf" if format == "pdf" else "https://example.com/doc",
        format=format,
        document_type=document_type,
        publication_date=publication_date,
        revision_date=None,
        years_back_limit=4,
        match_term="Keytruda",
        match_confidence="title_match",
    )


class TimelineNormalizationTests(unittest.TestCase):
    def test_nice_maps_to_final_decision(self) -> None:
        timeline_doc = normalize_document(
            _doc("nice_uk", "Pembrolizumab for lung cancer", "Technology appraisal guidance")
        )
        self.assertEqual(timeline_doc.document_stage, "final_decision")
        self.assertEqual(timeline_doc.document_family, "hta")
        self.assertEqual(timeline_doc.timeline_priority, 1)

    def test_has_summary_maps_to_supporting_material(self) -> None:
        timeline_doc = normalize_document(
            _doc("has_france", "KEYTRUDA summary", "KEYTRUDA SUMMARY CT21313")
        )
        self.assertEqual(timeline_doc.document_stage, "supporting_material")
        self.assertEqual(timeline_doc.timeline_priority, 3)

    def test_has_transcription_maps_to_committee_review(self) -> None:
        timeline_doc = normalize_document(
            _doc("has_france", "KEYTRUDA transcription", "KEYTRUDA TRANSCRIPTION CT21313")
        )
        self.assertEqual(timeline_doc.document_stage, "committee_review")
        self.assertEqual(timeline_doc.timeline_priority, 4)

    def test_gba_modul_maps_to_supporting_material(self) -> None:
        timeline_doc = normalize_document(
            _doc("gba_germany", "Pembrolizumab", "Modul 3 (PDF 1,35 MB)")
        )
        self.assertEqual(timeline_doc.document_stage, "supporting_material")
        self.assertEqual(timeline_doc.timeline_priority, 4)

    def test_gba_iqwig_maps_to_assessment(self) -> None:
        timeline_doc = normalize_document(
            _doc("gba_germany", "Pembrolizumab", "Nutzenbewertung IQWiG (PDF 1,21 MB)")
        )
        self.assertEqual(timeline_doc.document_stage, "assessment")
        self.assertEqual(timeline_doc.timeline_priority, 2)

    def test_aifa_registry_zip_maps_to_registry_update(self) -> None:
        timeline_doc = normalize_document(
            _doc("aifa_italy", "KEYTRUDA RCC", "registry_document", format="zip")
        )
        self.assertEqual(timeline_doc.document_stage, "post_decision_update")
        self.assertEqual(timeline_doc.document_family, "registry")
        self.assertEqual(timeline_doc.timeline_priority, 4)

    def test_aemps_pdf_maps_to_assessment(self) -> None:
        timeline_doc = normalize_document(
            _doc("aemps_spain", "IPT de pembrolizumab", "therapeutic_positioning_report")
        )
        self.assertEqual(timeline_doc.document_stage, "assessment")
        self.assertEqual(timeline_doc.timeline_priority, 1)

    def test_pbac_pdf_maps_to_recommendation(self) -> None:
        timeline_doc = normalize_document(
            _doc("pbac_australia", "Public Summary Document", "Public Summary Document (PSD)")
        )
        self.assertEqual(timeline_doc.document_stage, "recommendation")
        self.assertEqual(timeline_doc.timeline_priority, 1)

    def test_sort_uses_event_date_then_priority(self) -> None:
        doc_late = normalize_document(
            _doc("nice_uk", "Later doc", "Technology appraisal guidance", publication_date="2025-05-01")
        )
        doc_early_low = normalize_document(
            _doc("has_france", "Earlier summary", "summary", publication_date="2025-01-01")
        )
        doc_early_high = normalize_document(
            _doc("nice_uk", "Earlier guidance", "Technology appraisal guidance", publication_date="2025-01-01")
        )
        ordered = sort_timeline_documents([doc_late, doc_early_low, doc_early_high])
        self.assertEqual(ordered[0].event_date, "2025-01-01")
        self.assertEqual(ordered[-1].event_date, "2025-05-01")

    def test_lineage_key_uses_nice_guidance_code(self) -> None:
        doc = normalize_document(
            RetrievedDocument(
                source_id="nice_uk",
                source_name="NICE",
                source_type="hta_agency",
                country="United Kingdom",
                title="Pembrolizumab guidance",
                page_url="https://www.nice.org.uk/guidance/ta123",
                document_url="https://www.nice.org.uk/guidance/ta123/resources/doc.pdf",
                format="pdf",
                document_type="Technology appraisal guidance",
                publication_date="2025-01-01",
                revision_date=None,
                years_back_limit=4,
                match_term="Keytruda",
                match_confidence="title_match",
            )
        )
        lineage_id, confidence, basis = derive_document_lineage(doc)
        self.assertEqual(lineage_id, "nice_uk::ta123")
        self.assertEqual(confidence, "strong")
        self.assertEqual(basis, "same_source_same_guidance")

    def test_lineage_assignment_marks_latest_version(self) -> None:
        older = normalize_document(
            RetrievedDocument(
                source_id="aemps_spain",
                source_name="AEMPS",
                source_type="hta_agency",
                country="Spain",
                title="IPT-130 Jemperli",
                page_url="https://www.aemps.gob.es/informa/ipt-130-jemperli/",
                document_url="https://www.aemps.gob.es/docs/IPT-130-Jemperli-v1.pdf",
                format="pdf",
                document_type="therapeutic_positioning_report",
                publication_date="2024-01-01",
                revision_date=None,
                years_back_limit=4,
                match_term="Jemperli",
                match_confidence="pdf_match",
            )
        )
        newer = normalize_document(
            RetrievedDocument(
                source_id="aemps_spain",
                source_name="AEMPS",
                source_type="hta_agency",
                country="Spain",
                title="IPT-130 Jemperli",
                page_url="https://www.aemps.gob.es/informa/ipt-130-jemperli/",
                document_url="https://www.aemps.gob.es/docs/IPT-130-Jemperli-v2.pdf",
                format="pdf",
                document_type="therapeutic_positioning_report",
                publication_date="2025-02-28",
                revision_date=None,
                years_back_limit=4,
                match_term="Jemperli",
                match_confidence="pdf_match",
            )
        )
        docs = assign_document_lineages([older, newer])
        self.assertEqual(docs[0].document_lineage_id, docs[1].document_lineage_id)
        self.assertEqual(docs[0].version_rank, 1)
        self.assertFalse(docs[0].is_latest_version)
        self.assertEqual(docs[1].version_rank, 2)
        self.assertTrue(docs[1].is_latest_version)

    def test_has_summary_and_transcription_stay_in_separate_lineages(self) -> None:
        summary = normalize_document(
            _doc("has_france", "KEYTRUDA summary", "KEYTRUDA SUMMARY CT21313")
        )
        transcription = normalize_document(
            _doc("has_france", "KEYTRUDA transcription", "KEYTRUDA TRANSCRIPTION CT21313")
        )
        docs = assign_document_lineages([summary, transcription])
        self.assertNotEqual(docs[0].document_lineage_id, docs[1].document_lineage_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
