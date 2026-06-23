"""FastAPI application for NEWSJACK AI."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.logging_config import configure_logging
from app.models import BrandProfile
from app.services.analytics_service import build_analytics
from app.services.brand_profile_service import (
    create_brand_profile,
    delete_brand_profile,
    list_brand_profiles,
    load_brand_profile,
    update_brand_profile,
)
from app.services.competitor_monitor_service import monitor_competitors
from app.services.pipeline_service import add_campaign_assets, discover_and_rank
from app.services.trend_discovery_service import discover_trends

configure_logging()

app = FastAPI(
    title=settings.app_name,
    description="Discover trends. Find opportunities. Generate campaigns.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OpportunityRequest(BaseModel):
    brand_profile: BrandProfile
    limit: int = 8
    generate_assets: bool = False


class CampaignRequest(BaseModel):
    brand_profile: BrandProfile
    opportunity: dict[str, Any]


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "ready", "docs": "/docs"}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "providers": {
            "openrouter": bool(settings.openrouter_api_key),
            "serpapi": bool(settings.serpapi_key),
            "newsapi": bool(settings.newsapi_key),
        },
    }


@app.get("/api/trends")
def trends(limit: int = Query(default=10, ge=1, le=50)) -> list[dict[str, Any]]:
    return discover_trends(limit)


@app.get("/api/brands")
def brands() -> list[dict[str, Any]]:
    return [item.model_dump(mode="json") for item in list_brand_profiles()]


@app.post("/api/brands", status_code=201)
def create_brand(profile: BrandProfile) -> dict[str, Any]:
    return create_brand_profile(profile.model_dump()).model_dump(mode="json")


@app.get("/api/brands/{profile_id}")
def get_brand(profile_id: str) -> dict[str, Any]:
    try:
        return load_brand_profile(profile_id).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.put("/api/brands/{profile_id}")
def update_brand(profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return update_brand_profile(profile_id, payload).model_dump(mode="json")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.delete("/api/brands/{profile_id}")
def delete_brand(profile_id: str) -> dict[str, bool]:
    if not delete_brand_profile(profile_id):
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return {"deleted": True}


@app.post("/api/opportunities")
def opportunities(request: OpportunityRequest) -> list[dict[str, Any]]:
    return discover_and_rank(
        request.brand_profile.model_dump(),
        limit=request.limit,
        generate_assets=request.generate_assets,
    )


@app.post("/api/campaigns/generate")
def campaign(request: CampaignRequest) -> dict[str, Any]:
    return add_campaign_assets(request.brand_profile.model_dump(), request.opportunity)


@app.post("/api/analytics")
def analytics(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    return build_analytics(opportunities)


@app.post("/api/competitors")
def competitors(payload: dict[str, list[str]]) -> list[dict[str, Any]]:
    return monitor_competitors(payload.get("competitors", []))
