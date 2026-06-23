from app.services import brand_relevance_service as service


def test_brand_relevance_uses_validated_fallback(monkeypatch):
    monkeypatch.setattr(service, "_call_openrouter", lambda *_: (_ for _ in ()).throw(RuntimeError("offline")))
    result = service.score_brand_relevance(
        {
            "brand_name": "ProteinX",
            "industry": "Fitness",
            "target_audience": "Gym enthusiasts",
            "goals": "Build awareness",
        },
        {
            "topic": "Virat Kohli launches training shoes",
            "summary": "A sports and fitness product announcement",
            "newsjack_score": 82,
        },
    )
    assert 0 <= result["relevance_score"] <= 100
    assert result["relevance_score"] > 50
    assert result["recommended_angle"] in service.ALLOWED_ANGLES
