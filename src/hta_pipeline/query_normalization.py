from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Protocol

from .config import load_product_aliases, load_source_config
from .env import get_openai_api_key
from .models import SearchRequest


COUNTRY_ALIASES = {
    "uk": "United Kingdom",
    "united kingdom": "United Kingdom",
    "great britain": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "france": "France",
    "germany": "Germany",
    "de": "Germany",
    "italy": "Italy",
    "spain": "Spain",
    "australia": "Australia",
}


@dataclass(slots=True)
class NormalizedQuery:
    raw_query: str
    product_name: str
    country: str | None = None
    generic_name: str | None = None
    indication: str | None = None
    aliases: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    confidence: str = "low"
    notes: list[str] = field(default_factory=list)


class QueryNormalizer(Protocol):
    def normalize(
        self, raw_query: str, *, country_hint: str | None = None
    ) -> NormalizedQuery: ...


def supported_countries() -> list[str]:
    return list(load_source_config().get("active_geographies", []))


def normalize_search_request(
    *,
    product_name: str | None = None,
    country: str | None = None,
    raw_query: str | None = None,
    normalizer: QueryNormalizer | None = None,
) -> SearchRequest:
    if raw_query:
        chosen_normalizer = normalizer or build_default_query_normalizer()
        try:
            normalized = chosen_normalizer.normalize(raw_query, country_hint=country)
        except Exception as error:
            if isinstance(chosen_normalizer, HeuristicQueryNormalizer):
                raise
            normalized = HeuristicQueryNormalizer().normalize(
                raw_query, country_hint=country
            )
            normalized.notes.append(
                f"Fell back to heuristic normalization because the LLM normalizer failed: {error}"
            )
        resolved_country = country or normalized.country
        if not resolved_country:
            raise ValueError("Could not determine a supported country from the query.")
        return SearchRequest(
            product_name=normalized.product_name,
            country=resolved_country,
            generic_name=normalized.generic_name,
            indication=normalized.indication,
            raw_query=normalized.raw_query,
            aliases=normalized.aliases,
            search_terms=normalized.search_terms,
            normalization_confidence=normalized.confidence,
            normalization_notes=normalized.notes,
        )

    if not product_name or not country:
        raise ValueError("product_name and country are required when raw_query is not used.")

    return SearchRequest(
        product_name=product_name,
        country=country,
        raw_query=product_name,
        search_terms=[product_name],
    )


def build_default_query_normalizer() -> QueryNormalizer:
    if get_openai_api_key():
        return OpenAIQueryNormalizer()
    return HeuristicQueryNormalizer()


class HeuristicQueryNormalizer:
    def normalize(
        self, raw_query: str, *, country_hint: str | None = None
    ) -> NormalizedQuery:
        country = country_hint or infer_country(raw_query)
        cleaned_query = " ".join(raw_query.split())
        without_country = strip_country_phrase(cleaned_query, country).strip(" ,;-")
        product_name, generic_name, aliases, indication = infer_product_and_indication(
            without_country
        )
        search_terms = unique_strings([product_name, generic_name, indication, *aliases])
        notes = ["Used heuristic query normalization fallback."]
        if country_hint and country_hint != country:
            notes.append(f"Country overridden by explicit input: {country_hint}")
            country = country_hint
        return NormalizedQuery(
            raw_query=raw_query,
            product_name=product_name or without_country or cleaned_query,
            country=country,
            indication=indication,
            generic_name=generic_name,
            aliases=aliases,
            search_terms=search_terms,
            confidence="medium" if country else "low",
            notes=notes,
        )


class OpenAIQueryNormalizer:
    def __init__(self, *, model: str = "gpt-4.1-mini") -> None:
        from openai import OpenAI

        key = get_openai_api_key()
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=key)
        self.model = model

    def normalize(
        self, raw_query: str, *, country_hint: str | None = None
    ) -> NormalizedQuery:
        countries = supported_countries()
        prompt = f"""
You normalize an HTA retrieval query into a strict JSON object.

Supported countries: {countries}
Country hint: {country_hint or "none"}

Return JSON with exactly these keys:
- product_name
- generic_name
- indication
- country
- aliases
- search_terms
- confidence
- notes

Rules:
- Extract the drug/product actually being asked for.
- Expand abbreviations when clear, especially oncology indications.
- Country must be one of the supported countries or null.
- Respect the country hint when provided.
- aliases should include brand and generic forms when known from the query.
- search_terms should be a concise search list for retrieval, not a long explanation.
- If uncertain, keep the product_name close to the user's wording and set confidence to low or medium.
- Return valid JSON only.

User query: {raw_query}
""".strip()
        response = self.client.responses.create(
            model=self.model,
            input=prompt,
            text={"format": {"type": "json_object"}},
        )
        payload = json.loads(response.output_text)
        country = country_hint or normalize_country_name(payload.get("country"))
        notes = list(payload.get("notes") or [])
        if country_hint and payload.get("country") and country_hint != payload.get("country"):
            notes.append(f"Country overridden by explicit input: {country_hint}")
        product_name = (payload.get("product_name") or raw_query).strip()
        generic_name = normalize_optional_text(payload.get("generic_name"))
        indication = normalize_optional_text(payload.get("indication"))
        aliases = unique_strings(payload.get("aliases") or [])
        search_terms = unique_strings(
            payload.get("search_terms")
            or [product_name, generic_name, indication, *aliases]
        )
        return NormalizedQuery(
            raw_query=raw_query,
            product_name=product_name,
            country=country,
            generic_name=generic_name,
            indication=indication,
            aliases=aliases,
            search_terms=search_terms,
            confidence=(payload.get("confidence") or "medium"),
            notes=notes,
        )


def infer_country(raw_query: str) -> str | None:
    normalized = normalize_country_name(raw_query)
    if normalized:
        return normalized
    lowered = raw_query.lower()
    for alias, country in COUNTRY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return country
    return None


def normalize_country_name(value: str | None) -> str | None:
    if not value:
        return None
    lowered = " ".join(value.lower().split())
    for alias, country in COUNTRY_ALIASES.items():
        if lowered == alias:
            return country
    for country in supported_countries():
        if lowered == country.lower():
            return country
    return None


def strip_country_phrase(raw_query: str, country: str | None) -> str:
    if not country:
        return raw_query
    aliases = [country.lower()] + [
        alias for alias, mapped_country in COUNTRY_ALIASES.items() if mapped_country == country
    ]
    cleaned = raw_query
    for alias in aliases:
        cleaned = re.sub(rf"\b{re.escape(alias)}\b", "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def infer_product_and_indication(
    query_without_country: str,
) -> tuple[str, str | None, list[str], str | None]:
    normalized_query = " ".join(query_without_country.split())
    lowered_query = normalized_query.lower()
    alias_map = load_product_aliases()

    best_match: tuple[str, str, list[str]] | None = None
    for canonical_name, alias_values in alias_map.items():
        values = unique_strings([canonical_name, *alias_values])
        for value in sorted(values, key=len, reverse=True):
            pattern = rf"\b{re.escape(value.lower())}\b"
            if re.search(pattern, lowered_query):
                best_match = (canonical_name, value, values)
                break
        if best_match:
            break

    if best_match:
        canonical_name, matched_alias, aliases = best_match
        generic_name = next(
            (alias for alias in aliases if alias.lower() != canonical_name.lower()),
            None,
        )
        remainder = re.sub(
            rf"\b{re.escape(matched_alias)}\b",
            "",
            normalized_query,
            count=1,
            flags=re.IGNORECASE,
        )
        indication = clean_indication_text(remainder)
        return canonical_name.title() if canonical_name.islower() else canonical_name, generic_name, aliases, indication

    parts = re.split(
        r"\b(?:for|with)\b",
        normalized_query,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(parts) == 2:
        return parts[0].strip(" ,;-"), None, [], clean_indication_text(parts[1])

    tokens = normalized_query.split()
    if len(tokens) > 1:
        return tokens[0], None, [], clean_indication_text(" ".join(tokens[1:]))
    return normalized_query, None, [], None


def clean_indication_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(
        r"^\b(?:for|with|in|first line|second line|third line|1l|2l|3l)\b",
        "",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(?:in)\b\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:first[-\s]*line|second[-\s]*line|third[-\s]*line|1l|2l|3l)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;-")
    return cleaned or None


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def unique_strings(values: list[str | None]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = normalize_optional_text(value)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def normalized_query_to_dict(normalized: NormalizedQuery) -> dict[str, object]:
    return asdict(normalized)
