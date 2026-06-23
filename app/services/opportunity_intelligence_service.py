"""Calculate transparent, explainable opportunity scores."""

from __future__ import annotations

from typing import Any, Mapping

from app.services.brand_relevance_service import score_brand_relevance


def calculate_opportunity(
    trend: Mapping[str, Any],
    enrichment: Mapping[str, Any],
    brand_profile: Mapping[str, Any],
) -> dict[str, Any]:
    articles = list(enrichment.get("articles", []))
    sources = {str(article.get("source", "")).lower() for article in articles if article.get("source")}
    relevance = score_brand_relevance(
        brand_profile,
        {**dict(trend), "summary": enrichment.get("summary", ""), "newsjack_score": enrichment.get("newsjack_score", 0)},
    )
    trend_strength = _score(
        trend.get("trend_strength")
        or min(100, 35 + int(trend.get("increase_percentage", 0)) // 2 + int(trend.get("search_volume", 0)) // 5000)
    )
    news_volume_score = min(100, len(articles) * 12)
    diversity_score = min(100, len(sources) * 20)
    final_score = round(
        trend_strength * 0.20
        + news_volume_score * 0.10
        + diversity_score * 0.10
        + relevance["relevance_score"] * 0.25
        + relevance["audience_overlap"] * 0.15
        + relevance["newsjack_potential"] * 0.20
    )
    return {
        "topic": trend.get("topic", ""),
        "category": trend.get("category", "general"),
        "source": trend.get("source", "unknown"),
        "summary": enrichment.get("summary", ""),
        "articles": articles,
        "trend_strength": trend_strength,
        "news_volume": len(articles),
        "source_diversity": len(sources),
        "brand_relevance": relevance["relevance_score"],
        "relevance_score": relevance["relevance_score"],
        "audience_overlap": relevance["audience_overlap"],
        "newsjack_potential": relevance["newsjack_potential"],
        "final_score": _score(final_score),
        "reason": relevance["reason"],
        "recommended_angle": relevance["recommended_angle"],
    }


def rank_intelligent_opportunities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("final_score", 0), reverse=True)


def _score(value: Any) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0
