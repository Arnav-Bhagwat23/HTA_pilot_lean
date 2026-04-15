from __future__ import annotations

from .config import load_source_config
from .models import SourceDefinition


def load_sources() -> list[SourceDefinition]:
    config = load_source_config()
    return [SourceDefinition.from_dict(item) for item in config["sources"]]


def select_sources_for_country(country: str) -> list[SourceDefinition]:
    normalized_country = country.strip().lower()
    selected: list[SourceDefinition] = []

    for source in load_sources():
        if not source.mvp_include:
            continue

        supported = [item.strip().lower() for item in source.supported_countries]
        if "all" in supported or normalized_country in supported:
            selected.append(source)

    return selected
