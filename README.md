# HTA_Landscaping_V1

Initial repository for the HTA landscaping project.

## Current MVP direction

The current project scope is an HTA material retrieval pipeline for:

- United Kingdom
- France
- Germany
- Italy
- Spain
- Australia

The first implementation phase focuses on:

- taking a `product_name` and `country`
- selecting matching HTA and supporting sources from configuration
- retrieving relevant materials, preferring PDFs when available
- limiting results to the most recent 4 years

## Project structure

- `data/hta_sources.json`: source configuration and MVP scope
- `docs/timeline_schema.md`: timeline normalization and document ordering design
- `docs/schema_backfill_strategy.md`: rules for filling missing schema fields from previous versions
- `docs/document_lineage_strategy.md`: rules for grouping documents into version lineages
- `docs/extraction_schema_design.md`: first-pass extraction schema design based on the prior HTA workbook
- `docs/progressive_extraction_strategy.md`: newest-first progressive fill strategy with field-level provenance
- `data/extraction_schema_v1.json`: machine-readable draft extraction schema
- `data/hta_extraction_schema_v1.schema.json`: formal JSON Schema for extracted HTA records
- `data/hta_extraction_working_schema_v1.schema.json`: provenance-rich working schema for progressive extraction
- `data/hta_extraction_working_schema_v2.schema.json`: old-project-compatible working schema with repeatable Trial, NMA/ITC, Economic, and Guideline sections
- `src/hta_pipeline/`: pipeline package
- `downloads/`: retrieved files
- `results/`: saved outputs and manifests

## Local secrets

Create a local `.env` file for secrets. Do not commit it.

```bash
OPENAI_API_KEY=your_key_here
```

## Planned local run

Once Python is installed:

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python -m hta_pipeline.cli "drug name" "United Kingdom"
```

To run retrieval, extraction, and create the six-sheet Excel review workbook:

```bash
python -m hta_pipeline.cli "Jemperli" "United Kingdom" --mode extract --export-excel
```

To run the old-project-compatible full-schema extraction layer:

```bash
python -m hta_pipeline.cli "Jemperli" "United Kingdom" --mode extract --schema-scope full
```

To convert an existing filled extraction JSON into Excel:

```bash
python -m hta_pipeline.cli --mode export-excel --extraction-json results/extractions/united-kingdom/jemperli.json
```
