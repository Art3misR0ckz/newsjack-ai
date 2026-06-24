"""YouTube trend/search collection with safe empty-state fallback."""

from __future__ import annotations

import logging
from typing import Any, Mapping

from googleapiclient.discovery import build

from app.config import settings
from app.services.cache_service import cached_call
from app.services.query_generation_service import generate_brand_queries

logger = logging.getLogger(__name__)


def collect_youtube_signals(brand_profile: Mapping[str, Any], limit: int = 12) -> list[dict[str, Any]]:
    """Collect YouTube search signals for brand-expanded queries."""

    queries = generate_brand_queries(brand_profile, limit=6)
    if not settings.youtube_api_key or not queries:
        return []

    def produce() -> list[dict[str, Any]]:
        try:
            youtube = build("youtube", "v3", developerKey=settings.youtube_api_key, cache_discovery=False)
            videos: list[dict[str, Any]] = []
            for query in queries:
                videos.extend(_search_videos(youtube, query, max_results=max(1, limit // max(1, len(queries)))))
            return _dedupe(videos)[:limit]
        except Exception:
            logger.warning("YouTube signal collection failed")
            return []

    cache_key = "youtube:" + "|".join(query.casefold() for query in queries)
    return cached_call("youtube", cache_key, produce, ttl_seconds=settings.youtube_cache_ttl_seconds)


def youtube_buzz_score(videos: list[dict[str, Any]]) -> int:
    if not videos:
        return 0
    view_score = min(100, sum(int(video.get("views", 0)) for video in videos) // 5000)
    engagement = min(100, sum(int(video.get("likes", 0)) for video in videos) // 500)
    volume = min(100, len(videos) * 12)
    return round(view_score * 0.45 + engagement * 0.25 + volume * 0.30)


def _search_videos(youtube: Any, query: str, max_results: int) -> list[dict[str, Any]]:
    search_response = (
        youtube.search()
        .list(part="snippet", q=query, type="video", order="relevance", maxResults=min(10, max_results))
        .execute()
    )
    ids = [item["id"]["videoId"] for item in search_response.get("items", []) if item.get("id", {}).get("videoId")]
    stats: dict[str, dict[str, int]] = {}
    if ids:
        detail_response = youtube.videos().list(part="statistics,snippet", id=",".join(ids)).execute()
        for item in detail_response.get("items", []):
            stat = item.get("statistics", {})
            stats[item["id"]] = {
                "views": _safe_int(stat.get("viewCount")),
                "likes": _safe_int(stat.get("likeCount")),
            }

    videos: list[dict[str, Any]] = []
    for item in search_response.get("items", []):
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        stat = stats.get(video_id, {})
        videos.append(
            {
                "title": snippet.get("title", ""),
                "channel": snippet.get("channelTitle", ""),
                "views": stat.get("views", 0),
                "likes": stat.get("likes", 0),
                "publishedAt": snippet.get("publishedAt"),
                "category": "youtube",
                "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
                "query": query,
                "source": "YouTube",
                "source_type": "youtube",
            }
        )
    return [video for video in videos if video["title"]]


def _dedupe(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for video in sorted(videos, key=lambda item: int(item.get("views", 0)), reverse=True):
        key = (video.get("url") or video.get("title") or "").casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(video)
    return result


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
