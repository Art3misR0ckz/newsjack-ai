"""Generate and manage a Notion-backed LinkedIn content calendar."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Mapping

from app.services.env_service import load_project_env
from app.services.llm_service import generate_json
from app.services.notion_service import (
    create_notion_calendar_post,
    load_notion_calendar_posts,
    update_notion_post_approval,
    update_notion_post_status,
)

logger = logging.getLogger(__name__)
load_project_env()

GAMEPULSE_PROFILE: dict[str, Any] = {
    "brand_name": "GamePulse AI",
    "industry": "Gaming Intelligence / AI Marketing Intelligence",
    "target_audience": (
        "Gaming studios, esports teams, gaming hardware brands, streamers, creators, "
        "and gaming marketing agencies"
    ),
    "tone": "Energetic, sharp, data-driven, founder-like, gaming-native",
    "goals": "Help gaming brands discover viral moments early and turn gaming trends into campaign opportunities",
    "keywords": [
        "gaming",
        "esports",
        "Twitch",
        "YouTube Gaming",
        "Steam",
        "PlayStation",
        "Xbox",
        "Nintendo",
        "Discord",
        "game launches",
        "gaming marketing",
        "AI trend intelligence",
        "creator campaigns",
    ],
    "products": [
        "Gaming Trend Radar",
        "Opportunity Explorer",
        "Campaign Studio",
        "Competitor Monitor",
        "LinkedIn Scheduler",
    ],
    "competitors": [
        "IGN",
        "GameSpot",
        "Dexerto",
        "Esports Insider",
        "Newzoo",
        "Razer",
        "Logitech G",
        "Red Bull Gaming",
    ],
    "brand_summary": (
        "GamePulse AI is an AI-powered gaming intelligence platform that tracks gaming news, esports moments, "
        "creator trends, and community signals to help brands act before gaming moments peak."
    ),
}

THEMES = [
    "gaming trend intelligence",
    "esports marketing",
    "game launch campaigns",
    "creator economy",
    "Twitch and YouTube Gaming",
    "gaming hardware brands",
    "AI for gaming marketing",
    "community-led marketing",
    "viral gaming moments",
    "competitor monitoring",
    "campaign timing",
    "Discord communities",
    "Steam launches",
    "PlayStation, Xbox, and Nintendo updates",
]


def generate_linkedin_calendar(
    brand_profile: Mapping[str, Any] | None,
    days: int = 30,
    start_date: str | date | None = None,
    post_time: str = "10:00 AM IST",
) -> list[dict[str, Any]]:
    """Generate a LinkedIn calendar for GamePulse AI."""
    profile = {**GAMEPULSE_PROFILE, **dict(brand_profile or {})}
    start = _coerce_date(start_date) or date.today()
    days = max(1, min(int(days or 30), 60))
    fallback = {"posts": _fallback_calendar(profile, days, start, post_time)}
    result = generate_json(
        system_prompt=(
            "You are a founder-led LinkedIn content strategist for gaming intelligence SaaS. "
            "Return strict JSON only. Write natural, professional LinkedIn posts with short paragraphs."
        ),
        user_prompt=(
            "Generate a LinkedIn calendar as JSON with one key named posts. posts must be an array. "
            "Each item must include post_title, date, time, topic, campaign_angle, linkedin_post, hashtags, "
            "status, source_opportunity, approval, brand, created_by, notes. "
            "Use status Draft, approval false, brand GamePulse AI, created_by NEWSJACK AI. "
            f"Days: {days}. Start date: {start.isoformat()}. Post time: {post_time}. "
            f"Themes: {json.dumps(THEMES)}. Brand profile: {json.dumps(profile, default=str)}"
        ),
        fallback=fallback,
        cache_key=f"linkedin-calendar:{profile.get('brand_name')}:{start.isoformat()}:{days}:{post_time}",
        temperature=0.65,
    )
    posts = result.get("posts") if isinstance(result, dict) else None
    if not isinstance(posts, list) or not posts:
        posts = fallback["posts"]
    cleaned = [_normalize_post(post, index, profile, start, post_time) for index, post in enumerate(posts[:days])]
    logger.info("Generated LinkedIn calendar", extra={"event": "linkedin_calendar_generated", "count": len(cleaned)})
    return cleaned


def push_calendar_to_notion(calendar: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Push generated LinkedIn calendar posts into Notion."""
    created: list[dict[str, Any]] = []
    errors: list[str] = []
    for post in calendar:
        result = create_notion_calendar_post(post)
        if result.get("ok"):
            created.append(result)
        else:
            errors.append(str(result.get("message", "Unknown Notion error")))
    logger.info("Pushed calendar to Notion", extra={"event": "linkedin_calendar_pushed", "count": len(created)})
    return {
        "ok": not errors,
        "created_count": len(created),
        "error_count": len(errors),
        "created": created,
        "errors": errors,
        "message": f"Pushed {len(created)} posts to Notion." if not errors else errors[0],
    }


def load_calendar_from_notion() -> dict[str, Any]:
    """Load LinkedIn calendar posts from Notion."""
    return load_notion_calendar_posts()


def approve_post(page_id: str) -> dict[str, Any]:
    """Approve a Notion LinkedIn calendar post."""
    approval = update_notion_post_approval(page_id, True)
    if approval.get("ok"):
        update_notion_post_status(page_id, "Approved")
    return approval


def mark_post_as_scheduled(page_id: str) -> dict[str, Any]:
    """Mark a Notion LinkedIn calendar post as scheduled."""
    return update_notion_post_status(page_id, "Scheduled")


def mark_post_as_posted(page_id: str) -> dict[str, Any]:
    """Mark a Notion LinkedIn calendar post as posted."""
    return update_notion_post_status(page_id, "Posted")


def mark_post_as_failed(page_id: str) -> dict[str, Any]:
    """Mark a Notion LinkedIn calendar post as failed."""
    return update_notion_post_status(page_id, "Failed")


def export_calendar_to_csv(calendar: list[Mapping[str, Any]]) -> str:
    """Export a calendar list to CSV text."""
    fields = [
        "date",
        "time",
        "post_title",
        "topic",
        "campaign_angle",
        "linkedin_post",
        "hashtags",
        "status",
        "source_opportunity",
        "approval",
        "linkedin_url",
        "brand",
        "created_by",
        "notes",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for post in calendar:
        row = dict(post)
        row["hashtags"] = ", ".join(row.get("hashtags", [])) if isinstance(row.get("hashtags"), list) else row.get("hashtags", "")
        writer.writerow(row)
    return buffer.getvalue()


def _coerce_date(value: str | date | None) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            logger.warning("Invalid start_date supplied to LinkedIn calendar: %s", value)
    return None


def _normalize_post(
    post: Mapping[str, Any],
    index: int,
    profile: Mapping[str, Any],
    start: date,
    post_time: str,
) -> dict[str, Any]:
    fallback = _fallback_post(profile, THEMES[index % len(THEMES)], start + timedelta(days=index), post_time, index)
    merged = {**fallback, **dict(post)}
    merged["date"] = str(merged.get("date") or fallback["date"])
    merged["time"] = str(merged.get("time") or post_time)
    merged["hashtags"] = _clean_hashtags(merged.get("hashtags") or fallback["hashtags"])
    merged["status"] = merged.get("status") if merged.get("status") in {"Draft", "Approved", "Scheduled", "Posted", "Failed"} else "Draft"
    merged["approval"] = bool(merged.get("approval", False))
    merged["brand"] = "GamePulse AI"
    merged["created_by"] = "NEWSJACK AI"
    return merged


def _fallback_calendar(profile: Mapping[str, Any], days: int, start: date, post_time: str) -> list[dict[str, Any]]:
    return [
        _fallback_post(profile, THEMES[index % len(THEMES)], start + timedelta(days=index), post_time, index)
        for index in range(days)
    ]


def _fallback_post(
    profile: Mapping[str, Any],
    theme: str,
    scheduled_date: date,
    post_time: str,
    index: int,
) -> dict[str, Any]:
    brand = str(profile.get("brand_name") or "GamePulse AI")
    title_theme = theme.title().replace("And", "and")
    angle = f"Turn {theme} into an earlier, sharper campaign decision."
    post = (
        f"Gaming moves fast, but the useful signal usually appears before the headline peaks.\n\n"
        f"For {title_theme}, the winning brands are not waiting for a weekly recap. They are watching creator velocity, "
        "community language, platform shifts, and competitor timing while the moment is still forming.\n\n"
        f"{brand} helps teams spot those patterns early and turn them into campaign opportunities with context, not guesswork.\n\n"
        "The question for gaming marketers this week: which signal are you tracking before everyone else sees it?"
    )
    return {
        "post_title": f"{title_theme}: Signal Before Spike",
        "date": scheduled_date.isoformat(),
        "time": post_time,
        "topic": theme,
        "campaign_angle": angle,
        "linkedin_post": post,
        "hashtags": _clean_hashtags(["Gaming", "Esports", "AI", "Marketing", "GamePulseAI"]),
        "status": "Draft",
        "source_opportunity": f"Fallback calendar theme #{index + 1}: {theme}",
        "approval": False,
        "brand": brand,
        "created_by": "NEWSJACK AI",
        "notes": "Generated by deterministic fallback. Review before scheduling.",
    }


def _clean_hashtags(raw: Any) -> list[str]:
    if isinstance(raw, str):
        values = [part.strip() for part in raw.replace("#", "").split(",")]
    elif isinstance(raw, list):
        values = [str(item).replace("#", "").strip() for item in raw]
    else:
        values = []
    cleaned: list[str] = []
    for value in values:
        tag = "".join(ch for ch in value.title().replace(" ", "") if ch.isalnum())
        if tag and tag not in cleaned:
            cleaned.append(tag)
    return cleaned[:8] or ["Gaming", "AI", "Marketing"]
