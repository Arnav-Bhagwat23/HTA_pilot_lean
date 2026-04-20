# Progressive Extraction Strategy

This document defines how collected HTA documents should be used to fill the extraction schema.

The core idea is:

1. Start with the most recent, highest-priority document.
2. Fill only fields that are explicitly supported by that document.
3. Leave unsupported fields blank.
4. Move to the next most recent document.
5. Fill only fields that are still blank.
6. Continue until all available documents have been reviewed.
7. If fields remain blank, run a final controlled inference pass from the document set.
8. Leave fields blank if inference is weak or unsupported.

## Why This Workflow

HTA information is often distributed across several documents. The latest document may contain the final decision, while older or supporting documents may contain trial details, economic rationale, or comparator commentary.

This workflow preserves the priority of the most recent document while still allowing older documents to complete missing fields.

## Ordering Rules

Documents should be processed in this order:

1. Latest version first: `is_latest_version = true`
2. Newest `event_date`
3. Lowest `timeline_priority`
4. Highest lineage confidence
5. Source-specific tie-breakers where needed

The model should not decide which document is latest. That decision belongs to the retrieval, timeline, and lineage layers.

## Pass Types

### Explicit Latest Pass

The first document in the ordered set is processed with strict extraction rules.

Allowed:

- Extract values directly stated in the document.
- Use page references or snippets when available.
- Populate only fields with explicit support.

Not allowed:

- Guessing.
- Filling from general model knowledge.
- Filling because a value is likely.

Field-level `fill_method`:

- `explicit_latest`

### Explicit Backfill Pass

Each subsequent document is processed only for fields that remain blank.

Allowed:

- Fill missing fields that are explicitly stated in the current older/supporting document.
- Preserve existing values from newer documents.
- Add warnings if older content appears to conflict with newer content.

Not allowed:

- Overwriting a populated value.
- Using older content to replace newer content unless a later human review rule is added.

Field-level `fill_method`:

- `explicit_backfill`

### Final Controlled Inference Pass

After all explicit passes are complete, remaining blank fields may receive one final inference attempt.

Allowed:

- Infer only from the retrieved document set.
- Use conservative reasoning.
- Mark the field as inferred.
- Include a confidence value and warning when relevant.

Not allowed:

- External knowledge.
- Unsupported assumptions.
- Filling values only to make the schema complete.

Field-level `fill_method`:

- `inferred_final_pass`

If inference is not defensible, keep the field blank.

Field-level `fill_method`:

- `not_found`

## Field-Level Provenance

Every extracted field should store its own provenance.

Each field should contain:

- `value`
- `fill_method`
- `source_document_id`
- `source_document_title`
- `source_document_url`
- `source_document_date`
- `source_page`
- `evidence_snippet`
- `confidence`
- `warnings`

This allows a final JSON record to contain values from multiple documents while staying auditable.

## Working Schema vs Export Schema

The pipeline should use two representations.

### Working Extraction Schema

The working schema is rich and audit-focused. Every extracted field is an object with value and provenance.

Example:

```json
{
  "hta_results": {
    "hta_outcome": {
      "value": "Recommended with restrictions...",
      "fill_method": "explicit_latest",
      "source_document_id": "nice_uk::ta123",
      "source_document_title": "Example NICE guidance",
      "source_page": "12",
      "evidence_snippet": "The committee recommended...",
      "confidence": "high",
      "warnings": []
    }
  }
}
```

### Export Schema

The export schema is stakeholder-friendly and can flatten each field down to its `value`.

Example:

```json
{
  "hta_results": {
    "hta_outcome": "Recommended with restrictions..."
  }
}
```

## Overwrite Rules

Default rule:

- Do not overwrite populated fields.

Exceptions should be introduced only after review. For now, if a later processed document conflicts with an already-filled value, the pipeline should:

- keep the existing value
- add a warning
- store the conflicting evidence in the audit log

## Missing Field Rules

If a value is not found:

- `value` should be `null`
- `fill_method` should be `not_found`
- `confidence` should be `unknown`
- `warnings` should include a short reason if known

## Recommended First Implementation

The first implementation should support only the MVP extraction sections:

- `document_metadata`
- `timeline_metadata`
- `hta_results`
- `traceability`

Then add:

- `trial_results`
- `nma_itc_results`
- `economic_evaluation`
- `guideline_results`

## Review Principle

Completeness is useful, but correctness matters more.

The model should leave a field blank rather than provide weak or irrelevant content.

