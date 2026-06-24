"""Monitor recent competitor mentions through NewsAPI with safe fallbacks."""

from __future__ import annotations

import logging
from typing import Any, Iterable

import requests

from app.config import settings
from app.services.cache_service import cached_call

logger = logging.getLogger(__name__)


def monitor_competitors(competitors: Iterable[str], limit_per_competitor: int = 5) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for competitor in [item.strip() for item in competitors if item and item.strip()]:
        results.extend(_mentions(competitor, limit_per_competitor))
    return sorted(results, key=lambda item: (item.get("impact_score", 0), item.get("date") or ""), reverse=True)


def _mentions(competitor: str, limit: int) -> list[dict[str, Any]]:
    def produce() -> list[dict[str, Any]]:
        if settings.gnews_api_key:
            gnews = _gnews_mentions(competitor, limit)
            if gnews:
                return gnews
        if not settings.newsapi_key:
            return []
        try:
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": f'"{competitor}"',
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": limit,
                    "apiKey": settings.newsapi_key,
                },
                timeout=settings.request_timeout_seconds,
            )
            response.raise_for_status()
            return [_normalize_mention(competitor, article) for article in response.json().get("articles", []) if article.get("title")]
        except Exception:
            logger.warning("Competitor monitoring failed for %s", competitor)
            return []

    return cached_call("competitors", f"competitor:{competitor}:{limit}", produce, ttl_seconds=settings.competitor_cache_ttl_seconds)


def _gnews_mentions(competitor: str, limit: int) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            "https://gnews.io/api/v4/search",
            params={
                "q": f'"{competitor}" (launch OR partnership OR acquisition OR funding OR feature OR announcement)',
                "lang": "en",
                "country": settings.news_country.lower(),
                "max": min(10, limit),
                "sortby": "publishedAt",
                "apikey": settings.gnews_api_key,
            },
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
        return [_normalize_mention(competitor, article) for article in response.json().get("articles", []) if article.get("title")]
    except Exception:
        logger.warning("GNews competitor monitoring failed for %s", competitor)
        return []


def _normalize_mention(competitor: str, article: dict[str, Any]) -> dict[str, Any]:
    headline = article.get("title", "")
    description = article.get("description") or article.get("content") or ""
    source = article.get("source")
    if isinstance(source, dict):
        source = source.get("name", "Unknown")
    announcement_type = _announcement_type(f"{headline} {description}")
    return {
        "competitor": competitor,
        "headline": headline,
        "source": source or "Unknown",
        "date": article.get("publishedAt"),
        "url": article.get("url", ""),
        "description": description,
        "announcement_type": announcement_type,
        "impact_score": _impact_score(f"{headline} {description}", announcement_type),
    }


def _announcement_type(text: str) -> str:
    lowered = text.lower()
    for label, markers in {
        "Product launch": ["launch", "released", "new product", "feature"],
        "Partnership": ["partner", "partnership", "collaboration"],
        "Acquisition": ["acquire", "acquisition", "merger"],
        "Funding": ["funding", "raises", "investment", "valuation"],
        "Executive announcement": ["ceo", "chief", "executive", "appoints"],
    }.items():
        if any(marker in lowered for marker in markers):
            return label
    return "Media mention"


def _impact_score(text: str, announcement_type: str) -> int:
    base = {
        "Product launch": 82,
        "Partnership": 76,
        "Acquisition": 88,
        "Funding": 80,
        "Executive announcement": 64,
        "Media mention": 45,
    }.get(announcement_type, 45)
    lowered = text.lower()
    if any(marker in lowered for marker in ["major", "global", "breakthrough", "first", "exclusive"]):
        base += 10
    return max(0, min(100, base))
