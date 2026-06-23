from datetime import datetime, timezone

from app.services import trend_news_service as service


def test_news_enrichment_filters_duplicates_and_scores(monkeypatch):
    now = datetime.now(timezone.utc).isoformat()
    raw = [
        {
            "title": "OpenAI launches a major new AI product for businesses",
            "source": "Reuters",
            "published_date": now,
            "description": "The OpenAI product launch expands enterprise AI tools.",
            "url": "https://example.com/a",
        },
        {
            "title": "OpenAI launches a major new AI product for businesses",
            "source": "Reuters",
            "published_date": now,
            "description": "Duplicate",
            "url": "https://example.com/a",
        },
    ]
    monkeypatch.setattr(service, "_fetch_articles_for_topic", lambda topic: raw)
    monkeypatch.setattr(service, "_trend_popularity_score", lambda topic: 80)
    result = service.get_news_for_trend("OpenAI product launch")
    assert result["article_count"] == 1
    assert result["articles"][0]["relevance_score"] >= service.MIN_RELEVANCE_SCORE
    assert result["newsjack_score"] > 0
