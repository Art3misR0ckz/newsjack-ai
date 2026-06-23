from app.services import content_generation_service as service


def test_content_generation_is_channel_ready(monkeypatch):
    monkeypatch.setattr(service, "generate_json", lambda **kwargs: kwargs["fallback"])
    result = service.generate_content(
        {"brand_name": "ProteinX", "industry": "Fitness", "tone": "Motivational"},
        {"topic": "Recovery trends"},
        {"campaign_angle": "Recover stronger"},
    )
    assert result["linkedin_post"]
    assert len(result["twitter_post"]) <= 280
    assert result["tweet_x"] == result["twitter_post"]
    assert result["hashtags"]
