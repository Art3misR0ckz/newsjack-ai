from app.services import opportunity_intelligence_service as service


def test_opportunity_intelligence_calculates_final_score(monkeypatch):
    monkeypatch.setattr(
        service,
        "score_brand_relevance",
        lambda *args: {
            "relevance_score": 90,
            "audience_overlap": 82,
            "newsjack_potential": 88,
            "reason": "Strong fit",
            "recommended_angle": "inspirational",
        },
    )
    result = service.calculate_opportunity(
        {"topic": "Fitness recovery", "category": "health", "source": "google_trends", "trend_strength": 85},
        {
            "summary": "Recovery is trending.",
            "articles": [{"source": "Reuters"}, {"source": "BBC"}, {"source": "Reuters"}],
        },
        {"brand_name": "ProteinX", "industry": "Fitness"},
    )
    assert result["source_diversity"] == 2
    assert result["news_volume"] == 3
    assert result["final_score"] >= 70
