from __future__ import annotations

import json
from getpass import getpass
from pathlib import Path

from .config import project_root
from .env import get_openai_api_key
from .extraction import (
    DEFAULT_FULL_SCHEMA_MODEL,
    run_progressive_full_schema_extraction,
    save_extraction_record,
)
from .excel_export import write_extraction_excel
from .query_normalization import normalize_search_request
from .retriever import run_retrieval
from .storage import save_manifest


def _env_path() -> Path:
    return project_root() / ".env"


def _save_api_key_if_needed() -> None:
    if get_openai_api_key():
        return

    print("OpenAI API key not found.")
    api_key = getpass("Paste your OPENAI_API_KEY: ").strip()
    if not api_key:
        raise SystemExit("No API key provided. Exiting.")

    _env_path().write_text(f"OPENAI_API_KEY={api_key}\n", encoding="utf-8")
    print(f"Saved key to {_env_path()}")


def main() -> None:
    print("HTA Interactive Runner")
    print("Enter a prompt like: Keytruda first-line NSCLC in Germany")
    _save_api_key_if_needed()

    raw_query = input("Prompt: ").strip()
    if not raw_query:
        raise SystemExit("No prompt provided. Exiting.")

    request = normalize_search_request(raw_query=raw_query)
    print("\nNormalized request:")
    print(
        json.dumps(
            {
                "product_name": request.product_name,
                "country": request.country,
                "generic_name": request.generic_name,
                "indication": request.indication,
                "search_terms": request.search_terms,
            },
            indent=2,
        )
    )

    print("\nRunning retrieval...")
    run = run_retrieval(request)
    manifest_path = save_manifest(run)
    print(f"Retrieved {len(run.documents)} documents.")

    print("Running full-schema extraction...")
    record = run_progressive_full_schema_extraction(
        run,
        model=DEFAULT_FULL_SCHEMA_MODEL,
    )
    extraction_path = save_extraction_record(record)
    excel_path = write_extraction_excel(
        record,
        extraction_path.with_suffix(".xlsx"),
        json_source_path=extraction_path,
    )

    print("\nDone.")
    print(
        json.dumps(
            {
                "retrieval_manifest_path": str(manifest_path),
                "extraction_path": str(extraction_path),
                "extraction_status": record["traceability"]["extraction_status"],
                "excel_path": str(excel_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
