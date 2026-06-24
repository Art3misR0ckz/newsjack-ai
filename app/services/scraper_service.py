"""Graceful web scraping for marketing and technology source pages."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.services.cache_service import cached_call

logger = logging.getLogger(__name__)

SCRAPE_SOURCES: tuple[dict[str, str], ...] = (
    {"name": "OpenAI Blog", "url": "https://openai.com/blog", "category": "technology"},
    {"name": "Google Blog", "url": "https://blog.google", "category": "technology"},
    {"name": "NVIDIA Blog", "url": "https://blogs.nvidia.com", "category": "technology"},
    {"name": "HubSpot Blog", "url": "https://blog.hubspot.com", "category": "marketing"},
    {"name": "Marketing Brew", "url": "https://www.marketingbrew.com", "category": "marketing"},
    {"name": "TechCrunch", "url": "https://techcrunch.com", "category": "technology"},
    {"name": "Product Hunt", "url": "https://www.producthunt.com", "category": "product"},
)


def scrape_industry_sources(limit_per_source: int | None = None) -> list[dict[str, Any]]:
    """Scrape configured source landing pages; one failed site never fails the dashboard."""

    limit = limit_per_source or settings.max_scraped_items_per_source

    def produce() -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for source in SCRAPE_SOURCES:
            items.extend(_scrape_source(source, limit))
        return items

    return cached_call("scrapers", "industry_sources", produce, ttl_seconds=settings.scraper_cache_ttl_seconds)


def _scrape_source(source: dict[str, str], limit: int) -> list[dict[str, Any]]:
    try:
        response = requests.get(
            source["url"],
            headers={"User-Agent": "NEWSJACK-AI/2.0 (+https://newsjack.ai)"},
            timeout=settings.request_timeout_seconds,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return _extract_items(soup, source, limit)
    except Exception:
        logger.warning("Scraper source failed: %s", source["name"])
        return []


def _extract_items(soup: BeautifulSoup, source: dict[str, str], limit: int) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for element in soup.select("article, main a, h2 a, h3 a, a"):
        link = element if element.name == "a" else element.select_one("a")
        if not link:
            continue
        title = _clean(link.get_text(" ", strip=True))
        href = link.get("href") or ""
        if len(title) < 12 or not href:
            continue
        url = urljoin(source["url"], href)
        if not url.startswith("http"):
            continue
        summary = _nearby_summary(element)
        candidates.append(
            {
                "title": title,
                "headline": title,
                "summary": summary,
                "description": summary,
                "source": source["name"],
                "published_date": _extract_datetime(element),
                "url": url,
                "category": source["category"],
                "source_type": "scraper",
            }
        )
        if len(candidates) >= limit * 3:
            break
    return _dedupe(candidates)[:limit]


def _nearby_summary(element: Any) -> str:
    container = element if getattr(element, "name", "") == "article" else element.parent
    if not container:
        return ""
    paragraph = container.select_one("p")
    return _clean(paragraph.get_text(" ", strip=True))[:500] if paragraph else ""


def _extract_datetime(element: Any) -> str:
    container = element if getattr(element, "name", "") == "article" else element.parent
    if container:
        time_node = container.select_one("time")
        if time_node:
            return _clean(time_node.get("datetime") or time_node.get_text(" ", strip=True))
    return datetime.now(timezone.utc).isoformat()


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for item in items:
        key = (item.get("url") or item.get("title") or "").casefold().rstrip("/")
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())
