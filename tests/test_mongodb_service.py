from types import SimpleNamespace

import app.services.mongodb_service as service


def test_mongodb_ping_returns_safe_status(monkeypatch):
    monkeypatch.setattr(
        service,
        "settings",
        SimpleNamespace(mongodb_enabled=False, mongodb_uri="", mongodb_database="newsjack_ai"),
    )
    status = service.ping_mongodb()
    assert "enabled" in status
    assert "connected" in status
    assert "mode" in status or "database" in status
