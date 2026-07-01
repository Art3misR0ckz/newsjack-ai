"""Manual smoke test for the Notion-backed LinkedIn scheduler."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

from app.services.env_service import env_presence_report
from app.services.linkedin_scheduler_service import GAMEPULSE_PROFILE, generate_linkedin_calendar, push_calendar_to_notion
from app.services.notion_service import (
    REQUIRED_PROPERTY_TYPES,
    get_or_create_linkedin_calendar_database,
    load_notion_calendar_posts,
    update_notion_post_approval,
    update_notion_post_status,
)

load_dotenv(ROOT_DIR / ".env")


def main() -> int:
    print("NEWSJACK AI Notion LinkedIn Scheduler smoke test")
    os.environ["OPENROUTER_API_KEY"] = ""
    print("Environment presence:")
    for name, present in env_presence_report(
        ["NOTION_API_KEY", "NOTION_PARENT_PAGE_ID", "NOTION_LINKEDIN_DATABASE_ID"]
    ).items():
        print(f"  - {name}: {'present' if present else 'missing'}")
    missing = [name for name in ["NOTION_API_KEY"] if not os.getenv(name)]
    if not os.getenv("NOTION_PARENT_PAGE_ID") and not os.getenv("NOTION_LINKEDIN_DATABASE_ID"):
        missing.append("NOTION_PARENT_PAGE_ID or NOTION_LINKEDIN_DATABASE_ID")
    if missing:
        print(f"Missing env vars: {', '.join(missing)}")
        print("Add them to .env, share the Notion parent page/database with your integration, then retry.")
        return 0

    database = get_or_create_linkedin_calendar_database()
    print(database.get("message"))
    if not database.get("ok"):
        return 1
    property_names = database.get("property_names", [])
    print(f"Database ID: {database.get('database_id')}")
    if database.get("data_source_id"):
        print(f"Data source ID: {database.get('data_source_id')}")
    print("Current properties:")
    for name in property_names:
        print(f"  - {name}")
    missing = [name for name in REQUIRED_PROPERTY_TYPES if name not in property_names]
    if missing:
        print(f"Missing required properties after schema repair: {', '.join(missing)}")
        return 1

    calendar = generate_linkedin_calendar(GAMEPULSE_PROFILE, days=3)
    print(f"Generated {len(calendar)} sample posts.")

    pushed = push_calendar_to_notion(calendar)
    print(pushed.get("message"))
    if not pushed.get("ok"):
        print(pushed.get("errors", []))
        return 1

    loaded = load_notion_calendar_posts()
    print(f"Loaded {len(loaded.get('posts', []))} posts from Notion.")
    if not loaded.get("ok"):
        return 1
    loaded_posts = loaded.get("posts", [])
    created_page_ids = {item.get("page_id") for item in pushed.get("created", []) if item.get("page_id")}
    post = next((item for item in loaded_posts if item.get("page_id") in created_page_ids), loaded_posts[0] if loaded_posts else None)
    if not post or not post.get("page_id"):
        print("No Notion page id found after loading posts.")
        return 1

    scheduled = update_notion_post_status(post["page_id"], "Scheduled")
    print(scheduled.get("message"))
    if not scheduled.get("ok"):
        return 1
    approved = update_notion_post_approval(post["page_id"], True)
    print(approved.get("message"))
    if not approved.get("ok"):
        return 1

    print("SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
