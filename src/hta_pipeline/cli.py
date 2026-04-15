from __future__ import annotations

import argparse
import json
from dataclasses import asdict

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
        choices=("plan", "run"),
        default="run",
        help="Use 'plan' to show source planning only, or 'run' to execute implemented retrievers.",
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
    payload = asdict(run)
    payload["manifest_path"] = str(manifest_path)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
