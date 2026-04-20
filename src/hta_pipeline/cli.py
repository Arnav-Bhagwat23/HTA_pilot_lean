from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .excel_export import export_extraction_json_to_excel, write_extraction_excel
from .extraction import (
    DEFAULT_EXTRACTION_MODEL,
    run_progressive_hta_extraction,
    save_extraction_record,
)
from .models import SearchRequest
from .retriever import plan_retrieval, run_retrieval
from .storage import save_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan HTA source retrieval for a product and country."
    )
    parser.add_argument(
        "product_name",
        nargs="?",
        help="Drug or product name to search for.",
    )
    parser.add_argument(
        "country",
        nargs="?",
        help="Country to search within.",
    )
    parser.add_argument(
        "--mode",
        choices=("plan", "run", "extract", "export-excel"),
        default="run",
        help=(
            "Use 'plan' to show source planning only, 'run' to execute retrievers, "
            "'extract' to run retrieval and progressive HTA extraction, or "
            "'export-excel' to convert a filled extraction JSON into a workbook."
        ),
    )
    parser.add_argument(
        "--extraction-json",
        type=Path,
        default=None,
        help="Filled extraction JSON to convert when using export-excel mode.",
    )
    parser.add_argument(
        "--excel-path",
        type=Path,
        default=None,
        help="Optional destination path for the generated Excel workbook.",
    )
    parser.add_argument(
        "--export-excel",
        action="store_true",
        help="Also export an Excel workbook after extraction mode completes.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_EXTRACTION_MODEL,
        help="OpenAI model to use for extraction mode.",
    )
    parser.add_argument(
        "--max-documents",
        type=int,
        default=None,
        help="Optional maximum number of ordered documents to use in extraction mode.",
    )
    parser.add_argument(
        "--no-final-inference",
        action="store_true",
        help="Disable the final controlled inference pass in extraction mode.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "export-excel":
        if args.extraction_json is None:
            parser.error("--extraction-json is required for export-excel mode.")
        excel_path = export_extraction_json_to_excel(
            args.extraction_json, destination=args.excel_path
        )
        print(json.dumps({"excel_path": str(excel_path)}, indent=2))
        return

    if not args.product_name or not args.country:
        parser.error("product_name and country are required unless using export-excel mode.")

    request = SearchRequest(product_name=args.product_name, country=args.country)
    if args.mode == "plan":
        plan = plan_retrieval(request)
        payload = [asdict(candidate) for candidate in plan]
        print(json.dumps(payload, indent=2))
        return

    run = run_retrieval(request)
    manifest_path = save_manifest(run)
    if args.mode == "extract":
        extraction_record = run_progressive_hta_extraction(
            run,
            model=args.model,
            max_documents=args.max_documents,
            allow_final_inference=not args.no_final_inference,
        )
        extraction_path = save_extraction_record(extraction_record)
        excel_path = None
        if args.export_excel:
            excel_path = write_extraction_excel(
                extraction_record,
                args.excel_path or extraction_path.with_suffix(".xlsx"),
                json_source_path=extraction_path,
            )
        payload = {
            "retrieval_manifest_path": str(manifest_path),
            "extraction_path": str(extraction_path),
            "extraction_status": extraction_record["traceability"][
                "extraction_status"
            ],
        }
        if excel_path:
            payload["excel_path"] = str(excel_path)
        print(json.dumps(payload, indent=2))
        return

    payload = asdict(run)
    payload["manifest_path"] = str(manifest_path)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
