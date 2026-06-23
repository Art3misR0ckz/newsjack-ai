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
    return sorted(results, key=lambda item: item.get("date") or "", reverse=True)


def _mentions(competitor: str, limit: int) -> list[dict[str, Any]]:
    def produce() -> list[dict[str, Any]]:
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
            return [
                {
                    "competitor": competitor,
                    "headline": article.get("title", ""),
                    "source": (article.get("source") or {}).get("name", "Unknown"),
                    "date": article.get("publishedAt"),
                    "url": article.get("url", ""),
                    "description": article.get("description", ""),
                }
                for article in response.json().get("articles", [])
                if article.get("title")
            ]
        except Exception:
            logger.warning("Competitor monitoring failed for %s", competitor)
            return []

    return cached_call("newsapi", f"competitor:{competitor}:{limit}", produce)
