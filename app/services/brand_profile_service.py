"""Brand profile CRUD, persistence, and AI-assisted website profiling."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROFILE_DIR, settings
from app.models import BrandProfile
from app.services.llm_service import generate_json
from app.services.mongodb_service import get_collection

logger = logging.getLogger(__name__)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:60] or uuid.uuid4().hex[:12]


def _profile_path(profile_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", profile_id)
    if not safe_id:
        raise ValueError("Invalid profile id")
    return PROFILE_DIR / f"{safe_id}.json"


def save_brand_profile(profile: BrandProfile | dict[str, Any]) -> BrandProfile:
    model = profile if isinstance(profile, BrandProfile) else BrandProfile.model_validate(profile)
    model.id = model.id or f"{_slug(model.brand_name)}-{uuid.uuid4().hex[:8]}"
    model.updated_at = datetime.now(timezone.utc)
    if _mongodb_enabled():
        try:
            collection = _profiles_collection()
            collection.update_one(
                {"id": model.id},
                {"$set": _profile_document(model)},
                upsert=True,
            )
            logger.info("Brand profile saved to MongoDB", extra={"event": "brand_saved", "brand": model.brand_name})
            return model
        except Exception:
            logger.warning("MongoDB profile save failed; falling back to local JSON", exc_info=True)
    path = _profile_path(model.id)
    temp = path.with_suffix(".tmp")
    temp.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    temp.replace(path)
    logger.info("Brand profile saved", extra={"event": "brand_saved", "brand": model.brand_name})
    return model


def create_brand_profile(payload: dict[str, Any]) -> BrandProfile:
    return save_brand_profile(BrandProfile.model_validate(payload))


def update_brand_profile(profile_id: str, payload: dict[str, Any]) -> BrandProfile:
    current = load_brand_profile(profile_id)
    merged = current.model_dump()
    merged.update(payload)
    merged.update({"id": profile_id, "created_at": current.created_at})
    return save_brand_profile(merged)


def load_brand_profile(profile_id: str) -> BrandProfile:
    if _mongodb_enabled():
        try:
            document = _profiles_collection().find_one({"id": profile_id})
            if document:
                return _profile_from_document(document)
        except Exception:
            logger.warning("MongoDB profile load failed; falling back to local JSON", exc_info=True)
    path = _profile_path(profile_id)
    if not path.exists():
        raise FileNotFoundError(f"Brand profile '{profile_id}' was not found")
    return BrandProfile.model_validate_json(path.read_text(encoding="utf-8"))


def list_brand_profiles() -> list[BrandProfile]:
    if _mongodb_enabled():
        try:
            mongo_profiles = [
                _profile_from_document(document)
                for document in _profiles_collection().find({}, sort=[("updated_at", -1)])
            ]
            local_profiles = _list_local_profiles()
            merged = _merge_profiles(mongo_profiles, local_profiles)
            _sync_local_profiles_to_mongo(local_profiles, {profile.id for profile in mongo_profiles if profile.id})
            return sorted(merged, key=_profile_sort_key, reverse=True)
        except Exception:
            logger.warning("MongoDB profile list failed; falling back to local JSON", exc_info=True)
    return _list_local_profiles()


def _list_local_profiles() -> list[BrandProfile]:
    profiles: list[BrandProfile] = []
    for path in sorted(PROFILE_DIR.glob("*.json")):
        try:
            profiles.append(BrandProfile.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            logger.exception("Skipping invalid profile file: %s", path)
    return sorted(profiles, key=_profile_sort_key, reverse=True)


def delete_brand_profile(profile_id: str) -> bool:
    deleted = False
    if _mongodb_enabled():
        try:
            deleted = _profiles_collection().delete_one({"id": profile_id}).deleted_count > 0
        except Exception:
            logger.warning("MongoDB profile delete failed; falling back to local JSON", exc_info=True)
    path = _profile_path(profile_id)
    existed = path.exists()
    path.unlink(missing_ok=True)
    return deleted or existed


def generate_brand_profile(scraped_data: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(scraped_data, ensure_ascii=False, default=str)
    fallback = _fallback_from_scrape(scraped_data)
    result = generate_json(
        system_prompt=(
            "You are a senior brand strategist. Return one strict JSON object only. "
            "Do not invent claims unsupported by the supplied website evidence."
        ),
        user_prompt=(
            "Create a profile with keys brand_name, industry, target_audience, tone, goals, "
            "keywords, competitors, products, website, brand_summary.\n\n"
            f"Website evidence:\n{text[:12000]}"
        ),
        fallback=fallback,
        cache_key=f"brand-profile:{text[:4000]}",
    )
    return BrandProfile.model_validate({**fallback, **result}).model_dump(mode="json")


def _fallback_from_scrape(data: dict[str, Any]) -> dict[str, Any]:
    title = str(data.get("title") or "New Brand").split("|")[0].strip()
    description = str(data.get("meta_description") or "")
    headings = [str(item) for item in data.get("headings", [])]
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", " ".join([title, description, *headings]))
    stop = {"with", "your", "from", "that", "this", "about", "shop", "best", "online"}
    keywords = list(dict.fromkeys(token.lower() for token in tokens if token.lower() not in stop))[:12]
    return {
        "brand_name": title or "New Brand",
        "industry": "Consumer Brand",
        "target_audience": "Digital-first consumers",
        "tone": "Professional",
        "goals": "Increase awareness and engagement",
        "keywords": keywords,
        "competitors": [],
        "products": headings[:6],
        "website": data.get("url"),
        "brand_summary": description or f"{title} is a consumer-facing brand.",
    }


def _profiles_collection():
    collection = get_collection("brand_profiles")
    collection.create_index("id", unique=True)
    collection.create_index("updated_at")
    return collection


def _mongodb_enabled() -> bool:
    return bool(getattr(settings, "mongodb_enabled", False))


def _profile_document(model: BrandProfile) -> dict[str, Any]:
    document = model.model_dump(mode="python")
    document["id"] = model.id
    return document


def _profile_from_document(document: dict[str, Any]) -> BrandProfile:
    clean = dict(document)
    clean.pop("_id", None)
    return BrandProfile.model_validate(clean)


def _merge_profiles(*groups: list[BrandProfile]) -> list[BrandProfile]:
    merged: dict[str, BrandProfile] = {}
    for group in groups:
        for profile in group:
            key = profile.id or _slug(profile.brand_name)
            existing = merged.get(key)
            if not existing or _profile_sort_key(profile) >= _profile_sort_key(existing):
                merged[key] = profile
    return list(merged.values())


def _sync_local_profiles_to_mongo(local_profiles: list[BrandProfile], mongo_ids: set[str]) -> None:
    if not local_profiles:
        return
    collection = _profiles_collection()
    for profile in local_profiles:
        if not profile.id or profile.id in mongo_ids:
            continue
        try:
            collection.update_one({"id": profile.id}, {"$set": _profile_document(profile)}, upsert=True)
        except Exception:
            logger.warning("Could not sync local profile '%s' to MongoDB", profile.id, exc_info=True)


def _profile_sort_key(profile: BrandProfile) -> datetime:
    value = profile.updated_at
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
