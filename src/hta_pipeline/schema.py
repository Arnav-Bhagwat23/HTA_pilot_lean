from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SCHEMA_VERSION = "2.0"


@dataclass(frozen=True)
class SchemaSection:
    key: str
    title: str
    fields: tuple[str, ...]
    repeatable: bool = False


HTA_RESULT_FIELDS = (
    "indication",
    "country",
    "brand_and_company",
    "regulatory_approval",
    "hta_outcome",
    "reimbursed_population",
    "cited_driver_efficacy_vs_comparator",
    "cited_driver_nma_itc_results",
    "cited_driver_safety_tolerability",
    "cited_driver_qol",
    "cited_driver_economic_factors",
    "cited_driver_unmet_need_innovation",
    "rationale",
    "notes",
)

TRIAL_RESULT_FIELDS = (
    "indication",
    "country",
    "brand_and_company",
    "regulatory_approval",
    "pivotal_trial",
    "included_population",
    "design",
    "comparator",
    "outcome_week",
    "arm_and_efficacy_results",
    "qol",
    "safety",
    "notes",
)

NMA_ITC_RESULT_FIELDS = (
    "indication",
    "country",
    "drug",
    "agency",
    "year",
    "submission_and_type",
    "treatments_and_trials",
    "population",
    "key_results",
    "key_hta_comment",
    "overall_interpretation_colour_code",
    "notes",
)

ECONOMIC_EVALUATION_FIELDS = (
    "indication",
    "country",
    "drug",
    "agency",
    "year",
    "model_type",
    "time_horizon",
    "comparators",
    "population",
    "utility_data_and_key_results",
    "key_results",
)

GUIDELINE_RESULT_FIELDS = (
    "indication",
    "country",
    "guideline_file_name",
    "society",
    "treatment_flow",
    "mentioned_drugs",
    "alignment_with_hta",
    "notes",
)

SCHEMA_SECTIONS = (
    SchemaSection("hta_results", "HTA Results", HTA_RESULT_FIELDS, repeatable=False),
    SchemaSection("trial_results", "Trial Results", TRIAL_RESULT_FIELDS, repeatable=True),
    SchemaSection(
        "nma_itc_results", "NMA / ITC Results", NMA_ITC_RESULT_FIELDS, repeatable=True
    ),
    SchemaSection(
        "economic_evaluation",
        "Economic Evaluation",
        ECONOMIC_EVALUATION_FIELDS,
        repeatable=True,
    ),
    SchemaSection(
        "guideline_results", "Guideline Results", GUIDELINE_RESULT_FIELDS, repeatable=True
    ),
)

SCHEMA_SECTION_BY_KEY = {section.key: section for section in SCHEMA_SECTIONS}


FIELD_LABELS = {
    "indication": "Indication",
    "country": "Country",
    "brand_and_company": "Brand and Company",
    "regulatory_approval": "Regulatory Approval",
    "hta_outcome": "HTA Outcome",
    "reimbursed_population": "Reimbursed Population",
    "cited_driver_efficacy_vs_comparator": "Cited Driver: Efficacy vs Comparator",
    "cited_driver_nma_itc_results": "Cited Driver: NMA/ITC Results",
    "cited_driver_safety_tolerability": "Cited Driver: Safety / Tolerability",
    "cited_driver_qol": "Cited Driver: QoL",
    "cited_driver_economic_factors": "Cited Driver: Economic Factors",
    "cited_driver_unmet_need_innovation": "Cited Driver: Unmet Need / Innovation",
    "rationale": "Rationale",
    "notes": "Notes",
    "pivotal_trial": "Pivotal Trial",
    "included_population": "Included Population",
    "design": "Design",
    "comparator": "Comparator",
    "outcome_week": "Outcome Week",
    "arm_and_efficacy_results": "Arm and Efficacy Results",
    "qol": "QoL",
    "safety": "Safety",
    "drug": "Drug",
    "agency": "Agency",
    "year": "Year",
    "submission_and_type": "Submission & Type",
    "treatments_and_trials": "Treatments (and trials)",
    "population": "Population",
    "key_results": "Key Results",
    "key_hta_comment": "Key HTA Comment",
    "overall_interpretation_colour_code": "Overall Interpretation (Colour Code)",
    "model_type": "Model Type",
    "time_horizon": "Time horizon",
    "comparators": "Comparators",
    "utility_data_and_key_results": "Utility Data and Key Results",
    "guideline_file_name": "Guideline file name",
    "society": "Society",
    "treatment_flow": "Treatment Flow",
    "mentioned_drugs": "Mentioned drugs",
    "alignment_with_hta": "Alignment with HTA",
}


def empty_extracted_field() -> dict[str, Any]:
    return {
        "value": None,
        "fill_method": "not_found",
        "source_document_id": None,
        "source_document_title": None,
        "source_document_url": None,
        "source_document_date": None,
        "source_page": None,
        "evidence_snippet": None,
        "confidence": "unknown",
        "warnings": [],
    }


def empty_section_fields(section_key: str) -> dict[str, dict[str, Any]]:
    section = SCHEMA_SECTION_BY_KEY[section_key]
    return {field_name: empty_extracted_field() for field_name in section.fields}


def empty_repeatable_item(section_key: str, row_id: str | None = None) -> dict[str, Any]:
    section = SCHEMA_SECTION_BY_KEY[section_key]
    if not section.repeatable:
        raise ValueError(f"{section_key} is not a repeatable schema section.")
    return {
        "row_id": row_id,
        "row_label": None,
        "row_type": None,
        "fields": empty_section_fields(section_key),
    }


def build_empty_extraction_sections() -> dict[str, Any]:
    sections: dict[str, Any] = {}
    for section in SCHEMA_SECTIONS:
        if section.repeatable:
            sections[section.key] = []
        else:
            sections[section.key] = empty_section_fields(section.key)
    return sections


def all_schema_field_paths() -> list[str]:
    paths: list[str] = []
    for section in SCHEMA_SECTIONS:
        if section.repeatable:
            paths.extend(f"{section.key}[]/{field_name}" for field_name in section.fields)
        else:
            paths.extend(f"{section.key}/{field_name}" for field_name in section.fields)
    return paths
