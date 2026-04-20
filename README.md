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
- `src/hta_pipeline/`: pipeline package
- `downloads/`: retrieved files
- `results/`: saved outputs and manifests

## Planned local run

Once Python is installed:

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python -m hta_pipeline.cli "drug name" "United Kingdom"
```
