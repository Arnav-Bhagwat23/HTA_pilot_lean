from __future__ import annotations

import json
import unittest
from pathlib import Path

from hta_pipeline.extraction import build_working_record
from hta_pipeline.models import RetrievalRun, SearchRequest
from hta_pipeline.schema import (
    ECONOMIC_EVALUATION_FIELDS,
    GUIDELINE_RESULT_FIELDS,
    HTA_RESULT_FIELDS,
    NMA_ITC_RESULT_FIELDS,
    SCHEMA_SECTIONS,
    SCHEMA_VERSION,
    TRIAL_RESULT_FIELDS,
    all_schema_field_paths,
    empty_repeatable_item,
)


class SchemaLayerTests(unittest.TestCase):
    def test_schema_sections_match_old_project_and_repeatable_design(self) -> None:
        sections = {section.key: section for section in SCHEMA_SECTIONS}
        self.assertEqual(tuple(sections["hta_results"].fields), HTA_RESULT_FIELDS)
        self.assertFalse(sections["hta_results"].repeatable)
        self.assertEqual(tuple(sections["trial_results"].fields), TRIAL_RESULT_FIELDS)
        self.assertEqual(tuple(sections["nma_itc_results"].fields), NMA_ITC_RESULT_FIELDS)
        self.assertEqual(
            tuple(sections["economic_evaluation"].fields), ECONOMIC_EVALUATION_FIELDS
        )
        self.assertEqual(
            tuple(sections["guideline_results"].fields), GUIDELINE_RESULT_FIELDS
        )
        self.assertTrue(sections["trial_results"].repeatable)
        self.assertTrue(sections["nma_itc_results"].repeatable)
        self.assertTrue(sections["economic_evaluation"].repeatable)
        self.assertTrue(sections["guideline_results"].repeatable)

    def test_working_record_initializes_full_schema_shape(self) -> None:
        run = RetrievalRun(
            request=SearchRequest(product_name="Jemperli", country="United Kingdom"),
            generated_at="2026-04-20T00:00:00+00:00",
            documents=[],
            sources_considered=[],
        )
        record = build_working_record(run, [], "test-model")
        self.assertEqual(record["schema_version"], SCHEMA_VERSION)
        self.assertEqual(set(record["hta_results"]), set(HTA_RESULT_FIELDS))
        self.assertEqual(record["trial_results"], [])
        self.assertEqual(record["nma_itc_results"], [])
        self.assertEqual(record["economic_evaluation"], [])
        self.assertEqual(record["guideline_results"], [])

    def test_repeatable_items_can_hold_multiple_rows(self) -> None:
        pivotal = empty_repeatable_item("trial_results", row_id="trial-1")
        supporting = empty_repeatable_item("trial_results", row_id="trial-2")
        pivotal["row_label"] = "Pivotal trial"
        supporting["row_label"] = "Supporting trial"
        self.assertEqual(pivotal["fields"]["pivotal_trial"]["value"], None)
        self.assertNotEqual(pivotal["row_id"], supporting["row_id"])

    def test_field_paths_include_array_markers_for_repeatable_sections(self) -> None:
        paths = all_schema_field_paths()
        self.assertIn("hta_results/hta_outcome", paths)
        self.assertIn("trial_results[]/pivotal_trial", paths)
        self.assertIn("nma_itc_results[]/key_results", paths)
        self.assertIn("economic_evaluation[]/model_type", paths)
        self.assertIn("guideline_results[]/treatment_flow", paths)

    def test_v2_json_schema_is_valid_json_and_repeatable(self) -> None:
        schema_path = Path("data/hta_extraction_working_schema_v2.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["schema_version"]["const"], "2.0")
        self.assertEqual(schema["properties"]["trial_results"]["type"], "array")
        self.assertEqual(schema["properties"]["nma_itc_results"]["type"], "array")
        self.assertEqual(schema["properties"]["economic_evaluation"]["type"], "array")
        self.assertEqual(schema["properties"]["guideline_results"]["type"], "array")


if __name__ == "__main__":
    unittest.main()
