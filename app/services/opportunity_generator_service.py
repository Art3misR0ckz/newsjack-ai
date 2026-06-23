"""AI campaign generator with useful deterministic output when offline."""

from __future__ import annotations

import json
from typing import Any, Mapping

from app.models import Campaign
from app.services.llm_service import generate_json


def generate_campaign(brand: Mapping[str, Any], opportunity: Mapping[str, Any]) -> dict[str, Any]:
    topic = str(opportunity.get("topic", "the trend"))
    brand_name = str(brand.get("brand_name", "the brand"))
    angle = str(opportunity.get("recommended_angle", "timely perspective")).replace("_", " ")
    fallback = {
        "campaign_angle": f"{brand_name}'s {angle.title()} on {topic}",
        "why_it_matters": (
            f"{topic} is receiving attention now and offers a natural way to connect "
            f"{brand_name}'s expertise with its audience."
        ),
        "confidence": int(opportunity.get("final_score", 65)),
        "recommended_channels": ["LinkedIn", "Instagram", "X"],
        "marketing_insight": str(opportunity.get("reason", "Timely relevance can earn attention.")),
        "suggested_content": [
            "A rapid-response point of view",
            "A practical carousel or checklist",
            "A short audience question or poll",
        ],
    }
    result = generate_json(
        system_prompt=(
            "You are an experienced, brand-safe campaign strategist. Return strict JSON only. "
            "Do not exploit tragedy, speculate, or imply unsupported brand involvement."
        ),
        user_prompt=(
            "Generate keys campaign_angle, why_it_matters, confidence, recommended_channels, "
            "marketing_insight, suggested_content.\n\n"
            f"Brand: {json.dumps(dict(brand), default=str)}\n"
            f"Opportunity: {json.dumps(dict(opportunity), default=str)}"
        ),
        fallback=fallback,
        cache_key=f"campaign:{brand_name}:{topic}:{opportunity.get('final_score', 0)}",
    )
    return Campaign.model_validate({**fallback, **result}).model_dump(mode="json")
