# Timeline Schema

## Purpose

This document defines the recommended timeline schema for the HTA landscaping pipeline.

The goal is to move from simple document gathering to meaningful chronology. Not every retrieved file has the same importance, so the timeline schema is intended to:

- sort documents in a consistent way
- distinguish core HTA artifacts from supporting material
- make later extraction more targeted
- support comparison across countries

## Design Principle

The timeline should be built as a hybrid of:

- publication chronology
- HTA process stage
- revision history

This means a document is not only ordered by date, but also labelled according to what role it plays in the HTA pathway.

## Core Timeline Fields

The following fields should be treated as the normalized timeline layer for each retrieved document.

### 1. `event_date`

Primary sort date for the timeline.

Recommended rule:

- use `publication_date` when available
- if unavailable, use `revision_date`
- if neither is available, leave null and fall back to retrieval ordering

### 2. `publication_date`

Original publication date shown by the source.

Use for:

- baseline chronology
- identifying the first appearance of a document

### 3. `revision_date`

Latest revision or update date shown by the source.

Use for:

- identifying updated documents
- distinguishing revisions from first publication

### 4. `document_stage`

Normalized stage of the HTA process.

Recommended values:

- `pre_assessment`
- `assessment`
- `committee_review`
- `recommendation`
- `final_decision`
- `supporting_material`
- `post_decision_update`
- `regulatory_context`
- `guideline_context`
- `unknown`

This is one of the most important fields for later filtering.

### 5. `document_family`

High-level family for grouping related document types.

Recommended values:

- `hta`
- `guideline`
- `regulatory`
- `registry`
- `supporting`
- `literature`
- `trial`

### 6. `document_type`

Source-specific or semi-normalized document label.

Examples:

- `technology_appraisal_guidance`
- `medicine_advice`
- `hta_opinion`
- `summary`
- `transcription`
- `benefit_assessment`
- `dossier_module`
- `pricing_or_reimbursement_document`
- `registry_document`
- `therapeutic_positioning_report`
- `public_summary_document`

This field should preserve document specificity.

### 7. `timeline_priority`

A numeric or ordinal rank for display ordering when multiple documents share the same date.

Recommended direction:

- `1` = highest importance
- larger numbers = lower importance

Suggested default rules:

- `1`: final guidance, final decision, main recommendation
- `2`: core assessment report, opinion, IPT, PSD
- `3`: summaries, main reasons, committee outputs
- `4`: supporting material, transcripts, annexes
- `5`: registry files, procedural items, background material

### 8. `status`

Status of the document in its lifecycle.

Recommended values:

- `draft`
- `final`
- `updated`
- `superseded`
- `withdrawn`
- `archived`
- `unknown`

### 9. `document_version_label`

Source-provided version label when available.

Examples:

- `v1`
- `v2`
- `updated 2024`
- `revision 3`

### 10. `source`

Human-readable source name.

Examples:

- `NICE`
- `SMC`
- `HAS`
- `G-BA`
- `AIFA`
- `AEMPS`
- `PBS / PBAC`

### 11. `source_id`

Stable pipeline source identifier.

Examples:

- `nice_uk`
- `smc_uk`
- `has_france`
- `gba_germany`
- `aifa_italy`
- `aemps_spain`
- `pbac_australia`

### 12. `country`

Country used for timeline grouping and market-specific interpretation.

### 13. `product_name`

User input product name used for retrieval.

### 14. `brand_name`

Normalized brand label, when known.

### 15. `generic_name`

Normalized generic label, when known.

### 16. `indication`

Optional but highly valuable clinical context field.

This will become important later when we move from product-level grouping to indication-specific timelines.

### 17. `match_confidence`

Confidence score or label explaining why the document was retrieved.

Examples:

- `title_match`
- `detail_page_match`
- `pdf_match`

This is useful for auditability, but should not drive chronology directly.

## Recommended Ordering Rules

The recommended timeline sort order is:

1. `country`
2. `product_name`
3. `indication` when available
4. `event_date` ascending
5. `timeline_priority` ascending
6. `source`
7. `document_type`

If two documents share the same date, the higher-priority document should appear first.

## Country-Specific Expectations

Because each market exposes different document shapes, `document_stage` and `timeline_priority` will need country-specific rules.

### United Kingdom

Primary document patterns:

- NICE technology appraisal guidance
- SMC medicine advice

Suggested treatment:

- guidance/advice PDFs: `final_decision`, priority `1`
- supporting HTML pages: `supporting_material`, priority `4`

### France

Primary document patterns:

- `avis`
- `summary`
- `transcription`
- occasional HTML history pages

Suggested treatment:

- `avis`: `recommendation` or `final_decision`, priority `1`
- `summary`: `supporting_material`, priority `3`
- `transcription`: `committee_review`, priority `4`
- history page: `supporting_material`, priority `5`

### Germany

Primary document patterns:

- dossier modules
- annexes
- IQWiG assessment
- hearing/protocol materials

Suggested treatment:

- IQWiG assessment: `assessment`, priority `2`
- decision-facing G-BA core PDF when later identified: `final_decision`, priority `1`
- modules/annexes: `supporting_material`, priority `4`
- hearing/protocol: `committee_review`, priority `4`

### Italy

Primary document patterns:

- pricing and reimbursement PDFs
- registry documents
- ZIP bundles

Suggested treatment:

- reimbursement determination PDF: `final_decision`, priority `1`
- registry ZIP/file: `post_decision_update` or `registry`, priority `4`
- result page without attachment: `supporting_material`, priority `5`

### Spain

Primary document patterns:

- IPT reports

Suggested treatment:

- IPT PDF: `assessment` or `recommendation`, priority `1`
- IPT landing page: `supporting_material`, priority `4`

### Australia

Primary document patterns:

- PBAC Public Summary Document PDFs

Suggested treatment:

- PSD PDF: `recommendation`, priority `1`
- PSD page fallback: `supporting_material`, priority `4`

## Minimum Useful Timeline Schema

If we want the smallest viable implementation, start with:

- `country`
- `source`
- `product_name`
- `document_title`
- `document_type`
- `document_stage`
- `document_family`
- `event_date`
- `publication_date`
- `revision_date`
- `timeline_priority`
- `status`
- `document_url`
- `local_file_path`

This is the minimum set needed to make the timeline actually useful.

## Questions the Timeline Should Answer

A good timeline should let us answer:

- What was the first relevant HTA document for this product in a country?
- What is the latest meaningful document?
- Which document looks like the main decision artifact?
- Which files are supporting material versus core HTA outputs?
- Which documents are revisions of earlier ones?
- How did the document trail evolve through the HTA process?

## Recommended Next Step

Before building a timeline UI, define a lightweight normalization layer that assigns:

- `event_date`
- `document_stage`
- `document_family`
- `timeline_priority`

to every retrieved document.

That step will create the bridge between:

- raw document collection
- meaningful HTA chronology
