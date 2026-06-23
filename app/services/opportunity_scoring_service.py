"""Opportunity scoring and ranking utilities."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

from dotenv import load_dotenv

from app.services.brand_relevance_service import score_brand_relevance

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_RELEVANCE_WEIGHT = float(os.getenv("FINAL_SCORE_RELEVANCE_WEIGHT", "0.50"))
DEFAULT_NEWSJACK_WEIGHT = float(os.getenv("FINAL_SCORE_NEWSJACK_WEIGHT", "0.25"))
DEFAULT_AUDIENCE_WEIGHT = float(os.getenv("FINAL_SCORE_AUDIENCE_WEIGHT", "0.15"))
DEFAULT_POTENTIAL_WEIGHT = float(os.getenv("FINAL_SCORE_POTENTIAL_WEIGHT", "0.10"))

SOURCE_BASE_SCORES = {
    "google_trends": 50,
    "google_trends_news": 40,
    "technology": 30,
    "sports": 25,
    "seasonal": 20,
    "event": 20,
}

CATEGORY_BONUS_SCORES = {
    "technology": 20,
    "sports": 15,
    "seasonal": 10,
    "health": 10,
}


def score_opportunity(opportunity: Mapping[str, Any]) -> int:
    """Legacy heuristic score for backward compatibility."""

    score = 0
    source = str(opportunity.get("source", ""))
    category = str(opportunity.get("category", ""))

    score += SOURCE_BASE_SCORES.get(source, 0)
    score += CATEGORY_BONUS_SCORES.get(category, 0)

    return score


def calculate_final_opportunity_score(
    relevance_score: int,
    newsjack_score: int,
    audience_overlap: int,
    newsjack_potential: int,
) -> int:
    """Blend brand relevance and opportunity signals into a final 0-100 score."""

    weights_total = (
        DEFAULT_RELEVANCE_WEIGHT
        + DEFAULT_NEWSJACK_WEIGHT
        + DEFAULT_AUDIENCE_WEIGHT
        + DEFAULT_POTENTIAL_WEIGHT
    )
    if weights_total <= 0:
        weights_total = 1.0

    normalized_score = (
        (relevance_score * DEFAULT_RELEVANCE_WEIGHT)
        + (newsjack_score * DEFAULT_NEWSJACK_WEIGHT)
        + (audience_overlap * DEFAULT_AUDIENCE_WEIGHT)
        + (newsjack_potential * DEFAULT_POTENTIAL_WEIGHT)
    ) / weights_total

    return _clamp_score(normalized_score)


def rank_opportunities(
    opportunities: Iterable[Mapping[str, Any]],
    brand_profile: Optional[Mapping[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Rank opportunities with optional brand-aware scoring."""

    ranked: List[Dict[str, Any]] = []

    for opportunity in opportunities:
        opportunity_copy = dict(opportunity)

        if brand_profile:
            brand_relevance = score_brand_relevance(brand_profile, opportunity_copy)
            final_score = calculate_final_opportunity_score(
                brand_relevance.get("relevance_score", 50),
                _clamp_score(opportunity_copy.get("newsjack_score", 0)),
                brand_relevance.get("audience_overlap", 50),
                brand_relevance.get("newsjack_potential", 50),
            )

            opportunity_copy.update(
                {
                    "topic": brand_relevance.get("topic", opportunity_copy.get("topic", "")),
                    "final_score": final_score,
                    "relevance_score": brand_relevance.get("relevance_score", 50),
                    "audience_overlap": brand_relevance.get("audience_overlap", 50),
                    "newsjack_potential": brand_relevance.get("newsjack_potential", 50),
                    "recommended_angle": brand_relevance.get("recommended_angle", "informative"),
                    "reason": brand_relevance.get("reason", "Fallback response"),
                }
            )
        else:
            opportunity_copy["final_score"] = score_opportunity(opportunity_copy)

        ranked.append(opportunity_copy)

    ranked.sort(key=lambda item: item.get("final_score", 0), reverse=True)
    return ranked


def _clamp_score(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0