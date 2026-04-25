from __future__ import annotations

import re

from .config import load_product_aliases


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def build_product_aliases(
    product_name: str,
    *,
    generic_name: str | None = None,
    extra_aliases: list[str] | None = None,
) -> list[str]:
    aliases = load_product_aliases()
    requested_values = [product_name]
    if generic_name:
        requested_values.append(generic_name)
    if extra_aliases:
        requested_values.extend(extra_aliases)

    normalized_requested = {
        normalize_text(value) for value in requested_values if normalize_text(value)
    }

    for canonical_name, values in aliases.items():
        normalized_values = {normalize_text(value) for value in values + [canonical_name]}
        if normalized_requested & normalized_values:
            return sorted(normalized_values | normalized_requested)

    return sorted(normalized_requested) or [normalize_text(product_name)]


def text_contains_any_alias(text: str, aliases: list[str]) -> bool:
    normalized_text = normalize_text(text)
    return any(alias in normalized_text for alias in aliases)


def classify_match_confidence(
    listing_text: str, detail_text: str, pdf_urls: list[str], aliases: list[str]
) -> str:
    listing_match = text_contains_any_alias(listing_text, aliases)
    detail_match = text_contains_any_alias(detail_text, aliases)
    pdf_match = any(text_contains_any_alias(url, aliases) for url in pdf_urls)

    if pdf_match:
        return "pdf_match"
    if detail_match:
        return "detail_page_match"
    if listing_match:
        return "title_match"
    return "no_match"
