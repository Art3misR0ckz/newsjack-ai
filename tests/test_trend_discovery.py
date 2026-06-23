from app.services import trend_discovery_service as service


def test_discover_trends_normalizes_and_deduplicates(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_google_trends",
        lambda: [
            {"topic": "AI Launch", "search_volume": "10,000", "increase_percentage": "80", "category": "Technology"},
            {"topic": "AI Launch", "search_volume": 9000, "increase_percentage": 60, "category": "Technology"},
        ],
    )
    monkeypatch.setattr("app.services.cache_service.get_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.services.cache_service.set_cached", lambda namespace, key, value: value)
    results = service.discover_trends(5)
    assert len(results) == 1
    assert results[0]["source"] == "google_trends"
    assert results[0]["trend_strength"] > 50
