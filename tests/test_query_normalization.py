from __future__ import annotations

import unittest

from hta_pipeline.matching import build_product_aliases
from hta_pipeline.query_normalization import (
    HeuristicQueryNormalizer,
    NormalizedQuery,
    normalize_search_request,
)


class FakeNormalizer:
    def normalize(self, raw_query: str, *, country_hint: str | None = None) -> NormalizedQuery:
        return NormalizedQuery(
            raw_query=raw_query,
            product_name="Keytruda",
            generic_name="pembrolizumab",
            indication="first-line non-small cell lung cancer",
            country="Germany",
            aliases=["Keytruda", "pembrolizumab", "NSCLC"],
            search_terms=["Keytruda", "pembrolizumab", "first-line NSCLC"],
            confidence="high",
            notes=["Normalized by fake test normalizer."],
        )


class QueryNormalizationTests(unittest.TestCase):
    def test_normalize_search_request_from_query(self) -> None:
        request = normalize_search_request(
            raw_query="Keytruda first-line NSCLC in Germany",
            normalizer=FakeNormalizer(),
        )

        self.assertEqual(request.product_name, "Keytruda")
        self.assertEqual(request.generic_name, "pembrolizumab")
        self.assertEqual(request.indication, "first-line non-small cell lung cancer")
        self.assertEqual(request.country, "Germany")
        self.assertEqual(request.aliases, ["Keytruda", "pembrolizumab", "NSCLC"])
        self.assertEqual(request.normalization_confidence, "high")

    def test_explicit_country_overrides_normalized_country(self) -> None:
        request = normalize_search_request(
            raw_query="Keytruda first-line NSCLC in Germany",
            country="France",
            normalizer=FakeNormalizer(),
        )

        self.assertEqual(request.country, "France")

    def test_build_product_aliases_merges_brand_generic_and_query_aliases(self) -> None:
        aliases = build_product_aliases(
            "Keytruda",
            generic_name="pembrolizumab",
            extra_aliases=["NSCLC"],
        )

        self.assertIn("keytruda", aliases)
        self.assertIn("pembrolizumab", aliases)
        self.assertIn("nsclc", aliases)

    def test_heuristic_normalizer_splits_product_indication_and_country(self) -> None:
        normalized = HeuristicQueryNormalizer().normalize(
            "Keytruda first-line NSCLC in Germany"
        )

        self.assertEqual(normalized.product_name, "Keytruda")
        self.assertEqual(normalized.generic_name, "pembrolizumab")
        self.assertEqual(normalized.country, "Germany")
        self.assertEqual(normalized.indication, "NSCLC")


if __name__ == "__main__":
    unittest.main()
