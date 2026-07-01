import py_compile


def test_scheduler_services_import_cleanly():
    from app.services import linkedin_post_service, linkedin_scheduler_service, notion_service

    assert hasattr(notion_service, "update_notion_post_publish_result")
    assert hasattr(linkedin_post_service, "publish_due_posts")
    assert hasattr(linkedin_scheduler_service, "generate_linkedin_calendar")


def test_streamlit_app_compiles():
    py_compile.compile("app/streamlit_app.py", doraise=True)


def test_publish_due_posts_returns_cleanly_without_linkedin_credentials(monkeypatch):
    from app.services import linkedin_post_service

    monkeypatch.setattr(
        linkedin_post_service,
        "_missing_linkedin_credentials",
        lambda: ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORGANIZATION_URN"],
    )

    result = linkedin_post_service.publish_due_posts()

    assert result["ok"] is True
    assert result["published"] == 0
    assert result["failed"] == 0
    assert result["message"] == "LinkedIn credentials not configured"
