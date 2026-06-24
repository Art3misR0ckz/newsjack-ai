"""End-to-end orchestration for discovery, enrichment, ranking, and generation."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Mapping

from app.config import settings
from app.models import Opportunity
from app.services.cache_service import cached_call
from app.services.brand_relevance_service import score_brand_relevance
from app.services.competitor_monitor_service import monitor_competitors
from app.services.content_generation_service import generate_content
from app.services.opportunity_generator_service import generate_campaign
from app.services.opportunity_intelligence_service import calculate_opportunity, rank_intelligent_opportunities
from app.services.query_generation_service import generate_brand_queries
from app.services.scraper_service import scrape_industry_sources
from app.services.trend_discovery_service import discover_trends
from app.services.trend_news_service import deduplicate_articles, get_brand_news_pool, get_news_for_trend, infer_category
from app.services.youtube_service import collect_youtube_signals, youtube_buzz_score

logger = logging.getLogger(__name__)


def discover_and_rank(
    brand_profile: Mapping[str, Any],
    *,
    limit: int | None = None,
    generate_assets: bool = False,
) -> list[dict[str, Any]]:
    count = limit or settings.max_trends
    brand_queries = generate_brand_queries(brand_profile)
    trends = _brand_centered_trends(brand_profile, count)
    brand_news = get_brand_news_pool(brand_profile)
    scraped_items = scrape_industry_sources()
    youtube_signals = collect_youtube_signals(brand_profile)
    competitor_signals = monitor_competitors(brand_profile.get("competitors", []), limit_per_competitor=4)
    youtube_score = youtube_buzz_score(youtube_signals)
    opportunities: list[dict[str, Any]] = []

    def enrich(trend: Mapping[str, Any]) -> tuple[Mapping[str, Any], dict[str, Any]]:
        topic = str(trend.get("topic", ""))
        enrichment = cached_call("enrichment", topic.lower(), lambda topic=topic: get_news_for_trend(topic))
        enrichment["articles"] = _merge_brand_articles(topic, brand_profile, enrichment.get("articles", []), brand_news, scraped_items)
        enrichment["top_articles"] = enrichment["articles"][:5]
        enrichment["article_count"] = len(enrichment["articles"])
        if not enrichment.get("summary") or "Limited recent news" in enrichment.get("summary", ""):
            enrichment["summary"] = _summary_from_articles(topic, enrichment["articles"])
        return trend, enrichment

    with ThreadPoolExecutor(max_workers=min(6, len(trends) or 1)) as executor:
        enriched_trends = list(executor.map(enrich, trends))

    for trend, enrichment in enriched_trends:
        topic = str(trend.get("topic", ""))
        opportunity = calculate_opportunity(
            trend,
            enrichment,
            brand_profile,
            competitor_signals=competitor_signals,
            youtube_signals=youtube_signals,
            youtube_buzz_score=youtube_score,
        )
        opportunity["articles"] = [_normalize_article(article) for article in opportunity.get("articles", [])]
        if opportunity["brand_relevance"] < 35 and not _mentions_brand_query(opportunity, brand_queries):
            continue
        if generate_assets or opportunity["final_score"] >= 70:
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
        "content": article.get("content", ""),
        "source": article.get("source", "Unknown"),
        "published_date": article.get("published_date") or article.get("date"),
        "image": article.get("image", ""),
        "url": article.get("url", ""),
        "relevance_score": article.get("relevance_score", 0),
        "importance_score": article.get("importance_score", 0),
        "recency_score": article.get("recency_score", 0),
        "credibility_score": article.get("credibility_score", article.get("importance_score", 0)),
    }


def _brand_centered_trends(brand_profile: Mapping[str, Any], count: int) -> list[dict[str, Any]]:
    trends = discover_trends(max(count, settings.max_trends))
    brand_queries = generate_brand_queries(brand_profile)
    brand_candidates: list[dict[str, Any]] = []
    for query in brand_queries:
        brand_candidates.append(
            {
                "topic": query,
                "title": query,
                "category": infer_category(query),
                "source": "brand_query",
                "search_volume": 0,
                "growth_rate": 0,
                "increase_percentage": 0,
                "trend_strength": 76,
                "trend_score": 76,
            }
        )
    scored_live: list[tuple[int, dict[str, Any]]] = []
    seen: set[str] = set()
    ordered: list[dict[str, Any]] = []
    for trend in brand_candidates:
        key = str(trend.get("topic", "")).casefold()
        if key and key not in seen:
            seen.add(key)
            ordered.append(trend)
    for trend in trends:
        topic = str(trend.get("topic", "")).strip()
        if not topic or topic.casefold() in seen:
            continue
        relevance = score_brand_relevance(brand_profile, trend)["relevance_score"]
        if relevance < 55 or _looks_like_generic_fixture(topic):
            continue
        momentum = int(trend.get("trend_score") or trend.get("trend_strength") or 0)
        scored_live.append((round(relevance * 0.65 + momentum * 0.35), trend))
    ordered.extend(trend for _, trend in sorted(scored_live, key=lambda item: item[0], reverse=True))
    return ordered[: max(count * 2, count)]


def _merge_brand_articles(
    topic: str,
    brand_profile: Mapping[str, Any],
    topic_articles: list[Mapping[str, Any]],
    brand_news: list[Mapping[str, Any]],
    scraped_items: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    merged = [dict(article) for article in topic_articles]
    for article in [*brand_news, *scraped_items]:
        payload = {**dict(article), "topic": topic}
        relevance = score_brand_relevance(brand_profile, payload)["relevance_score"]
        if relevance >= 45 or _topic_overlap(topic, article):
            enriched = dict(article)
            enriched["relevance_score"] = max(int(enriched.get("relevance_score", 0) or 0), relevance)
            enriched["importance_score"] = max(int(enriched.get("importance_score", 0) or 0), relevance)
            merged.append(enriched)
    return sorted(
        deduplicate_articles(merged),
        key=lambda item: (int(item.get("relevance_score", 0) or 0), str(item.get("published_date", ""))),
        reverse=True,
    )[:15]


def _topic_overlap(topic: str, article: Mapping[str, Any]) -> bool:
    tokens = {token for token in topic.casefold().split() if len(token) > 2}
    text = f"{article.get('title', '')} {article.get('headline', '')} {article.get('description', '')}".casefold()
    return bool(tokens and any(token in text for token in tokens))


def _summary_from_articles(topic: str, articles: list[Mapping[str, Any]]) -> str:
    if not articles:
        return f"No high-confidence brand-relevant coverage was found for {topic} yet."
    top = articles[0].get("headline") or articles[0].get("title") or topic
    return f"{topic} is showing brand-relevant momentum, led by: {top}"


def _mentions_brand_query(opportunity: Mapping[str, Any], queries: list[str]) -> bool:
    text = " ".join(
        [
            str(opportunity.get("topic", "")),
            str(opportunity.get("summary", "")),
            " ".join(str(article.get("headline", "")) for article in opportunity.get("articles", [])),
        ]
    ).casefold()
    return any(query.casefold() in text for query in queries if len(query) >= 3)


def _looks_like_generic_fixture(topic: str) -> bool:
    lowered = topic.casefold()
    return " vs " in lowered or "standings" in lowered or "national football team" in lowered
