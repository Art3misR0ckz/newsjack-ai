from app.services import opportunity_generator_service as service


def test_campaign_generator_returns_complete_campaign(monkeypatch):
    monkeypatch.setattr(service, "generate_json", lambda **kwargs: kwargs["fallback"])
    result = service.generate_campaign(
        {"brand_name": "ProteinX"},
        {"topic": "Athlete recovery", "final_score": 84, "recommended_angle": "inspirational"},
    )
    assert result["campaign_angle"]
    assert result["confidence"] == 84
    assert "Instagram" in result["recommended_channels"]
