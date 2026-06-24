"""Brand-driven query expansion shared by discovery providers."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from app.config import settings


INDUSTRY_EXPANSIONS: dict[str, list[str]] = {
    "ai": ["artificial intelligence", "AI agents", "generative AI", "LLM", "agentic AI"],
    "artificial intelligence": ["AI agents", "generative AI", "LLM", "foundation models"],
    "fitness": ["fitness", "workout", "training", "wellness", "sports nutrition"],
    "nutrition": ["protein", "recovery", "supplements", "healthy lifestyle"],
    "sports": ["athletes", "sports marketing", "tournament", "marathon"],
    "marketing": ["brand campaign", "creator marketing", "social media trends"],
    "technology": ["product launch", "software", "startup", "innovation"],
}

COMPETITOR_ALIASES: dict[str, list[str]] = {
    "anthropic": ["Claude"],
    "google": ["Gemini", "Google AI"],
    "openai": ["ChatGPT", "GPT-5", "GPT"],
    "nike": ["running", "athletes", "sportswear"],
    "adidas": ["sportswear", "football boots"],
    "perplexity": ["AI search"],
}


def generate_brand_queries(brand_profile: Mapping[str, Any], *, limit: int | None = None) -> list[str]:
    """Generate deduplicated search terms from the active brand profile."""

    max_terms = limit or settings.max_brand_queries
    terms: list[str] = []
    brand_name = _clean(brand_profile.get("brand_name") or brand_profile.get("name"))
    industry = _clean(brand_profile.get("industry"))

    _extend(terms, [brand_name])
    _extend(terms, _as_list(brand_profile.get("products")))
    _extend(terms, _as_list(brand_profile.get("keywords")))
    _extend(terms, _industry_terms(industry))
    _extend(terms, _audience_terms(brand_profile.get("target_audience") or brand_profile.get("audience")))

    competitors = _as_list(brand_profile.get("competitors"))
    _extend(terms, competitors)
    for competitor in competitors:
        _extend(terms, COMPETITOR_ALIASES.get(competitor.casefold(), []))

    if brand_name and industry:
        _extend(terms, [f"{brand_name} {industry}", f"{industry} trends"])

    return _dedupe(terms)[:max_terms]


def searchable_brand_text(brand_profile: Mapping[str, Any]) -> str:
    fields = [
        brand_profile.get("brand_name") or brand_profile.get("name"),
        brand_profile.get("industry"),
        brand_profile.get("target_audience") or brand_profile.get("audience"),
        brand_profile.get("tone"),
        brand_profile.get("goals"),
        brand_profile.get("brand_summary") or brand_profile.get("summary"),
        *_as_list(brand_profile.get("keywords")),
        *_as_list(brand_profile.get("products")),
        *_as_list(brand_profile.get("competitors")),
        *generate_brand_queries(brand_profile),
    ]
    return " ".join(_clean(item) for item in fields if _clean(item))


def _industry_terms(industry: str) -> list[str]:
    normalized = industry.casefold()
    terms: list[str] = [industry] if industry else []
    for key, expansions in INDUSTRY_EXPANSIONS.items():
        if key in normalized:
            terms.extend(expansions)
    return terms


def _audience_terms(value: Any) -> list[str]:
    text = _clean(value)
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", text)
    stop = {"and", "the", "for", "with", "who", "people", "consumers", "professionals"}
    return [token for token in tokens if token.casefold() not in stop][:5]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, Iterable):
        return [_clean(item) for item in value if _clean(item)]
    return [_clean(value)] if _clean(value) else []


def _extend(target: list[str], values: Iterable[str]) -> None:
    for value in values:
        cleaned = _clean(value)
        if cleaned:
            target.append(cleaned)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = re.sub(r"\s+", " ", value).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()
