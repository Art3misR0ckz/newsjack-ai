"""Official LinkedIn API publishing for approved Notion scheduler posts."""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests

from app.services.env_service import env_value, load_project_env, missing_env
from app.services.notion_service import (
    load_notion_calendar_posts,
    update_notion_post_publish_result,
)

logger = logging.getLogger(__name__)
load_project_env()

LINKEDIN_POSTS_URL = "https://api.linkedin.com/rest/posts"
LINKEDIN_API_VERSION = "202606"
SCHEDULER_TZ = ZoneInfo("Asia/Kolkata")


def get_due_approved_posts() -> list[dict[str, Any]]:
    """Return approved, scheduled Notion posts whose scheduled date/time is due."""
    loaded = load_notion_calendar_posts()
    if not loaded.get("ok"):
        logger.warning("Could not load Notion posts for LinkedIn publishing: %s", loaded.get("message"))
        return []
    now = datetime.now(SCHEDULER_TZ)
    return [
        post
        for post in loaded.get("posts", [])
        if _is_publishable(post, now=now)
    ]


def publish_due_posts() -> dict[str, Any]:
    """Publish every due, approved, scheduled Notion post through LinkedIn's Posts API."""
    missing_credentials = _missing_linkedin_credentials()
    if missing_credentials:
        return {
            "ok": True,
            "total": 0,
            "published": 0,
            "failed": 0,
            "results": [],
            "message": "LinkedIn credentials not configured",
            "missing": missing_credentials,
        }
    posts = get_due_approved_posts()
    results = [publish_text_post(post) for post in posts]
    published = sum(1 for result in results if result.get("ok"))
    failed = sum(1 for result in results if not result.get("ok"))
    return {
        "ok": failed == 0,
        "total": len(results),
        "published": published,
        "failed": failed,
        "results": results,
        "message": f"Published {published} due LinkedIn post{'s' if published != 1 else ''}.",
    }


def publish_text_post(post: Mapping[str, Any]) -> dict[str, Any]:
    """
    Publish one approved scheduled text post via LinkedIn Posts API.

    This function intentionally refuses Draft, unapproved, unscheduled, or not-yet-due
    posts even when called directly.
    """
    page_id = str(post.get("page_id") or "")
    safety_error = _publish_safety_error(post)
    if safety_error:
        return {"ok": False, "published": False, "message": safety_error, "page_id": page_id}

    due_at = _scheduled_datetime(post)
    if due_at is None or due_at > datetime.now(SCHEDULER_TZ):
        return {"ok": False, "published": False, "message": "Post is not due yet.", "page_id": page_id}

    text = str(post.get("linkedin_post") or "").strip()
    if not text:
        return {"ok": False, "published": False, "message": "LinkedIn post text is empty.", "page_id": page_id}

    missing_credentials = _missing_linkedin_credentials()
    if missing_credentials:
        return {
            "ok": False,
            "published": False,
            "message": "LinkedIn credentials not configured",
            "missing": missing_credentials,
            "page_id": page_id,
        }

    try:
        response = requests.post(
            LINKEDIN_POSTS_URL,
            headers=_linkedin_headers(),
            json=_post_payload(text),
            timeout=_request_timeout(),
        )
    except Exception as exc:
        message = f"LinkedIn API request failed: {exc.__class__.__name__}"
        _mark_failed(page_id, post, message)
        logger.exception("LinkedIn publish request failed", extra={"event": "linkedin_publish_failed"})
        return {"ok": False, "published": False, "message": message, "page_id": page_id}

    if response.status_code not in {200, 201}:
        message = _response_error(response)
        _mark_failed(page_id, post, message)
        logger.warning(
            "LinkedIn publish failed",
            extra={"event": "linkedin_publish_failed", "status_code": response.status_code},
        )
        return {"ok": False, "published": False, "message": message, "page_id": page_id}

    post_urn = response.headers.get("x-restli-id", "")
    linkedin_url = _linkedin_url_from_urn(post_urn)
    notes = _append_note(post, "Published to LinkedIn via Posts API." + (f" Post URN: {post_urn}" if post_urn else ""))
    if page_id:
        update_notion_post_publish_result(page_id, "Posted", notes=notes, linkedin_url=linkedin_url)
    logger.info("Published LinkedIn post", extra={"event": "linkedin_post_published"})
    return {
        "ok": True,
        "published": True,
        "message": "LinkedIn post published.",
        "page_id": page_id,
        "linkedin_urn": post_urn,
        "linkedin_url": linkedin_url,
    }


def _publish_safety_error(post: Mapping[str, Any]) -> str:
    if not bool(post.get("approval", False)):
        return "Refusing to publish unapproved post."
    status = str(post.get("status") or "").strip()
    if status == "Draft":
        return "Refusing to publish Draft post."
    if status != "Scheduled":
        return f"Refusing to publish post with status {status or 'empty'}."
    return ""


def _is_publishable(post: Mapping[str, Any], now: datetime | None = None) -> bool:
    if _publish_safety_error(post):
        return False
    scheduled = _scheduled_datetime(post)
    return scheduled is not None and scheduled <= (now or datetime.now(SCHEDULER_TZ))


def _scheduled_datetime(post: Mapping[str, Any]) -> datetime | None:
    scheduled_date = _parse_date(post.get("date"))
    scheduled_time = _parse_time(post.get("time"))
    if scheduled_date is None or scheduled_time is None:
        return None
    return datetime.combine(scheduled_date, scheduled_time, tzinfo=SCHEDULER_TZ)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.astimezone(SCHEDULER_TZ).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None


def _parse_time(value: Any) -> time | None:
    if isinstance(value, datetime):
        return value.astimezone(SCHEDULER_TZ).time().replace(tzinfo=None)
    if isinstance(value, time):
        return value.replace(tzinfo=None)
    text = str(value or "").strip().upper()
    if not text:
        return None
    for token in (" IST", " UTC", " GMT"):
        text = text.replace(token, "")
    text = " ".join(text.split())
    for time_format in ("%I:%M %p", "%I %p", "%H:%M", "%H%M"):
        try:
            return datetime.strptime(text, time_format).time()
        except ValueError:
            continue
    return None


def _linkedin_headers() -> dict[str, str]:
    token = env_value("LINKEDIN_ACCESS_TOKEN")
    if not token:
        raise ValueError("Set LINKEDIN_ACCESS_TOKEN before publishing.")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Linkedin-Version": env_value("LINKEDIN_API_VERSION", LINKEDIN_API_VERSION) or LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
    }


def _post_payload(text: str) -> dict[str, Any]:
    organization_urn = env_value("LINKEDIN_ORGANIZATION_URN")
    if not organization_urn:
        raise ValueError("Set LINKEDIN_ORGANIZATION_URN before publishing.")
    return {
        "author": organization_urn,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def _request_timeout() -> int:
    try:
        return int(env_value("REQUEST_TIMEOUT_SECONDS", "20"))
    except ValueError:
        return 20


def _missing_linkedin_credentials() -> list[str]:
    return missing_env(["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_ORGANIZATION_URN"])


def _response_error(response: requests.Response) -> str:
    body = response.text[:1000] if response.text else ""
    return f"LinkedIn API returned {response.status_code}: {body or response.reason}"


def _mark_failed(page_id: str, post: Mapping[str, Any], message: str) -> None:
    if page_id:
        update_notion_post_publish_result(page_id, "Failed", notes=_append_note(post, message))


def _append_note(post: Mapping[str, Any], note: str) -> str:
    current = str(post.get("notes") or "").strip()
    stamp = datetime.now(SCHEDULER_TZ).strftime("%Y-%m-%d %H:%M %Z")
    addition = f"[{stamp}] {note}"
    return f"{current}\n{addition}" if current else addition


def _linkedin_url_from_urn(post_urn: str) -> str:
    if not post_urn:
        return ""
    if post_urn.startswith("urn:li:ugcPost:"):
        return f"https://www.linkedin.com/feed/update/{post_urn}/"
    if post_urn.startswith("urn:li:share:"):
        return f"https://www.linkedin.com/feed/update/{post_urn}/"
    return ""
