"""Calculate transparent, explainable opportunity scores."""

from __future__ import annotations

from typing import Any, Mapping

from app.services.brand_relevance_service import score_brand_relevance
from app.services.opportunity_scoring_service import calculate_v2_opportunity_score


def calculate_opportunity(
    trend: Mapping[str, Any],
    enrichment: Mapping[str, Any],
    brand_profile: Mapping[str, Any],
    *,
    competitor_signals: list[Mapping[str, Any]] | None = None,
    youtube_signals: list[Mapping[str, Any]] | None = None,
    youtube_buzz_score: int = 0,
) -> dict[str, Any]:
    articles = list(enrichment.get("articles", []))
    sources = {str(article.get("source", "")).lower() for article in articles if article.get("source")}
    relevance = score_brand_relevance(
        brand_profile,
        {**dict(trend), "summary": enrichment.get("summary", ""), "newsjack_score": enrichment.get("newsjack_score", 0)},
    )
    trend_strength = _score(
        trend.get("trend_score")
        or
        trend.get("trend_strength")
        or min(100, 35 + int(trend.get("increase_percentage", 0)) // 2 + int(trend.get("search_volume", 0)) // 5000)
    )
    relevant_competitors = _matching_competitor_signals(
        trend.get("topic", ""), list(competitor_signals or []), brand_profile
    )
    relevant_youtube = _matching_youtube_signals(trend.get("topic", ""), list(youtube_signals or []))
    scores = calculate_v2_opportunity_score(
        relevance_score=relevance["relevance_score"],
        trend_score=trend_strength,
        articles=articles,
        competitor_signals=relevant_competitors,
        youtube_buzz_score=youtube_buzz_score if relevant_youtube else 0,
    )
    reason = _reason(relevance, enrichment, scores, relevant_competitors, relevant_youtube)
    return {
        "topic": trend.get("topic", ""),
        "category": trend.get("category", "general"),
        "source": trend.get("source", "unknown"),
        "summary": enrichment.get("summary", ""),
        "articles": articles,
        "latest_news": articles,
        "trend_strength": trend_strength,
        "trend_score": scores["trend_score"],
        "news_volume": len(articles),
        "source_diversity": len(sources),
        "brand_relevance": relevance["relevance_score"],
        "relevance_score": relevance["relevance_score"],
        "audience_overlap": relevance["audience_overlap"],
        "newsjack_potential": relevance["newsjack_potential"],
        "opportunity_score": scores["opportunity_score"],
        "final_score": scores["final_score"],
        "freshness_score": scores["freshness_score"],
        "competitor_activity_score": scores["competitor_activity_score"],
        "youtube_buzz_score": scores["youtube_buzz_score"],
        "content_volume_score": scores["content_volume_score"],
        "competitor_signals": relevant_competitors,
        "youtube_signals": relevant_youtube,
        "reason": reason,
        "recommended_angle": relevance["recommended_angle"],
    }


def rank_intelligent_opportunities(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: item.get("final_score", 0), reverse=True)


def _score(value: Any) -> int:
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


def _matching_competitor_signals(
    topic: Any, signals: list[Mapping[str, Any]], brand_profile: Mapping[str, Any]
) -> list[Mapping[str, Any]]:
    topic_text = str(topic).casefold()
    competitors = [str(item).casefold() for item in brand_profile.get("competitors", []) or []]
    matched: list[Mapping[str, Any]] = []
    for signal in signals:
        text = " ".join(str(signal.get(key, "")) for key in ("competitor", "headline", "description")).casefold()
        if any(competitor and competitor in text for competitor in competitors) or any(token in text for token in topic_text.split()):
            matched.append(signal)
    return matched[:5]


def _matching_youtube_signals(topic: Any, signals: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    tokens = {token for token in str(topic).casefold().split() if len(token) > 2}
    if not tokens:
        return []
    return [
        signal for signal in signals
        if tokens & {token for token in str(signal.get("title", "")).casefold().split() if len(token) > 2}
    ][:5]


def _reason(
    relevance: Mapping[str, Any],
    enrichment: Mapping[str, Any],
    scores: Mapping[str, int],
    competitor_signals: list[Mapping[str, Any]],
    youtube_signals: list[Mapping[str, Any]],
) -> str:
    parts = [str(relevance.get("reason", "Strong active-brand relevance."))]
    if enrichment.get("article_count"):
        parts.append(f"{enrichment['article_count']} relevant news items support the signal.")
    if competitor_signals:
        parts.append(f"{len(competitor_signals)} competitor developments increase urgency.")
    if youtube_signals:
        parts.append(f"{len(youtube_signals)} YouTube signals suggest creator/community buzz.")
    parts.append(f"Final score uses v2.0 weighted components; freshness is {scores['freshness_score']}/100.")
    return " ".join(parts)
