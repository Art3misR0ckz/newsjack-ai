"""NEWSJACK AI v2.0 opportunity scoring formula."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from dateutil import parser as date_parser


def calculate_v2_opportunity_score(
    *,
    relevance_score: int,
    trend_score: int,
    articles: list[Mapping[str, Any]],
    competitor_signals: list[Mapping[str, Any]],
    youtube_buzz_score: int,
) -> dict[str, int]:
    """Return v2 score components and final 0-100 opportunity score."""

    freshness_score = _freshness_score(articles)
    competitor_activity_score = (
        min(100, len(competitor_signals) * 18 + _max_signal_score(competitor_signals))
        if competitor_signals
        else 50
    )
    normalized_youtube_buzz = _score(youtube_buzz_score) if youtube_buzz_score else 50
    content_volume_score = min(100, len(articles) * 8 + len(competitor_signals) * 6)
    opportunity_score = round(
        _score(relevance_score) * 0.40
        + _score(trend_score) * 0.20
        + freshness_score * 0.15
        + competitor_activity_score * 0.10
        + normalized_youtube_buzz * 0.10
        + content_volume_score * 0.05
    )
    return {
        "opportunity_score": _score(opportunity_score),
        "final_score": _score(opportunity_score),
        "relevance_score": _score(relevance_score),
        "trend_score": _score(trend_score),
        "freshness_score": freshness_score,
        "competitor_activity_score": competitor_activity_score,
        "youtube_buzz_score": normalized_youtube_buzz,
        "content_volume_score": content_volume_score,
    }


def _freshness_score(articles: list[Mapping[str, Any]]) -> int:
    if not articles:
        return 0
    scores = [_single_freshness(article.get("published_date") or article.get("publishedAt")) for article in articles]
    return round(sum(scores) / len(scores))


def _single_freshness(value: Any) -> int:
    parsed = _parse_date(value)
    if not parsed:
        return 40
    age_hours = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600)
    if age_hours <= 12:
        return 100
    if age_hours <= 24:
        return 90
    if age_hours <= 48:
        return 78
    if age_hours <= 96:
        return 62
    if age_hours <= 168:
        return 45
    return 25


def _parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_parser.parse(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _max_signal_score(signals: list[Mapping[str, Any]]) -> int:
    scores = [_score(signal.get("impact_score", 0)) for signal in signals]
    return max(scores, default=0) // 2


def _score(value: Any) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0
