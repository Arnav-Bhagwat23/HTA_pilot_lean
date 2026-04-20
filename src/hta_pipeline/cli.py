from __future__ import annotations

import argparse
import json
from dataclasses import asdict

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
    parser.add_argument("product_name", help="Drug or product name to search for.")
    parser.add_argument("country", help="Country to search within.")
    parser.add_argument(
        "--mode",
        choices=("plan", "run", "extract"),
        default="run",
        help=(
            "Use 'plan' to show source planning only, 'run' to execute retrievers, "
            "or 'extract' to run retrieval and progressive HTA extraction."
        ),
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
        payload = {
            "retrieval_manifest_path": str(manifest_path),
            "extraction_path": str(extraction_path),
            "extraction_status": extraction_record["traceability"][
                "extraction_status"
            ],
        }
        print(json.dumps(payload, indent=2))
        return

    payload = asdict(run)
    payload["manifest_path"] = str(manifest_path)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
