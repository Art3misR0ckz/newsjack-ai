"""Manual smoke test for due LinkedIn publishing."""

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
    print("NEWSJACK AI LinkedIn due-post publisher smoke test")
    print("Environment presence:")
    for name, present in env_presence_report(
        [
            "NOTION_API_KEY",
            "NOTION_PARENT_PAGE_ID",
            "NOTION_LINKEDIN_DATABASE_ID",
            "LINKEDIN_ACCESS_TOKEN",
            "LINKEDIN_ORGANIZATION_URN",
        ]
    ).items():
        print(f"  - {name}: {'present' if present else 'missing'}")
    result = publish_due_posts()
    print(json.dumps(result, indent=2, default=str))
    if not isinstance(result, dict):
        print("Publisher returned a non-dict result.")
        return 1
    if not result.get("ok"):
        print("Publisher returned a handled failure.")
        return 1
    print("SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
