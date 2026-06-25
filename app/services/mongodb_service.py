"""MongoDB Atlas connection helpers for NEWSJACK AI."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import settings


@lru_cache(maxsize=1)
def get_mongo_client() -> MongoClient:
    """Return a cached MongoDB client configured for Atlas."""

    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is not configured")
    return MongoClient(
        settings.mongodb_uri,
        serverSelectionTimeoutMS=settings.request_timeout_seconds * 1000,
        connectTimeoutMS=settings.request_timeout_seconds * 1000,
    )


def get_database() -> Database:
    return get_mongo_client()[settings.mongodb_database]


def get_collection(name: str) -> Collection:
    return get_database()[name]


def ping_mongodb() -> dict[str, Any]:
    """Return a safe health payload without exposing credentials."""

    mongodb_enabled = getattr(settings, "mongodb_enabled", False)
    mongodb_uri = getattr(settings, "mongodb_uri", "")
    mongodb_database = getattr(settings, "mongodb_database", "newsjack_ai")
    if not mongodb_enabled:
        return {"enabled": False, "connected": False, "mode": "local_json_fallback"}
    if not mongodb_uri:
        return {"enabled": True, "connected": False, "mode": "missing_uri"}
    try:
        get_database().command("ping")
        return {"enabled": True, "connected": True, "database": mongodb_database}
    except Exception as exc:
        return {
            "enabled": True,
            "connected": False,
            "database": mongodb_database,
            "error": exc.__class__.__name__,
        }
