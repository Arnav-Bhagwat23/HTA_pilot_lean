# Extraction Schema Design

This document defines the first-pass extraction schema for the HTA landscaping pipeline. It uses the prior Sanofi HTA extraction workbook as the reference baseline, but adapts it into a JSON-first structure that fits this project's automated retrieval, timeline, lineage, and future backfill layers.

## Goal

The extraction layer should convert selected HTA documents into structured records that can be reviewed, compared across countries, and exported into stakeholder-ready tables.

The schema should support two goals at the same time:

- Preserve the proven extraction domains from the prior workbook.
- Add pipeline metadata so every extracted value remains traceable to a source document, version, and retrieval event.

## Reference Baseline

The prior HTA extraction project used five major extraction tables:

- `HTA Results`
- `Trial Results`
- `NMA / ITC Results`
- `Economic Evaluation`
- `Guideline Results`

The most important retained fields are:

- HTA outcome and reimbursement population
- cited drivers of decision
- pivotal trial evidence
- NMA/ITC evidence
- economic model details
- guideline treatment flow and HTA alignment

## Design Change

The old project stored the schema as flat Excel tabs. This project should use a nested JSON shape.

Reason:

- Documents from different countries do not contain the same information.
- Some sections apply only to certain document types.
- Pipeline metadata and extraction traceability should not be mixed into HTA content fields.
- Nested sections are easier to validate and export later.

## Working Schema vs Export Schema

The extraction pipeline should use a richer working schema while extraction is in progress. In that working schema, every extracted field stores both the value and field-level provenance.

This is needed because the final record may be filled progressively from multiple documents:

- the latest document fills explicitly supported fields first
- older documents fill only missing fields
- a final controlled inference pass may fill remaining fields only when defensible

The stakeholder export can later flatten each field down to the `value`.

Working schema file:

- `data/hta_extraction_working_schema_v1.schema.json`

Export-style schema file:

- `data/hta_extraction_schema_v1.schema.json`

## Proposed JSON Structure

```json
{
  "schema_version": "1.0",
  "document_metadata": {},
  "timeline_metadata": {},
  "hta_summary": {},
  "trial_data": {},
  "nma_itc": {},
  "economic_evaluation": {},
  "guideline_alignment": {},
  "traceability": {}
}
```

## MVP Scope

The MVP extraction schema should start with only the fields needed to summarize the HTA decision and preserve traceability.

MVP sections:

- `document_metadata`
- `timeline_metadata`
- `hta_summary`
- `traceability`

Later sections:

- `trial_data`
- `nma_itc`
- `economic_evaluation`
- `guideline_alignment`

This keeps the first extraction pass focused and avoids forcing every PDF to answer every possible question.

## Section: document_metadata

Purpose: identify the source document being extracted.

MVP fields:

- `product_name`
- `brand_name`
- `generic_name`
- `country`
- `source_id`
- `source_name`
- `source_type`
- `document_title`
- `document_type`
- `document_url`
- `local_file_path`
- `publication_date`
- `revision_date`
- `retrieved_at`

Rationale:

The prior project derived metadata from filenames. This pipeline should derive it from retrieval metadata wherever possible.

## Section: timeline_metadata

Purpose: connect extracted content to the document timeline and version chain.

MVP fields:

- `event_date`
- `document_stage`
- `document_family`
- `timeline_priority`
- `document_lineage_id`
- `version_rank`
- `is_latest_version`
- `lineage_confidence`
- `lineage_basis`

Rationale:

This is a major improvement over the older workbook. Extraction should know whether a document is the latest known version and what role it plays in the HTA process.

## Section: hta_summary

Purpose: capture the main HTA decision and reasons for the decision.

MVP fields:

- `indication`
- `brand_and_company`
- `regulatory_approval`
- `hta_outcome`
- `reimbursed_population`
- `cited_driver_efficacy_vs_comparator`
- `cited_driver_nma_itc_results`
- `cited_driver_safety_tolerability`
- `cited_driver_qol`
- `cited_driver_economic_factors`
- `cited_driver_unmet_need_innovation`
- `rationale`
- `notes`

These fields are directly based on the prior HTA extraction workbook.

## Section: trial_data

Purpose: capture clinical trial evidence used in the submission or assessment.

Later fields:

- `pivotal_trial`
- `included_population`
- `design`
- `comparator`
- `outcome_timepoint`
- `arm_and_efficacy_results`
- `qol_results`
- `safety_results`
- `notes`

Rationale:

This should be a second-phase extraction section. Some HTA decision documents contain this content clearly, but others require deeper parsing of appendices, evidence submissions, or dossier modules.

## Section: nma_itc

Purpose: capture indirect comparison evidence and agency commentary.

Later fields:

- `agency`
- `year`
- `submission_type`
- `treatments_and_trials`
- `population`
- `key_results`
- `key_hta_comment`
- `overall_interpretation`
- `notes`

Rationale:

This matches the prior workbook, but should not be required for every document. Many decision documents either do not include an NMA/ITC or only discuss it briefly.

## Section: economic_evaluation

Purpose: capture economic model evidence and value-for-money conclusions.

Later fields:

- `agency`
- `year`
- `model_type`
- `time_horizon`
- `comparators`
- `population`
- `utility_data_and_key_results`
- `key_results`

Rationale:

This should be separated from the main HTA outcome because economic content varies heavily across agencies. NICE, PBAC, and CADTH-style reports are usually richer here than some other country sources.

## Section: guideline_alignment

Purpose: capture treatment pathway information and alignment between guidelines and HTA positioning.

Later fields:

- `guideline_file_name`
- `society`
- `treatment_flow`
- `mentioned_drugs`
- `alignment_with_hta`
- `notes`

Rationale:

This section is valuable but should not be part of the first extraction pass from HTA PDFs alone. It depends on guideline retrieval and, in the prior project, sometimes required combined guideline plus HTA documents.

## Section: traceability

Purpose: make extraction auditable.

MVP fields:

- `schema_version`
- `extracted_at`
- `extraction_model`
- `extraction_status`
- `extraction_confidence`
- `source_pages`
- `evidence_snippets`
- `warnings`

Rationale:

The older workbook asked the model to include page numbers in many fields, but did not separate traceability into a first-class structure. This project should.

## Field Optionality

Not every section should be required for every document.

Required for MVP extraction:

- `document_metadata`
- `timeline_metadata`
- `hta_summary`
- `traceability`

Optional or later:

- `trial_data`
- `nma_itc`
- `economic_evaluation`
- `guideline_alignment`

## Recommended Extraction Flow

1. Retrieve country documents.
2. Normalize timeline fields.
3. Assign document lineages.
4. Select latest/high-priority documents.
5. Run MVP extraction into `document_metadata`, `timeline_metadata`, `hta_summary`, and `traceability`.
6. Run additional section extractors only when the document type supports them.
7. Export JSON and, later, Excel views.

## How This Improves the Prior Workflow

The prior workflow depended on:

- manual document collection
- manual file renaming
- file-name parsing for country and indication
- one extraction pass per schema tab
- later summarization of long text fields

This project should instead use:

- source-driven document retrieval
- source metadata rather than filename metadata
- timeline and lineage selection
- schema-aware extraction by document type
- traceability fields for audit and review

## First Implementation Recommendation

Start with MVP extraction only:

- `document_metadata`
- `timeline_metadata`
- `hta_summary`
- `traceability`

This gives us a useful structured output quickly. Once that is stable, add `trial_data`, `nma_itc`, `economic_evaluation`, and `guideline_alignment` as separate targeted extractors.
