"""Discover and normalize current search trends."""

from __future__ import annotations

import logging
from typing import Any

from serpapi import GoogleSearch

from app.config import settings
from app.services.cache_service import cached_call
from app.services.trend_news_service import infer_category

logger = logging.getLogger(__name__)


def get_google_trends() -> list[dict[str, Any]]:
    if not settings.serpapi_key:
        return []

    search = GoogleSearch(
        {
            "engine": "google_trends_trending_now",
            "geo": settings.trend_geo,
            "api_key": settings.serpapi_key,
        }
    )
    results = search.get_dict()
    if results.get("error"):
        raise RuntimeError(str(results["error"]))

    trends: list[dict[str, Any]] = []
    for item in results.get("trending_searches", []):
        topic = str(item.get("query") or "").strip()
        if not topic:
            continue
        categories = item.get("categories") or []
        category = categories[0].get("name") if categories else infer_category(topic)
        trends.append(
            {
                "topic": topic,
                "search_volume": item.get("search_volume", 0),
                "increase_percentage": item.get("increase_percentage", 0),
                "category": category or infer_category(topic),
            }
        )
    return trends


def discover_trends(limit: int = 12) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 50))

    def produce() -> list[dict[str, Any]]:
        discovered: list[dict[str, Any]] = []
        try:
            for item in get_google_trends():
                topic = str(item.get("topic") or "").strip()
                if len(topic) < 3:
                    continue
                increase = _safe_number(item.get("increase_percentage"))
                volume = _safe_number(item.get("search_volume"))
                discovered.append(
                    {
                        "topic": topic,
                        "category": str(item.get("category") or infer_category(topic)).lower(),
                        "source": "google_trends",
                        "search_volume": volume,
                        "increase_percentage": increase,
                        "trend_strength": min(100, 45 + increase // 2 + volume // 5000),
                    }
                )
        except Exception:
            logger.warning("Live trend discovery failed; using curated fallback")

        if not discovered:
            discovered = _fallback_trends()

        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for trend in discovered:
            key = trend["topic"].casefold()
            if key not in seen:
                seen.add(key)
                unique.append(trend)
        return unique[:limit]

    return cached_call("serpapi", f"trends:{settings.trend_geo}:{limit}", produce)


def _fallback_trends() -> list[dict[str, Any]]:
    base = [
        ("AI product launches", "technology", 82),
        ("Creator economy growth", "business", 72),
        ("Sustainable packaging", "climate", 70),
        ("Fitness and recovery", "health", 68),
        ("Major sporting events", "sports", 66),
        ("Short-form video trends", "entertainment", 64),
    ]
    return [
        {
            "topic": topic,
            "category": category,
            "source": "curated_fallback",
            "search_volume": 0,
            "increase_percentage": 0,
            "trend_strength": score,
        }
        for topic, category, score in base
    ]


def _safe_number(value: Any) -> int:
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("+", "")
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
