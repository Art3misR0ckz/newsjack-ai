"""Publish due approved LinkedIn posts from the Notion scheduler."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.env_service import env_presence_report, load_project_env
from app.services.linkedin_post_service import publish_due_posts

load_project_env()


def main() -> int:
    report = env_presence_report(
        [
            "NOTION_API_KEY",
            "NOTION_PARENT_PAGE_ID",
            "NOTION_LINKEDIN_DATABASE_ID",
            "LINKEDIN_ACCESS_TOKEN",
            "LINKEDIN_ORGANIZATION_URN",
        ]
    )
    print("NEWSJACK AI LinkedIn due-post publisher")
    print("Environment presence:")
    for name, present in report.items():
        print(f"  - {name}: {'present' if present else 'missing'}")
    result = publish_due_posts()
    print("Result:")
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
