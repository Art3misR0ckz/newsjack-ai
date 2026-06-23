"""End-to-end orchestration for discovery, enrichment, ranking, and generation."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping

from app.config import settings
from app.models import Opportunity
from app.services.cache_service import cached_call
from app.services.content_generation_service import generate_content
from app.services.opportunity_generator_service import generate_campaign
from app.services.opportunity_intelligence_service import calculate_opportunity, rank_intelligent_opportunities
from app.services.trend_discovery_service import discover_trends
from app.services.trend_news_service import get_news_for_trend

logger = logging.getLogger(__name__)


def discover_and_rank(
    brand_profile: Mapping[str, Any],
    *,
    limit: int | None = None,
    generate_assets: bool = False,
) -> list[dict[str, Any]]:
    count = limit or settings.max_trends
    trends = discover_trends(count)
    opportunities: list[dict[str, Any]] = []

    def enrich(trend: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, Any]]:
        topic = str(trend.get("topic", ""))
        enrichment = cached_call("enrichment", topic.lower(), lambda topic=topic: get_news_for_trend(topic))
        return trend, enrichment

    with ThreadPoolExecutor(max_workers=min(6, len(trends) or 1)) as executor:
        enriched_trends = list(executor.map(enrich, trends))

    for trend, enrichment in enriched_trends:
        topic = str(trend.get("topic", ""))
        opportunity = calculate_opportunity(trend, enrichment, brand_profile)
        opportunity["articles"] = [_normalize_article(article) for article in opportunity.get("articles", [])]
        if generate_assets:
            opportunity = add_campaign_assets(brand_profile, opportunity)
        opportunities.append(Opportunity.model_validate(opportunity).model_dump(mode="json"))
        logger.info(
            "Opportunity scored",
            extra={"event": "opportunity_scored", "topic": topic, "score": opportunity["final_score"]},
        )
    return rank_intelligent_opportunities(opportunities)


def add_campaign_assets(
    brand_profile: Mapping[str, Any], opportunity: Mapping[str, Any]
) -> dict[str, Any]:
    enriched = dict(opportunity)
    campaign = generate_campaign(brand_profile, enriched)
    content = generate_content(brand_profile, enriched, campaign)
    enriched.update({"campaign": campaign, "content": content})
    return enriched


def _normalize_article(article: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "headline": article.get("headline") or article.get("title") or "Untitled",
        "description": article.get("description", ""),
        "source": article.get("source", "Unknown"),
        "published_date": article.get("published_date") or article.get("date"),
        "url": article.get("url", ""),
        "relevance_score": article.get("relevance_score", 0),
        "importance_score": article.get("importance_score", 0),
        "recency_score": article.get("recency_score", 0),
        "credibility_score": article.get("credibility_score", article.get("importance_score", 0)),
    }
