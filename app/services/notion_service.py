"""Notion calendar database helpers for the LinkedIn scheduler."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping

from app.services.env_service import env_value, load_project_env

try:
    from notion_client import Client
except Exception:  # pragma: no cover - optional dependency path
    Client = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)
load_project_env()

DATABASE_TITLE = "GamePulse AI LinkedIn Calendar"
STATUS_OPTIONS = ["Draft", "Approved", "Scheduled", "Posted", "Failed"]
REQUIRED_PROPERTY_TYPES = {
    "Post Title": "title",
    "Date": "date",
    "Time": "rich_text",
    "Topic": "rich_text",
    "Campaign Angle": "rich_text",
    "LinkedIn Post": "rich_text",
    "Hashtags": "multi_select",
    "Status": "select",
    "Source Opportunity": "rich_text",
    "Approval": "checkbox",
    "LinkedIn URL": "url",
    "Brand": "rich_text",
    "Created By": "rich_text",
    "Notes": "rich_text",
}


def _safe_response(ok: bool, message: str, **extra: Any) -> dict[str, Any]:
    return {"ok": ok, "message": message, **extra}


def _notion_client() -> Any | None:
    api_key = env_value("NOTION_API_KEY")
    if not api_key:
        logger.warning("NOTION_API_KEY is not configured")
        return None
    if Client is None:
        logger.warning("notion-client package is not installed")
        return None
    return Client(auth=api_key)


def _database_properties() -> dict[str, Any]:
    return {
        "Post Title": {"title": {}},
        "Date": {"date": {}},
        "Time": {"rich_text": {}},
        "Topic": {"rich_text": {}},
        "Campaign Angle": {"rich_text": {}},
        "LinkedIn Post": {"rich_text": {}},
        "Hashtags": {"multi_select": {"options": [{"name": tag} for tag in ["Gaming", "AI", "Marketing"]]}},
        "Status": {"select": {"options": [{"name": status} for status in STATUS_OPTIONS]}},
        "Source Opportunity": {"rich_text": {}},
        "Approval": {"checkbox": {}},
        "LinkedIn URL": {"url": {}},
        "Brand": {"rich_text": {}},
        "Created By": {"rich_text": {}},
        "Notes": {"rich_text": {}},
    }


def _database_title(database: Mapping[str, Any]) -> str:
    return "".join(item.get("plain_text", "") for item in database.get("title", []))


def _property_names(database: Mapping[str, Any]) -> list[str]:
    return sorted((database.get("properties") or {}).keys())


def _missing_schema_properties(data_source: Mapping[str, Any]) -> dict[str, Any]:
    current = data_source.get("properties") or {}
    specs = _database_properties()
    return {name: specs[name] for name in REQUIRED_PROPERTY_TYPES if name not in current}


def _wrong_type_properties(data_source: Mapping[str, Any]) -> dict[str, str]:
    current = data_source.get("properties") or {}
    wrong: dict[str, str] = {}
    for name, expected_type in REQUIRED_PROPERTY_TYPES.items():
        actual_type = current.get(name, {}).get("type")
        if actual_type and actual_type != expected_type:
            wrong[name] = str(actual_type)
    return wrong


def _status_options_update(data_source: Mapping[str, Any]) -> dict[str, Any]:
    status = (data_source.get("properties") or {}).get("Status", {})
    if status.get("type") != "select":
        return {}
    existing = {option.get("name") for option in status.get("select", {}).get("options", [])}
    if all(option in existing for option in STATUS_OPTIONS):
        return {}
    options = [{"name": option.get("name")} for option in status.get("select", {}).get("options", []) if option.get("name")]
    for status_name in STATUS_OPTIONS:
        if status_name not in existing:
            options.append({"name": status_name})
    return {"Status": {"select": {"options": options}}}


def _retrieve_database(client: Any, database_id: str) -> dict[str, Any] | None:
    try:
        database = client.databases.retrieve(database_id=database_id)
        if isinstance(database, dict):
            return database
    except Exception:
        logger.warning("Could not retrieve Notion database '%s'", database_id, exc_info=True)
    return None


def _retrieve_data_source(client: Any, data_source_id: str) -> dict[str, Any] | None:
    try:
        data_source = client.data_sources.retrieve(data_source_id=data_source_id)
        if isinstance(data_source, dict):
            return data_source
    except Exception:
        logger.warning("Could not retrieve Notion data source '%s'", data_source_id, exc_info=True)
    return None


def _data_source_database_id(data_source: Mapping[str, Any]) -> str:
    parent = data_source.get("parent", {})
    return str(parent.get("database_id", "") if parent.get("type") == "database_id" else "")


def _resolve_from_data_source(client: Any, data_source_id: str) -> dict[str, Any] | None:
    data_source = _retrieve_data_source(client, data_source_id)
    if not data_source:
        return None
    database_id = _data_source_database_id(data_source)
    database = _retrieve_database(client, database_id) if database_id else None
    return {"database_id": database_id or data_source_id, "data_source_id": data_source["id"], "database": database, "data_source": data_source}


def _resolve_from_database(client: Any, database_id: str) -> dict[str, Any] | None:
    database = _retrieve_database(client, database_id)
    if not database:
        return None
    data_sources = database.get("data_sources") or []
    if not data_sources:
        return {"database_id": database["id"], "data_source_id": "", "database": database, "data_source": database}
    data_source_id = data_sources[0]["id"]
    data_source = _retrieve_data_source(client, data_source_id)
    if not data_source:
        return None
    return {"database_id": database["id"], "data_source_id": data_source_id, "database": database, "data_source": data_source}


def _resolve_calendar_database(client: Any, database_or_data_source_id: str, prefer: str = "database") -> dict[str, Any] | None:
    if prefer == "data_source":
        return _resolve_from_data_source(client, database_or_data_source_id) or _resolve_from_database(client, database_or_data_source_id)
    return _resolve_from_database(client, database_or_data_source_id) or _resolve_from_data_source(client, database_or_data_source_id)


def _search_linkedin_calendar_database(client: Any) -> dict[str, Any] | None:
    try:
        response = client.search(
            query=DATABASE_TITLE,
            filter={"property": "object", "value": "data_source"},
            page_size=25,
        )
        parent_page_id = env_value("NOTION_PARENT_PAGE_ID").replace("-", "")
        candidates: list[dict[str, Any]] = []
        for result in response.get("results", []):
            if _database_title(result) != DATABASE_TITLE:
                continue
            resolved = _resolve_calendar_database(client, result["id"], prefer="data_source")
            if not resolved:
                continue
            database = resolved.get("database") or {}
            parent = database.get("parent", {})
            database_parent_id = str(parent.get("page_id", "")).replace("-", "")
            if parent_page_id and database_parent_id and database_parent_id != parent_page_id:
                continue
            candidates.append(resolved)
        if candidates:
            candidates.sort(
                key=lambda item: sum(
                    1 for name in REQUIRED_PROPERTY_TYPES if name in (item.get("data_source", {}).get("properties") or {})
                ),
                reverse=True,
            )
            return candidates[0]
    except Exception:
        logger.warning("Could not search for Notion calendar database", exc_info=True)
    return None


def _rename_default_title_property(client: Any, data_source: Mapping[str, Any]) -> dict[str, Any]:
    properties = data_source.get("properties") or {}
    if "Post Title" in properties:
        return dict(data_source)
    for name, prop in properties.items():
        if prop.get("type") == "title":
            logger.info("Renaming Notion title property", extra={"event": "notion_title_property_renamed"})
            if hasattr(client, "data_sources") and data_source.get("object") == "data_source":
                return client.data_sources.update(data_source_id=data_source["id"], properties={name: {"name": "Post Title"}})
            return client.databases.update(database_id=data_source["id"], properties={name: {"name": "Post Title"}})
    return dict(data_source)


def ensure_linkedin_calendar_schema(database_id: str, data_source_id: str | None = None) -> dict[str, Any]:
    """Ensure the Notion calendar database has every required scheduler property."""
    client = _notion_client()
    if client is None or not database_id:
        return _safe_response(False, "Set NOTION_API_KEY and provide a Notion database id.", property_names=[])
    resolved = (
        _resolve_calendar_database(client, data_source_id, prefer="data_source")
        if data_source_id
        else _resolve_calendar_database(client, database_id, prefer="database")
    )
    if not resolved:
        return _safe_response(False, "Could not retrieve Notion database.", database_id=database_id, property_names=[])
    database = resolved.get("database") or {}
    data_source = resolved["data_source"]
    database_id = resolved["database_id"]
    data_source_id = resolved["data_source_id"]
    try:
        data_source = _rename_default_title_property(client, data_source)
    except Exception as exc:
        logger.exception("Could not rename Notion title property")
        return _safe_response(
            False,
            f"Could not rename Notion title property: {exc.__class__.__name__}",
            database_id=database_id,
            data_source_id=data_source_id,
            property_names=_property_names(data_source),
        )
    wrong_types = _wrong_type_properties(data_source)
    if wrong_types:
        message = "Notion database has incompatible property types: " + ", ".join(
            f"{name} is {actual}, expected {REQUIRED_PROPERTY_TYPES[name]}" for name, actual in wrong_types.items()
        )
        return _safe_response(False, message, database_id=database_id, data_source_id=data_source_id, property_names=_property_names(data_source))
    updates = _missing_schema_properties(data_source)
    updates.update(_status_options_update(data_source))
    if updates:
        try:
            if data_source_id and hasattr(client, "data_sources"):
                data_source = client.data_sources.update(data_source_id=data_source_id, properties=updates)
            else:
                data_source = client.databases.update(database_id=database_id, properties=updates)
            logger.info(
                "Updated Notion calendar database schema",
                extra={"event": "notion_database_schema_updated", "properties": sorted(updates.keys())},
            )
        except Exception as exc:
            logger.exception("Could not update Notion calendar database schema")
            return _safe_response(
                False,
                f"Could not update Notion database schema: {exc.__class__.__name__}",
                database_id=database_id,
                data_source_id=data_source_id,
                property_names=_property_names(data_source),
            )
    property_names = _property_names(data_source)
    logger.info(
        "Notion calendar schema ready",
        extra={
            "event": "notion_database_schema_ready",
            "database_id": database_id,
            "data_source_id": data_source_id,
            "property_names": property_names,
        },
    )
    return _safe_response(
        True,
        "Notion database schema ready.",
        database_id=database_id,
        data_source_id=data_source_id,
        database=database,
        data_source=data_source,
        property_names=property_names,
    )


def _text(value: Any) -> list[dict[str, Any]]:
    content = str(value or "")
    if not content:
        return []
    return [
        {"type": "text", "text": {"content": content[index:index + 2000]}}
        for index in range(0, len(content), 2000)
    ]


def _post_properties(post: Mapping[str, Any]) -> dict[str, Any]:
    hashtags = [str(tag).replace("#", "").strip() for tag in post.get("hashtags", []) if str(tag).strip()]
    status = str(post.get("status") or "Draft")
    if status not in STATUS_OPTIONS:
        status = "Draft"
    return {
        "Post Title": {"title": _text(post.get("post_title") or post.get("title") or "LinkedIn Post")},
        "Date": {"date": {"start": str(post.get("date") or "")} if post.get("date") else None},
        "Time": {"rich_text": _text(post.get("time"))},
        "Topic": {"rich_text": _text(post.get("topic"))},
        "Campaign Angle": {"rich_text": _text(post.get("campaign_angle"))},
        "LinkedIn Post": {"rich_text": _text(post.get("linkedin_post"))},
        "Hashtags": {"multi_select": [{"name": tag[:100]} for tag in hashtags[:20]]},
        "Status": {"select": {"name": status}},
        "Source Opportunity": {"rich_text": _text(post.get("source_opportunity"))},
        "Approval": {"checkbox": bool(post.get("approval", False))},
        "LinkedIn URL": {"url": post.get("linkedin_url") or None},
        "Brand": {"rich_text": _text(post.get("brand") or "GamePulse AI")},
        "Created By": {"rich_text": _text(post.get("created_by") or "NEWSJACK AI")},
        "Notes": {"rich_text": _text(post.get("notes"))},
    }


def _plain_text(prop: Mapping[str, Any]) -> str:
    values = prop.get("title") or prop.get("rich_text") or []
    return "".join(item.get("plain_text", "") for item in values)


def _page_to_post(page: Mapping[str, Any]) -> dict[str, Any]:
    props = page.get("properties", {})
    return {
        "page_id": page.get("id", ""),
        "post_title": _plain_text(props.get("Post Title", {})),
        "date": (props.get("Date", {}).get("date") or {}).get("start", ""),
        "time": _plain_text(props.get("Time", {})),
        "topic": _plain_text(props.get("Topic", {})),
        "campaign_angle": _plain_text(props.get("Campaign Angle", {})),
        "linkedin_post": _plain_text(props.get("LinkedIn Post", {})),
        "hashtags": [item.get("name", "") for item in props.get("Hashtags", {}).get("multi_select", [])],
        "status": (props.get("Status", {}).get("select") or {}).get("name", ""),
        "source_opportunity": _plain_text(props.get("Source Opportunity", {})),
        "approval": bool(props.get("Approval", {}).get("checkbox", False)),
        "linkedin_url": props.get("LinkedIn URL", {}).get("url", "") or "",
        "brand": _plain_text(props.get("Brand", {})),
        "created_by": _plain_text(props.get("Created By", {})),
        "notes": _plain_text(props.get("Notes", {})),
    }


def create_linkedin_calendar_database() -> dict[str, Any]:
    """Create the GamePulse AI LinkedIn calendar database in Notion."""
    client = _notion_client()
    parent_page_id = env_value("NOTION_PARENT_PAGE_ID")
    if client is None or not parent_page_id:
        return _safe_response(False, "Set NOTION_API_KEY and NOTION_PARENT_PAGE_ID to create the Notion database.")
    try:
        database = client.databases.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            title=[{"type": "text", "text": {"content": DATABASE_TITLE}}],
            properties=_database_properties(),
        )
        database_id = database["id"]
        os.environ["NOTION_LINKEDIN_DATABASE_ID"] = database_id
        logger.info("Created Notion LinkedIn calendar database", extra={"event": "notion_database_created"})
        schema = ensure_linkedin_calendar_schema(database_id)
        return _safe_response(
            schema.get("ok", True),
            "Notion database created.",
            database_id=schema.get("database_id", database_id),
            data_source_id=schema.get("data_source_id", ""),
            database=schema.get("database", database),
            data_source=schema.get("data_source"),
            property_names=schema.get("property_names", _property_names(database)),
        )
    except Exception as exc:
        logger.exception("Could not create Notion database")
        return _safe_response(False, f"Could not create Notion database: {exc.__class__.__name__}")


def get_or_create_linkedin_calendar_database() -> dict[str, Any]:
    """Return one Notion calendar database, creating it only when no exact match exists."""
    client = _notion_client()
    if client is None:
        return _safe_response(False, "Set NOTION_API_KEY to connect to Notion.", property_names=[])
    database_id = env_value("NOTION_LINKEDIN_DATABASE_ID")
    if database_id:
        schema = ensure_linkedin_calendar_schema(database_id)
        message = "Using configured Notion database." if schema.get("ok") else schema.get("message", "Schema check failed.")
        return {**schema, "message": message}
    existing = _search_linkedin_calendar_database(client)
    if existing:
        database_id = existing["database_id"]
        os.environ["NOTION_LINKEDIN_DATABASE_ID"] = database_id
        schema = ensure_linkedin_calendar_schema(database_id, existing.get("data_source_id"))
        message = "Connected to existing Notion database." if schema.get("ok") else schema.get("message", "Schema check failed.")
        return {**schema, "message": message}
    return create_linkedin_calendar_database()


def create_notion_calendar_post(post: Mapping[str, Any]) -> dict[str, Any]:
    """Create a LinkedIn calendar post page in Notion."""
    client = _notion_client()
    database = get_or_create_linkedin_calendar_database()
    if client is None or not database.get("ok"):
        return _safe_response(False, database.get("message", "Notion is not configured."))
    try:
        missing = [name for name in REQUIRED_PROPERTY_TYPES if name not in database.get("property_names", [])]
        if missing:
            database = ensure_linkedin_calendar_schema(database["database_id"], database.get("data_source_id"))
            missing = [name for name in REQUIRED_PROPERTY_TYPES if name not in database.get("property_names", [])]
        if missing:
            return _safe_response(False, f"Notion database is missing required properties: {', '.join(missing)}")
        parent = {"data_source_id": database["data_source_id"]} if database.get("data_source_id") else {"database_id": database["database_id"]}
        page = client.pages.create(parent=parent, properties=_post_properties(post))
        logger.info("Created Notion calendar post", extra={"event": "notion_post_created"})
        return _safe_response(True, "Post pushed to Notion.", page_id=page["id"], page=page)
    except Exception as exc:
        logger.exception("Could not create Notion calendar post")
        return _safe_response(False, f"Could not create Notion calendar post: {exc.__class__.__name__}")


def load_notion_calendar_posts() -> dict[str, Any]:
    """Load LinkedIn calendar posts from Notion."""
    client = _notion_client()
    database = get_or_create_linkedin_calendar_database()
    if client is None or not database.get("ok"):
        return _safe_response(False, database.get("message", "Notion is not configured."), posts=[])
    try:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            if database.get("data_source_id"):
                kwargs = {"data_source_id": database["data_source_id"]}
                query_call = client.data_sources.query
            else:
                kwargs = {"database_id": database["database_id"]}
                query_call = client.databases.query
            if cursor:
                kwargs["start_cursor"] = cursor
            response = query_call(**kwargs)
            results.extend(_page_to_post(page) for page in response.get("results", []))
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
        logger.info("Loaded Notion calendar posts", extra={"event": "notion_posts_loaded", "count": len(results)})
        return _safe_response(True, "Loaded Notion posts.", posts=results)
    except Exception as exc:
        logger.exception("Could not load Notion calendar posts")
        return _safe_response(False, f"Could not load Notion posts: {exc.__class__.__name__}", posts=[])


def update_notion_post_status(page_id: str, status: str) -> dict[str, Any]:
    """Update a Notion calendar post status."""
    if status not in STATUS_OPTIONS:
        return _safe_response(False, f"Unsupported status: {status}")
    return _update_page_properties(page_id, {"Status": {"select": {"name": status}}}, f"Status updated to {status}.")


def update_notion_post_approval(page_id: str, approved: bool) -> dict[str, Any]:
    """Update a Notion calendar post approval checkbox."""
    return _update_page_properties(page_id, {"Approval": {"checkbox": approved}}, "Approval updated.")


def update_notion_post_content(page_id: str, post_text: str) -> dict[str, Any]:
    """Update a Notion calendar post's LinkedIn copy."""
    return _update_page_properties(page_id, {"LinkedIn Post": {"rich_text": _text(post_text)}}, "LinkedIn post updated.")


def update_notion_post_notes(page_id: str, notes: str) -> dict[str, Any]:
    """Update a Notion calendar post's notes."""
    return _update_page_properties(page_id, {"Notes": {"rich_text": _text(notes)}}, "Notes updated.")


def update_notion_post_publish_result(
    page_id: str,
    status: str,
    linkedin_url: str | None = None,
    error_message: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Update Notion fields after a LinkedIn publishing attempt."""
    if status not in STATUS_OPTIONS:
        return _safe_response(False, f"Unsupported status: {status}", page_id=page_id, status=status)
    if not page_id:
        return _safe_response(False, "Set NOTION_API_KEY and provide a Notion page id.", page_id=page_id, status=status)
    properties: dict[str, Any] = {"Status": {"select": {"name": status}}}
    note_text = error_message or notes or ""
    if note_text:
        properties["Notes"] = {"rich_text": _text(note_text)}
    if linkedin_url:
        properties["LinkedIn URL"] = {"url": linkedin_url}
    result = _update_page_properties(
        page_id,
        properties,
        f"Publish result updated: {status}.",
        optional_properties={"LinkedIn URL", "Notes"},
    )
    return {
        "ok": bool(result.get("ok")),
        "page_id": page_id,
        "status": status,
        "message": result.get("message", ""),
    }


def archive_notion_post(page_id: str) -> dict[str, Any]:
    """Archive a Notion calendar post page."""
    client = _notion_client()
    if client is None:
        return _safe_response(False, "Set NOTION_API_KEY to archive Notion posts.")
    try:
        client.pages.update(page_id=page_id, archived=True)
        logger.info("Archived Notion calendar post", extra={"event": "notion_post_archived"})
        return _safe_response(True, "Post archived.")
    except Exception as exc:
        logger.exception("Could not archive Notion calendar post")
        return _safe_response(False, f"Could not archive post: {exc.__class__.__name__}")


def _update_page_properties(
    page_id: str,
    properties: dict[str, Any],
    message: str,
    optional_properties: set[str] | None = None,
) -> dict[str, Any]:
    client = _notion_client()
    if client is None or not page_id:
        return _safe_response(False, "Set NOTION_API_KEY and provide a Notion page id.")
    optional_properties = optional_properties or set()
    try:
        page = client.pages.update(page_id=page_id, properties=properties)
        logger.info("Updated Notion calendar post", extra={"event": "notion_post_updated"})
        return _safe_response(True, message, page=page)
    except Exception as exc:
        if optional_properties:
            fallback_properties = {
                name: value for name, value in properties.items() if name not in optional_properties
            }
            if fallback_properties != properties:
                try:
                    page = client.pages.update(page_id=page_id, properties=fallback_properties)
                    logger.warning(
                        "Updated Notion post without optional properties",
                        extra={"event": "notion_post_updated_without_optional"},
                    )
                    skipped = ", ".join(sorted(set(properties) - set(fallback_properties)))
                    return _safe_response(True, f"{message} Skipped optional properties: {skipped}.", page=page)
                except Exception:
                    pass
        logger.exception("Could not update Notion calendar post")
        return _safe_response(False, f"Could not update Notion post: {exc.__class__.__name__}")
