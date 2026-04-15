from __future__ import annotations

import unittest
from pathlib import Path

from hta_pipeline.models import SearchRequest
from hta_pipeline.selector import load_sources
from hta_pipeline.sources.cadth import parse_find_reports_listing, search_cadth


class CadthCanadaFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = [source for source in load_sources() if source.id == "cadth_canada"][0]
        fixture_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "cadth"
            / "find_reports_reimbursement_review.html"
        )
        cls.fixture_html = fixture_path.read_text(encoding="utf-8")

    def test_listing_parser_reads_rows(self) -> None:
        entries = parse_find_reports_listing(self.fixture_html)
        self.assertGreaterEqual(len(entries), 4)
        self.assertEqual(entries[0].brand_name, "Keytruda")
        self.assertEqual(entries[1].generic_name, "nivolumab")

    def test_keytruda_canada_returns_recent_documents(self) -> None:
        documents, scan_log = search_cadth(
            self.source, SearchRequest(product_name="Keytruda", country="Canada")
        )
        self.assertGreaterEqual(len(documents), 3)
        self.assertTrue(
            any(doc.match_confidence in {"pdf_match", "detail_page_match"} for doc in documents)
        )
        self.assertTrue(all(doc.source_id == "cadth_canada" for doc in documents))
        self.assertTrue(all((doc.publication_date or "")[:4] >= "2022" for doc in documents))
        self.assertGreater(len(scan_log), 0)

    def test_multiple_products_match_expected_brand_or_generic(self) -> None:
        for product, expected in [
            ("Keytruda", "pembrolizumab"),
            ("Opdivo", "nivolumab"),
            ("Jemperli", "dostarlimab"),
        ]:
            with self.subTest(product=product):
                documents, _ = search_cadth(
                    self.source, SearchRequest(product_name=product, country="Canada")
                )
                self.assertGreater(len(documents), 0)
                self.assertTrue(
                    any(expected in doc.title.lower() or expected in doc.document_url.lower() for doc in documents)
                )

    def test_old_documents_are_filtered_out_by_year_cap(self) -> None:
        documents, _ = search_cadth(
            self.source, SearchRequest(product_name="Keytruda", country="Canada")
        )
        urls = [doc.document_url for doc in documents]
        self.assertFalse(any("PC0295" in url for url in urls))


if __name__ == "__main__":
    unittest.main(verbosity=2)
