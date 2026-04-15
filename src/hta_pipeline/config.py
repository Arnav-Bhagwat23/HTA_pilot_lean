from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_path() -> Path:
    return project_root() / "data" / "hta_sources.json"


def load_source_config() -> dict[str, Any]:
    with config_path().open("r", encoding="utf-8") as file:
        return json.load(file)


def product_aliases_path() -> Path:
    return project_root() / "data" / "product_aliases.json"


def load_product_aliases() -> dict[str, list[str]]:
    with product_aliases_path().open("r", encoding="utf-8") as file:
        return json.load(file)
