"""Trend news enrichment and scoring utilities.

This module turns a noisy trend topic into a ranked, filtered news package that
can be used by the opportunity pool and later newsjacking workflows.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

logger = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
SERPAPI_GEO = os.getenv("SERPAPI_GEO", "IN")
NEWSAPI_LANGUAGE = os.getenv("NEWSAPI_LANGUAGE", "en")
MAX_ARTICLE_AGE_DAYS = int(os.getenv("TREND_NEWS_MAX_AGE_DAYS", "7"))
MIN_TITLE_LENGTH = int(os.getenv("TREND_NEWS_MIN_TITLE_LENGTH", "15"))
MIN_RELEVANCE_SCORE = int(os.getenv("TREND_NEWS_MIN_RELEVANCE_SCORE", "50"))
MAX_ARTICLES_PER_TOPIC = int(os.getenv("TREND_NEWS_MAX_ARTICLES", "15"))
TOP_ARTICLES_LIMIT = int(os.getenv("TREND_NEWS_TOP_ARTICLES", "5"))

TRUSTED_SOURCES: Set[str] = {
    "reuters",
    "bbc",
    "ap",
    "associated press",
    "cnbc",
    "bloomberg",
    "techcrunch",
    "the verge",
    "economic times",
    "indian express",
    "the hindu",
    "fortune",
    "wire",
    "axios",
    "financial times",
    "wall street journal",
    "forbes",
    "abc news",
    "cnn",
    "usa today",
    "washington post",
}

SPAM_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(click here|subscribe now|buy now|free money|win a|cheap pills)\b", re.I),
    re.compile(r"\b(whatsapp|telegram)\b", re.I),
    re.compile(r"[!?]{3,}"),
)

CATEGORY_KEYWORDS: Dict[str, Set[str]] = {
    "technology": {
        "iphone",
        "apple",
        "android",
        "openai",
        "google",
        "microsoft",
        "ai",
        "chip",
        "software",
        "hardware",
    },
    "sports": {
        "vs",
        "world cup",
        "ipl",
        "match",
        "final",
        "cricket",
        "football",
        "soccer",
        "tennis",
        "nba",
        "fifa",
    },
    "entertainment": {
        "movie",
        "film",
        "series",
        "show",
        "trailer",
        "celebrity",
        "festival",
        "music",
    },
    "climate": {
        "weather",
        "storm",
        "rain",
        "heat",
        "cold",
        "hurricane",
        "monsoon",
        "climate",
    },
    "business": {
        "stock",
        "shares",
        "market",
        "earnings",
        "profit",
        "economy",
        "finance",
        "bank",
    },
    "health": {
        "health",
        "medical",
        "covid",
        "hospital",
        "vaccine",
        "wellness",
    },
}


@dataclass(frozen=True)
class ArticleSignal:
    title: str
    source: str
    published_date: Optional[str]
    description: str
    url: str
    relevance_score: int
    importance_score: int


def get_news_for_trend(topic: str) -> Dict[str, Any]:
    """Fetch, filter, score, and summarize news for a single trend topic."""

    normalized_topic = _normalize_text(topic)
    if not normalized_topic:
        logger.warning("Empty topic passed to get_news_for_trend")
        return _empty_result(topic)

    try:
        raw_articles = _fetch_articles_for_topic(topic)
        filtered_articles = _clean_and_score_articles(topic, raw_articles)
        filtered_articles.sort(
            key=lambda article: (
                article["importance_score"],
                article["relevance_score"],
                _recency_score(article.get("published_date")),
            ),
            reverse=True,
        )

        top_articles = filtered_articles[:TOP_ARTICLES_LIMIT]
        summary = generate_trend_summary(topic, filtered_articles)
        newsjack_score = calculate_newsjack_score(topic, filtered_articles)

        return {
            "topic": topic,
            "summary": summary,
            "newsjack_score": newsjack_score,
            "articles": filtered_articles,
            "top_articles": top_articles,
            "article_count": len(filtered_articles),
            "avg_relevance": _average_score(filtered_articles, "relevance_score"),
            "avg_importance": _average_score(filtered_articles, "importance_score"),
        }
    except Exception:
        logger.exception("Failed to enrich news for trend: %s", topic)
        return _empty_result(topic)


def get_trend_news() -> List[Dict[str, Any]]:
    """Compatibility wrapper used by the opportunity pool builder.

    It discovers live trends, enriches each one, and flattens the top articles so
    the existing opportunity pool can still consume a list of items.
    """

    trends = _fetch_live_trends()
    opportunities: List[Dict[str, Any]] = []

    for trend in trends:
        topic = trend.get("topic", "")
        category = trend.get("category", infer_category(topic))
        enriched = get_news_for_trend(topic)

        for article in enriched.get("top_articles", []):
            opportunities.append(
                {
                    "topic": topic,
                    "headline": article.get("title", ""),
                    "source": article.get("source", ""),
                    "url": article.get("url", ""),
                    "description": article.get("description", ""),
                    "published_date": article.get("published_date"),
                    "category": category,
                    "relevance_score": article.get("relevance_score", 0),
                    "importance_score": article.get("importance_score", 0),
                    "newsjack_score": enriched.get("newsjack_score", 0),
                    "source_type": "trend_news",
                }
            )

    return opportunities


def _fetch_articles_for_topic(topic: str) -> List[Dict[str, Any]]:
    articles: List[Dict[str, Any]] = []
    articles.extend(_fetch_serpapi_google_news(topic))
    articles.extend(_fetch_serpapi_trends_news(topic))
    articles.extend(_fetch_newsapi_articles(topic))

    logger.info("Fetched %s raw articles for topic '%s'", len(articles), topic)
    return articles


def _fetch_serpapi_google_news(topic: str) -> List[Dict[str, Any]]:
    if not SERPAPI_KEY:
        return []

    try:
        search = GoogleSearch(
            {
                "engine": "google_news",
                "q": topic,
                "hl": "en",
                "gl": SERPAPI_GEO,
                "api_key": SERPAPI_KEY,
            }
        )
        results = search.get_dict()
        return [_normalize_serpapi_article(article) for article in results.get("news_results", [])]
    except Exception:
        logger.exception("SerpAPI Google News fetch failed for topic '%s'", topic)
        return []


def _fetch_serpapi_trends_news(topic: str) -> List[Dict[str, Any]]:
    if not SERPAPI_KEY:
        return []

    try:
        trends_search = GoogleSearch(
            {
                "engine": "google_trends_trending_now",
                "geo": SERPAPI_GEO,
                "api_key": SERPAPI_KEY,
            }
        )
        trends_results = trends_search.get_dict()

        matched_token = None
        for trend in trends_results.get("trending_searches", []):
            query = trend.get("query", "")
            if _topics_match(topic, query):
                matched_token = trend.get("news_page_token")
                break

        if not matched_token:
            return []

        news_search = GoogleSearch(
            {
                "engine": "google_trends_news",
                "page_token": matched_token,
                "api_key": SERPAPI_KEY,
            }
        )
        news_results = news_search.get_dict()
        return [_normalize_serpapi_article(article) for article in news_results.get("news_results", [])]
    except Exception:
        logger.exception("SerpAPI Trends News fetch failed for topic '%s'", topic)
        return []


def _fetch_newsapi_articles(topic: str) -> List[Dict[str, Any]]:
    if not NEWS_API_KEY:
        return []

    try:
        response = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": topic,
                "language": NEWSAPI_LANGUAGE,
                "sortBy": "publishedAt",
                "pageSize": 10,
                "apiKey": NEWS_API_KEY,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        return [_normalize_newsapi_article(article) for article in payload.get("articles", [])]
    except Exception:
        logger.exception("NewsAPI fallback failed for topic '%s'", topic)
        return []


def _normalize_serpapi_article(article: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _first_non_empty(article, ["title", "headline", "story_title"]),
        "source": _extract_source_name(article),
        "published_date": _first_non_empty(article, ["date", "published_date", "publishedAt"]),
        "description": _first_non_empty(article, ["snippet", "description", "summary"]),
        "url": _first_non_empty(article, ["link", "url", "news_url"]),
    }


def _normalize_newsapi_article(article: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": _first_non_empty(article, ["title"]),
        "source": _extract_source_name(article),
        "published_date": _first_non_empty(article, ["publishedAt"]),
        "description": _first_non_empty(article, ["description", "content"]),
        "url": _first_non_empty(article, ["url"]),
    }


def _clean_and_score_articles(topic: str, raw_articles: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=MAX_ARTICLE_AGE_DAYS)

    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()
    scored_articles: List[Dict[str, Any]] = []

    for raw_article in raw_articles:
        title = _normalize_text(raw_article.get("title", ""))
        if not title or len(title) < MIN_TITLE_LENGTH:
            continue

        url = _normalize_url(raw_article.get("url", ""))
        if not url or url in seen_urls:
            continue

        title_key = _normalize_title_key(title)
        if title_key in seen_titles:
            continue

        published_date = _parse_datetime(raw_article.get("published_date"))
        if published_date and published_date < cutoff:
            continue

        if _is_spam(title, raw_article.get("description", "")):
            continue

        relevance_score = calculate_relevance_score(topic, raw_article)
        if relevance_score < MIN_RELEVANCE_SCORE:
            continue

        importance_score = calculate_importance_score(topic, raw_article, relevance_score)

        seen_urls.add(url)
        seen_titles.add(title_key)

        scored_articles.append(
            {
                "title": title,
                "source": _normalize_text(raw_article.get("source", "Unknown")) or "Unknown",
                "published_date": published_date.isoformat() if published_date else raw_article.get("published_date"),
                "description": _truncate_text(_normalize_text(raw_article.get("description", "")), 400),
                "url": url,
                "relevance_score": relevance_score,
                "importance_score": importance_score,
            }
        )

    return scored_articles[:MAX_ARTICLES_PER_TOPIC]


def calculate_relevance_score(topic: str, article: Dict[str, Any]) -> int:
    topic_tokens = _keyword_tokens(topic)
    title = _normalize_text(article.get("title", ""))
    description = _normalize_text(article.get("description", ""))

    if not topic_tokens or not title:
        return 0

    title_tokens = _keyword_tokens(title)
    description_tokens = _keyword_tokens(description)
    combined_text = f"{title} {description}"
    combined_tokens = set(title_tokens) | set(description_tokens)

    overlap = len(set(topic_tokens) & combined_tokens)
    overlap_score = min(45, overlap * 18)

    fuzzy_title = int(_similarity(topic, title) * 35)
    fuzzy_description = int(_similarity(topic, description) * 15)

    token_coverage = 0
    if topic_tokens:
        token_coverage = int((len(set(topic_tokens) & combined_tokens) / len(set(topic_tokens))) * 20)

    phrase_bonus = 0
    if _normalize_text(topic) in combined_text:
        phrase_bonus = 10

    score = overlap_score + fuzzy_title + fuzzy_description + token_coverage + phrase_bonus
    return max(0, min(100, score))


def calculate_importance_score(topic: str, article: Dict[str, Any], relevance_score: int) -> int:
    source_score = _source_quality_score(article.get("source", ""))
    recency_score = _recency_score(article.get("published_date"))
    matching_keyword_score = _matching_keyword_score(topic, article)
    uniqueness_score = _uniqueness_score(article)

    score = (
        (source_score * 0.35)
        + (recency_score * 0.25)
        + (matching_keyword_score * 0.20)
        + (uniqueness_score * 0.20)
        + (relevance_score * 0.10)
    )
    return max(0, min(100, int(score)))


def _source_quality_score(source: str) -> int:
    normalized = _normalize_text(source)
    if not normalized:
        return 25

    if normalized in TRUSTED_SOURCES:
        return 90

    if any(trusted in normalized for trusted in TRUSTED_SOURCES):
        return 80

    if any(word in normalized for word in ["news", "times", "post", "daily", "journal"]):
        return 60

    return 40


def _recency_score(published_date: Optional[str]) -> int:
    parsed = _parse_datetime(published_date)
    if not parsed:
        return 45

    age_hours = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0)
    if age_hours <= 6:
        return 100
    if age_hours <= 24:
        return 92
    if age_hours <= 48:
        return 80
    if age_hours <= 72:
        return 68
    if age_hours <= 120:
        return 55
    return 35


def _matching_keyword_score(topic: str, article: Dict[str, Any]) -> int:
    topic_tokens = set(_keyword_tokens(topic))
    article_tokens = set(_keyword_tokens(f"{article.get('title', '')} {article.get('description', '')}"))
    if not topic_tokens:
        return 0

    overlap = len(topic_tokens & article_tokens)
    ratio = overlap / max(1, len(topic_tokens))
    return int(min(100, (overlap * 20) + (ratio * 40)))


def _uniqueness_score(article: Dict[str, Any]) -> int:
    title = _normalize_text(article.get("title", ""))
    description = _normalize_text(article.get("description", ""))
    if not title:
        return 0

    similarity_penalty = int(_similarity(title, description) * 30)
    return max(40, 100 - similarity_penalty)


def generate_trend_summary(topic: str, articles: Sequence[Dict[str, Any]]) -> str:
    if not articles:
        return f"Limited recent news coverage is available for {topic}."

    titles = [article.get("title", "") for article in articles[:5] if article.get("title")]
    descriptions = [article.get("description", "") for article in articles[:5] if article.get("description")]
    category = infer_category(topic)

    if titles:
        lead = _build_lead_phrase(topic, titles)
    else:
        lead = f"Recent coverage around {topic}"

    themes = _extract_themes(topic, titles + descriptions)
    theme_text = f" around {', '.join(themes[:3])}" if themes else ""

    return (
        f"{lead} is generating recent discussion{theme_text}. "
        f"The topic appears most relevant to {category} content, with the strongest signals coming from the most recent and trusted sources."
    )


def calculate_newsjack_score(topic: str, articles: Sequence[Dict[str, Any]]) -> int:
    if not articles:
        return _category_baseline_newsjack_score(topic)

    article_count = len(articles)
    source_diversity = len({ _normalize_text(article.get("source", "")) for article in articles if article.get("source") })
    recency_avg = _average_recentness(articles)
    popularity_score = _trend_popularity_score(topic)
    category_score = _category_opportunity_score(topic)

    count_score = min(100, article_count * 7)
    diversity_score = min(100, source_diversity * 20)

    score = (
        (count_score * 0.20)
        + (recency_avg * 0.20)
        + (diversity_score * 0.15)
        + (popularity_score * 0.25)
        + (category_score * 0.20)
    )
    return max(0, min(100, int(score)))


def infer_category(topic: str) -> str:
    normalized = _normalize_text(topic)
    if not normalized:
        return "general"

    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return category

    return "general"


def _category_opportunity_score(topic: str) -> int:
    category = infer_category(topic)
    if category in {"technology", "entertainment", "sports"}:
        return 90
    if category in {"business", "climate"}:
        return 72
    if category == "health":
        return 68
    return 45


def _category_baseline_newsjack_score(topic: str) -> int:
    baseline = _category_opportunity_score(topic)
    return max(20, baseline - 25)


def _trend_popularity_score(topic: str) -> int:
    popularity = 40
    try:
        if not SERPAPI_KEY:
            return popularity

        search = GoogleSearch(
            {
                "engine": "google_trends_trending_now",
                "geo": SERPAPI_GEO,
                "api_key": SERPAPI_KEY,
            }
        )
        results = search.get_dict()
        for trend in results.get("trending_searches", []):
            query = trend.get("query", "")
            if not _topics_match(topic, query):
                continue

            increase_percentage = _safe_int(trend.get("increase_percentage", 0))
            search_volume = _safe_int(trend.get("search_volume", 0))
            popularity = min(100, max(20, increase_percentage + min(60, search_volume // 1000)))
            break
    except Exception:
        logger.exception("Failed to calculate popularity score for '%s'", topic)

    return popularity


def _fetch_live_trends() -> List[Dict[str, Any]]:
    if not SERPAPI_KEY:
        return []

    try:
        search = GoogleSearch(
            {
                "engine": "google_trends_trending_now",
                "geo": SERPAPI_GEO,
                "api_key": SERPAPI_KEY,
            }
        )
        results = search.get_dict()

        trends: List[Dict[str, Any]] = []
        for item in results.get("trending_searches", []):
            topic = item.get("query", "")
            if not topic:
                continue
            trends.append(
                {
                    "topic": topic,
                    "category": infer_category(topic),
                    "news_page_token": item.get("news_page_token"),
                }
            )

        return trends
    except Exception:
        logger.exception("Failed to fetch live trends")
        return []


def _topics_match(left: str, right: str) -> bool:
    left_normalized = _normalize_text(left)
    right_normalized = _normalize_text(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    if left_normalized in right_normalized or right_normalized in left_normalized:
        return True
    return _similarity(left_normalized, right_normalized) >= 0.72


def _is_spam(title: str, description: str) -> bool:
    text = f"{title} {description}".strip()
    if not text:
        return True

    if any(pattern.search(text) for pattern in SPAM_PATTERNS):
        return True

    letters = sum(1 for char in text if char.isalpha())
    if letters and len(text) > 0:
        upper_ratio = sum(1 for char in text if char.isupper()) / max(1, letters)
        if upper_ratio > 0.7:
            return True

    return False


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    try:
        parsed = date_parser.parse(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_url(value: Any) -> str:
    url = _normalize_text(value).lower()
    return url.rstrip("/")


def _normalize_title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def _keyword_tokens(text: str) -> List[str]:
    normalized = _normalize_text(text).lower()
    normalized = re.sub(r"[^a-z0-9\s]+", " ", normalized)
    return [token for token in normalized.split() if len(token) > 1]


def _first_non_empty(payload: Dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, dict):
            candidate = value.get("name") or value.get("title")
        else:
            candidate = value
        if candidate:
            return _normalize_text(candidate)
    return ""


def _extract_source_name(article: Dict[str, Any]) -> str:
    source = article.get("source")
    if isinstance(source, dict):
        return _normalize_text(source.get("name", ""))
    return _normalize_text(source)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _normalize_text(left).lower(), _normalize_text(right).lower()).ratio()


def _truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _average_score(articles: Sequence[Dict[str, Any]], key: str) -> int:
    values = [int(article.get(key, 0)) for article in articles if article.get(key) is not None]
    if not values:
        return 0
    return int(sum(values) / len(values))


def _average_recentness(articles: Sequence[Dict[str, Any]]) -> int:
    if not articles:
        return 0
    scores = [_recency_score(article.get("published_date")) for article in articles]
    return int(sum(scores) / len(scores))


def _extract_themes(topic: str, texts: Sequence[str]) -> List[str]:
    tokens = []
    for text in texts:
        tokens.extend(_keyword_tokens(text))

    topic_tokens = set(_keyword_tokens(topic))
    counts = Counter(token for token in tokens if token not in topic_tokens and len(token) > 3)
    return [token for token, _ in counts.most_common(4)]


def _build_lead_phrase(topic: str, titles: Sequence[str]) -> str:
    primary = titles[0]
    topic_text = _normalize_text(topic)
    if _topics_match(topic_text, primary):
        return primary
    return f"{topic_text.title()} coverage"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _empty_result(topic: str) -> Dict[str, Any]:
    return {
        "topic": topic,
        "summary": f"No strong recent coverage was found for {topic}.",
        "newsjack_score": 0,
        "articles": [],
        "top_articles": [],
        "article_count": 0,
        "avg_relevance": 0,
        "avg_importance": 0,
    }