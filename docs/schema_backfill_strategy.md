# Schema Backfill Strategy

## Purpose

This document defines how missing schema fields should be backfilled from previous document versions.

The goal is to improve schema completeness without overwriting newer truth with older content.

## Design Principle

Backfilling should work as:

1. use the current version first
2. if a field is missing, check the immediately previous version
3. if still missing, continue walking backward version by version
4. stop when a value is found or no earlier version remains

The current version is always authoritative.

Older versions should only:

- fill blanks
- never overwrite a non-null field from the current version

## Core Rule

For every field:

- if current value exists, keep it
- if current value is null or empty, try prior versions in reverse chronological order
- fill from the first prior version that contains a usable value

## Provenance Requirement

Backfilled values should not be silent.

Whenever a field is backfilled, the schema should preserve:

- the final field value
- whether the field was backfilled
- which version the value came from

Recommended metadata fields:

- `<field_name>_backfilled`
- `<field_name>_source_version`

Examples:

- `indication_backfilled = true`
- `indication_source_version = v2`
- `status_backfilled = false`

## Version Chain Requirements

Backfill depends on version grouping, so each document lineage should eventually support:

- `document_lineage_id`
- `version_rank`
- `is_latest_version`

These fields do not have to be fully implemented now, but the backfill design assumes they will exist.

## Backfill Categories

Fields should not all be treated the same. They fall into three groups.

### 1. Safe To Backfill

These fields are usually stable enough to inherit from earlier versions when missing:

- `country`
- `source`
- `source_id`
- `source_type`
- `product_name`
- `brand_name`
- `generic_name`
- `document_family`
- `document_stage` when the document lineage clearly represents the same HTA artifact

Default behavior:

- allow automatic backward fill

### 2. Conditional Backfill

These fields may be backfilled, but only with provenance tracking and caution:

- `publication_date`
- `document_type`
- `status`
- `document_version_label`
- `indication`
- `timeline_priority`
- `event_date`

Default behavior:

- allow backward fill only when current value is missing
- preserve provenance
- never overwrite the current value

Special note on `event_date`:

- if `event_date` is derived from `publication_date`, then it may be indirectly backfilled
- if `event_date` is explicitly tied to the current version, then it should not be inherited blindly

### 3. Never Backfill

These fields are version-specific and should always describe the current retrieved file:

- `revision_date`
- `retrieved_at`
- `source_last_seen_at`
- `content_hash`
- `document_url`
- `page_url`
- `local_file_path`
- `match_confidence`

Default behavior:

- do not backfill

## Recommended Field-Level Rules

### Identity Fields

- `product_name`: safe
- `brand_name`: safe
- `generic_name`: safe
- `country`: safe
- `source`: safe
- `source_id`: safe

Rationale:

- these identify the object or source context and should remain stable across versions

### Classification Fields

- `document_family`: safe
- `document_stage`: conditional-safe
- `document_type`: conditional
- `timeline_priority`: conditional
- `status`: conditional

Rationale:

- these may drift as the document evolves, so backfill is useful but should be traceable

### Time Fields

- `publication_date`: conditional
- `revision_date`: never
- `event_date`: conditional

Rationale:

- `publication_date` can often be preserved from earlier versions
- `revision_date` belongs to the current version only

### Linkage Fields

- `document_url`: never
- `page_url`: never
- `local_file_path`: never

Rationale:

- these are concrete pointers to the current retrieved asset

### Audit Fields

- `match_confidence`: never
- `content_hash`: never
- `retrieved_at`: never
- `source_last_seen_at`: never

Rationale:

- these are about the retrieval event, not the document lineage

### Clinical Context

- `indication`: conditional

Rationale:

- indication is very valuable and often stable, but must be backfilled carefully because newer versions may broaden or narrow the use case

## Example Backfill Behavior

### Example 1: Missing Indication On Current Version

Current version:

- `indication = null`
- `document_version_label = v3`

Previous version:

- `indication = metastatic melanoma`

Result:

- `indication = metastatic melanoma`
- `indication_backfilled = true`
- `indication_source_version = v2`

### Example 2: Current Version Has A Different Status

Current version:

- `status = final`

Previous version:

- `status = draft`

Result:

- keep `status = final`
- do not overwrite with `draft`

### Example 3: Missing Publication Date

Current version:

- `publication_date = null`

Previous version:

- `publication_date = 2024-06-14`

Result:

- `publication_date = 2024-06-14`
- `publication_date_backfilled = true`

## Backfill Execution Order

Recommended enrichment order:

1. retrieve raw document
2. normalize timeline fields
3. group documents into version lineages
4. apply field-level backfill
5. emit enriched timeline-ready schema

Backfill should happen after normalization, not before.

That order is important because:

- normalization helps identify comparable documents
- backfill depends on knowing whether two files belong to the same lineage

## Country-Specific Notes

### United Kingdom

Likely useful backfill targets:

- `publication_date`
- `document_version_label`

Likely low risk because document families are relatively clean.

### France

Likely useful backfill targets:

- `indication`
- `document_stage`
- `document_type`

Needs caution because `avis`, `summary`, and `transcription` are related but not equivalent.

### Germany

Likely useful backfill targets:

- `document_stage`
- `timeline_priority`
- `publication_date`

Needs caution because dossier modules and decision-facing artifacts should not be conflated.

### Italy

Likely useful backfill targets:

- `status`
- `publication_date`
- `document_stage`

Needs caution because ZIP-based registry files and reimbursement PDFs serve different purposes.

### Spain

Likely useful backfill targets:

- `publication_date`
- `document_version_label`
- `indication`

Likely low risk because IPT records are relatively structured.

### Australia

Likely useful backfill targets:

- `publication_date`
- `document_stage`

Likely low risk because PSD records are relatively consistent.

## Minimal First Implementation

The first backfill implementation should only support:

- `brand_name`
- `generic_name`
- `publication_date`
- `document_stage`
- `document_family`
- `timeline_priority`
- `indication`

This keeps the first pass manageable while still improving schema completeness in a meaningful way.

## Rules To Avoid

Do not:

- overwrite a current non-null value with an older value
- backfill retrieval-event fields
- merge unrelated documents into one lineage
- assume all documents with the same product name are versions of the same artifact

## Recommended Next Step

After the timeline normalization layer, add:

1. version lineage grouping
2. field-level backfill using the rules above
3. provenance tracking for all backfilled values

That will give the project a more complete and auditable schema without losing version truth.
