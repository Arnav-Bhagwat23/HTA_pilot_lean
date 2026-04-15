from __future__ import annotations

import unittest
from collections import defaultdict

from hta_pipeline.models import SearchRequest
from hta_pipeline.retriever import SUPPORTED_SOURCE_HANDLERS, run_retrieval
from hta_pipeline.selector import select_sources_for_country


class LiveUKFlowTests(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.products = ["Keytruda", "Opdivo", "Jemperli"]
        cls.country = "United Kingdom"
        cls.runs = {
            product: run_retrieval(SearchRequest(product_name=product, country=cls.country))
            for product in cls.products
        }
        cls.selected_sources = select_sources_for_country(cls.country)
        cls.selected_source_ids = {source.id for source in cls.selected_sources}
        cls.implemented_source_ids = set(SUPPORTED_SOURCE_HANDLERS)

    def test_multiple_products_return_documents(self) -> None:
        for product, run in self.runs.items():
            with self.subTest(product=product):
                self.assertGreater(
                    len(run.documents),
                    0,
                    msg=f"{product} returned no documents for the UK flow.",
                )

    def test_documents_are_consistent_with_selected_json_sources(self) -> None:
        for product, run in self.runs.items():
            with self.subTest(product=product):
                self.assertEqual(
                    set(run.sources_considered),
                    self.selected_source_ids,
                    msg="Sources considered by the run do not match the JSON selection logic.",
                )
                for document in run.documents:
                    self.assertIn(
                        document.source_id,
                        self.selected_source_ids,
                        msg=f"{product} produced a document from an unexpected source.",
                    )
                    self.assertEqual(
                        document.country,
                        self.country,
                        msg=f"{product} produced a document with the wrong country.",
                    )
                    self.assertLessEqual(
                        document.years_back_limit,
                        4,
                        msg=f"{product} produced a document outside the configured year cap.",
                    )

    def test_relevant_implemented_sources_return_documents_across_suite(self) -> None:
        docs_by_source: dict[str, int] = defaultdict(int)
        for run in self.runs.values():
            for document in run.documents:
                docs_by_source[document.source_id] += 1

        for source_id in sorted(self.implemented_source_ids):
            with self.subTest(source_id=source_id):
                self.assertGreater(
                    docs_by_source[source_id],
                    0,
                    msg=f"Implemented source '{source_id}' returned no documents across the UK test products.",
                )

    def test_pdf_and_local_file_expectations_for_pdf_results(self) -> None:
        for product, run in self.runs.items():
            with self.subTest(product=product):
                pdf_documents = [doc for doc in run.documents if doc.format == "pdf"]
                self.assertGreater(
                    len(pdf_documents),
                    0,
                    msg=f"{product} returned no PDF documents.",
                )
                downloaded = [doc for doc in pdf_documents if doc.local_path]
                self.assertGreater(
                    len(downloaded),
                    0,
                    msg=f"{product} returned PDF documents but none were saved locally.",
                )

    def test_source_coverage_audit_identifies_unimplemented_selected_sources(self) -> None:
        missing = self.selected_source_ids - self.implemented_source_ids
        self.assertSetEqual(
            missing,
            {
                "who_iris_global",
                "nccn_guidelines",
                "esmo_guidelines",
                "clinicaltrials_global",
                "pubmed_global",
            },
            msg="The set of selected-but-unimplemented UK sources changed unexpectedly.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
