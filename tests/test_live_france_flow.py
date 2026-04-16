from __future__ import annotations

import unittest
from collections import defaultdict

from hta_pipeline.models import SearchRequest
from hta_pipeline.retriever import SUPPORTED_SOURCE_HANDLERS, run_retrieval
from hta_pipeline.selector import select_sources_for_country


class LiveFranceFlowTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.products = ["Keytruda", "Opdivo", "Jemperli"]
        cls.country = "France"
        cls.runs = {
            product: run_retrieval(SearchRequest(product_name=product, country=cls.country))
            for product in cls.products
        }
        cls.selected_sources = select_sources_for_country(cls.country)
        cls.selected_source_ids = {source.id for source in cls.selected_sources}
        cls.implemented_source_ids = cls.selected_source_ids & set(SUPPORTED_SOURCE_HANDLERS)

    def test_multiple_products_return_documents(self) -> None:
        for product, run in self.runs.items():
            with self.subTest(product=product):
                self.assertGreater(len(run.documents), 0, msg=f"{product} returned no documents for the France flow.")

    def test_documents_are_consistent_with_selected_json_sources(self) -> None:
        for product, run in self.runs.items():
            with self.subTest(product=product):
                self.assertEqual(set(run.sources_considered), self.selected_source_ids)
                for document in run.documents:
                    self.assertIn(document.source_id, self.selected_source_ids)
                    self.assertEqual(document.country, self.country)
                    self.assertLessEqual(document.years_back_limit, 4)

    def test_relevant_implemented_sources_return_documents_across_suite(self) -> None:
        docs_by_source: dict[str, int] = defaultdict(int)
        for run in self.runs.values():
            for document in run.documents:
                docs_by_source[document.source_id] += 1

        for source_id in sorted(self.implemented_source_ids):
            with self.subTest(source_id=source_id):
                self.assertGreater(docs_by_source[source_id], 0)

    def test_pdf_or_html_outputs_exist_for_has_results(self) -> None:
        for product, run in self.runs.items():
            with self.subTest(product=product):
                has_docs = [doc for doc in run.documents if doc.source_id == "has_france"]
                self.assertGreater(len(has_docs), 0)
                self.assertTrue(any(doc.format in {"pdf", "html"} for doc in has_docs))

    def test_titles_or_urls_match_expected_brand_or_generic(self) -> None:
        for product, expected in [
            ("Keytruda", "pembrolizumab"),
            ("Opdivo", "nivolumab"),
            ("Jemperli", "dostarlimab"),
        ]:
            with self.subTest(product=product):
                docs = [doc for doc in self.runs[product].documents if doc.source_id == "has_france"]
                self.assertGreater(len(docs), 0)
                self.assertTrue(
                    any(expected in doc.title.lower() or expected in doc.document_url.lower() for doc in docs)
                )

    def test_source_coverage_audit_identifies_unimplemented_selected_sources(self) -> None:
        missing = self.selected_source_ids - self.implemented_source_ids
        self.assertSetEqual(
            missing,
            {
                "ema_eu",
                "who_iris_global",
                "nccn_guidelines",
                "esmo_guidelines",
                "clinicaltrials_global",
                "pubmed_global",
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
