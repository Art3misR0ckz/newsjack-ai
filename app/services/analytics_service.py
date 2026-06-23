"""Aggregate opportunity data for Plotly and API consumers."""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any, Iterable, Mapping


def build_analytics(opportunities: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    items = list(opportunities)
    categories = Counter(str(item.get("category", "general")).title() for item in items)
    score_bands = Counter(_band(int(item.get("final_score", 0))) for item in items)
    scores = [int(item.get("final_score", 0)) for item in items]
    return {
        "total_opportunities": len(items),
        "average_score": round(mean(scores), 1) if scores else 0,
        "top_categories": [{"category": key, "count": value} for key, value in categories.most_common()],
        "opportunity_distribution": [
            {"band": band, "count": score_bands.get(band, 0)}
            for band in ("0-39", "40-59", "60-79", "80-100")
        ],
        "trend_volume": [
            {"topic": item.get("topic", ""), "news_volume": item.get("news_volume", 0)}
            for item in items[:10]
        ],
        "score_breakdown": [
            {
                "topic": item.get("topic", ""),
                "final_score": item.get("final_score", 0),
                "brand_relevance": item.get("brand_relevance", 0),
                "newsjack_potential": item.get("newsjack_potential", 0),
            }
            for item in items
        ],
    }


def _band(score: int) -> str:
    if score < 40:
        return "0-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"
