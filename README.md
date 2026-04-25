# HTA_Landscaping_V1

Repository for the HTA landscaping project.

## Current MVP direction

The current project scope is an HTA material retrieval pipeline for:

- United Kingdom
- France
- Germany
- Italy
- Spain
- Australia

The current implementation focuses on:

- taking a `product_name` and `country`
- selecting matching HTA and supporting sources from configuration
- retrieving relevant materials, preferring PDFs when available
- limiting results to the most recent 4 years
- normalizing retrieved materials into a timeline/lineage-aware document set
- extracting structured HTA fields from the latest selected PDF document
- exporting extraction output into an old-project-style Excel workbook

## Current extraction behavior

The extraction layer currently processes the single highest-priority latest
document selected by the timeline ordering logic.

It does not currently perform:

- multi-document backfill across older documents
- final inference across the full retrieved document set

The design docs include progressive extraction and backfill concepts for future
or alternative implementations, but the intended behavior in this repository is
latest-document extraction only.

## Project structure

- `data/hta_sources.json`: source configuration and MVP scope
- `docs/timeline_schema.md`: timeline normalization and document ordering design
- `docs/schema_backfill_strategy.md`: design notes for a possible future backfill layer
- `docs/document_lineage_strategy.md`: rules for grouping documents into version lineages
- `docs/extraction_schema_design.md`: first-pass extraction schema design based on the prior HTA workbook
- `docs/progressive_extraction_strategy.md`: design notes for progressive extraction and field-level provenance
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

## Local run

Once Python is installed:

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python -m hta_pipeline.cli "drug name" "United Kingdom"
```

## Simplest way to run it

If you want other people to use this with the least setup possible:

```bash
pip install -r requirements.txt
set PYTHONPATH=src
python -m hta_pipeline.interactive
```

The interactive runner will:

- ask for an OpenAI API key if one is not already in `.env`
- save that key locally in `.env`
- ask for a free-text prompt such as `Keytruda first-line NSCLC in Germany`
- run retrieval
- run full-schema extraction
- write JSON and Excel outputs

This is the closest current workflow to:

1. clone the repo
2. paste your API key
3. paste your prompt
4. get the output files

To run retrieval, extraction, and create the old-project-style Excel workbook:

```bash
python -m hta_pipeline.cli "Jemperli" "United Kingdom" --mode extract --export-excel
```

To run the old-project-compatible full-schema extraction layer:

```bash
python -m hta_pipeline.cli "Jemperli" "United Kingdom" --mode extract --schema-scope full
```

To run full-schema extraction and export the old-project-style workbook:

```bash
python -m hta_pipeline.cli "Jemperli" "United Kingdom" --mode extract --schema-scope full --export-excel
```

Full-schema extraction defaults to `gpt-4.1-mini` and splits larger PDFs into
temporary page chunks before sending them to the model. You can still override
the model explicitly:

```bash
python -m hta_pipeline.cli "Jemperli" "United Kingdom" --mode extract --schema-scope full --model gpt-4.1
```

To convert an existing filled extraction JSON into Excel:

```bash
python -m hta_pipeline.cli --mode export-excel --extraction-json results/extractions/united-kingdom/jemperli.json
```

## Current modes

- `plan`: show which sources would be selected
- `run`: retrieve documents and save a retrieval manifest
- `extract`: retrieve documents and run latest-document extraction
- `export-excel`: convert an existing extraction JSON into Excel
