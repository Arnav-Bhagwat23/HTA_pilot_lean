from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict

from hta_pipeline.models import SearchRequest
from hta_pipeline.retriever import SUPPORTED_SOURCE_HANDLERS, run_retrieval
from hta_pipeline.selector import select_sources_for_country


def main() -> None:
    products = ["Keytruda", "Opdivo", "Jemperli"]
    country = "United Kingdom"
    runs = {
        product: run_retrieval(SearchRequest(product_name=product, country=country))
        for product in products
    }

    selected_sources = select_sources_for_country(country)
    selected_source_ids = {source.id for source in selected_sources}
    implemented_source_ids = set(SUPPORTED_SOURCE_HANDLERS)

    documents_by_product = {product: len(run.documents) for product, run in runs.items()}
    documents_by_source = Counter()
    source_titles: dict[str, list[str]] = defaultdict(list)

    for run in runs.values():
        for document in run.documents:
            documents_by_source[document.source_id] += 1
            if len(source_titles[document.source_id]) < 5:
                source_titles[document.source_id].append(document.title)

    report = {
        "country": country,
        "products_tested": products,
        "documents_by_product": documents_by_product,
        "selected_sources_from_json": sorted(selected_source_ids),
        "implemented_sources": sorted(implemented_source_ids),
        "unimplemented_selected_sources": sorted(selected_source_ids - implemented_source_ids),
        "documents_by_source": dict(documents_by_source),
        "sample_titles_by_source": dict(source_titles),
        "raw_runs": {product: asdict(run) for product, run in runs.items()},
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
