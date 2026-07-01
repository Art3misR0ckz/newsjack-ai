from datetime import datetime

from app.services import linkedin_post_service as service


def _post(**overrides):
    post = {
        "page_id": "notion-page-1",
        "approval": True,
        "status": "Scheduled",
        "date": "2026-07-01",
        "time": "10:00 AM IST",
        "linkedin_post": "Hello from the official API.",
        "notes": "",
    }
    post.update(overrides)
    return post


def test_due_posts_exclude_drafts_and_unapproved(monkeypatch):
    monkeypatch.setattr(
        service,
        "load_notion_calendar_posts",
        lambda: {
            "ok": True,
            "posts": [
                _post(page_id="approved-scheduled"),
                _post(page_id="draft", status="Draft"),
                _post(page_id="unapproved", approval=False),
                _post(page_id="future", date="2026-07-02"),
            ],
        },
    )
    monkeypatch.setattr(service, "datetime", _FixedDatetime)

    due = service.get_due_approved_posts()

    assert [post["page_id"] for post in due] == ["approved-scheduled"]


def test_publish_text_post_refuses_unapproved_without_api_call(monkeypatch):
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(service.requests, "post", fake_post)

    result = service.publish_text_post(_post(approval=False))

    assert not result["ok"]
    assert "unapproved" in result["message"]
    assert called is False


def test_publish_text_post_updates_notion_with_linkedin_url(monkeypatch):
    updates = []

    class Response:
        status_code = 201
        reason = "Created"
        text = ""
        headers = {"x-restli-id": "urn:li:ugcPost:12345"}

    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "token")
    monkeypatch.setenv("LINKEDIN_ORGANIZATION_URN", "urn:li:organization:123")
    monkeypatch.setattr(service, "datetime", _FixedDatetime)
    monkeypatch.setattr(service.requests, "post", lambda *args, **kwargs: Response())
    monkeypatch.setattr(
        service,
        "update_notion_post_publish_result",
        lambda *args, **kwargs: updates.append((args, kwargs)) or {"ok": True},
    )

    result = service.publish_text_post(_post())

    assert result["ok"]
    assert result["linkedin_url"] == "https://www.linkedin.com/feed/update/urn:li:ugcPost:12345/"
    assert updates[0][0][1] == "Posted"
    assert updates[0][1]["linkedin_url"] == result["linkedin_url"]


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 1, 10, 30, tzinfo=tz)
