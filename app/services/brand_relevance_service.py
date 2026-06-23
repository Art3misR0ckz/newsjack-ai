"""Brand relevance scoring for trend opportunities.

This module evaluates how well a trend opportunity fits a brand profile using
an OpenRouter LLM, with strong validation and deterministic fallback behavior.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Mapping, Optional

from dotenv import load_dotenv
from openai import OpenAI

from app.config import settings

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL = os.getenv("OPENROUTER_BRAND_RELEVANCE_MODEL", os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free"))
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "https://newsjack.ai")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "NEWSJACK AI")

FALLBACK_RESULT: Dict[str, Any] = {
    "relevance_score": 50,
    "audience_overlap": 50,
    "newsjack_potential": 50,
    "reason": "Fallback response",
    "recommended_angle": "informative",
}

ALLOWED_ANGLES = {
    "informative",
    "educational",
    "inspirational",
    "humorous",
    "empathetic",
    "promotional",
    "thought_leadership",
    "actionable",
}


def score_brand_relevance(brand_profile: Mapping[str, Any], opportunity: Mapping[str, Any]) -> Dict[str, Any]:
    """Score a trend opportunity against a brand profile.

    Returns a normalized result with the topic plus relevance, audience overlap,
    newsjack potential, reason, and recommended angle.
    """

    topic = _extract_topic(opportunity)

    if not OPENROUTER_API_KEY or not settings.enable_llm_relevance:
        return _result_with_topic(topic, _heuristic_scores(brand_profile, opportunity))

    try:
        response_text = _call_openrouter(brand_profile, opportunity)
        parsed = _parse_llm_response(response_text)
        if not parsed:
            logger.warning("Empty or invalid brand relevance response for topic '%s'", topic)
            return _result_with_topic(topic, FALLBACK_RESULT)

        normalized = _normalize_response(parsed)
        heuristic = _heuristic_scores(brand_profile, opportunity)
        normalized["relevance_score"] = _blend_scores(normalized["relevance_score"], heuristic["relevance_score"], 0.7)
        normalized["audience_overlap"] = _blend_scores(normalized["audience_overlap"], heuristic["audience_overlap"], 0.65)
        normalized["newsjack_potential"] = _blend_scores(normalized["newsjack_potential"], heuristic["newsjack_potential"], 0.7)
        normalized["recommended_angle"] = _resolve_angle(normalized["recommended_angle"], heuristic["recommended_angle"])
        normalized["topic"] = topic
        return normalized
    except Exception:
        logger.exception("Brand relevance scoring failed for topic '%s'", topic)
        return _result_with_topic(topic, _heuristic_scores(brand_profile, opportunity))


def _call_openrouter(brand_profile: Mapping[str, Any], opportunity: Mapping[str, Any]) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=OPENROUTER_API_KEY)

    prompt = _build_prompt(brand_profile, opportunity)
    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=500,
        extra_headers={
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
    )

    content = response.choices[0].message.content if response.choices else None
    return (content or "").strip()


def _build_prompt(brand_profile: Mapping[str, Any], opportunity: Mapping[str, Any]) -> str:
    return f"""
You are scoring whether a news trend is relevant to a specific brand.

Brand profile:
{json.dumps(dict(brand_profile), ensure_ascii=True, indent=2)}

Trend opportunity:
{json.dumps(dict(opportunity), ensure_ascii=True, indent=2)}

Assess:
- How relevant is this topic to the brand?
- Is there audience overlap?
- Is there a marketing opportunity?
- Can this trend be used for newsjacking?

Return ONLY valid JSON using this schema:
{{
  "relevance_score": 0,
  "audience_overlap": 0,
  "newsjack_potential": 0,
  "reason": "",
  "recommended_angle": ""
}}

Scoring rules:
- Use integers from 0 to 100.
- Be conservative when the brand and topic only weakly intersect.
- Prefer a clear, practical angle that a marketing team could execute.
- Recommended angle must be one of: {", ".join(sorted(ALLOWED_ANGLES))}.
""".strip()


def _parse_llm_response(response_text: str) -> Dict[str, Any]:
    if not response_text:
        return {}

    cleaned = response_text.strip()
    cleaned = cleaned.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}


def _normalize_response(payload: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(FALLBACK_RESULT)
    result["relevance_score"] = _clamp_score(payload.get("relevance_score", result["relevance_score"]))
    result["audience_overlap"] = _clamp_score(payload.get("audience_overlap", result["audience_overlap"]))
    result["newsjack_potential"] = _clamp_score(payload.get("newsjack_potential", result["newsjack_potential"]))
    result["reason"] = _normalize_text(payload.get("reason", result["reason"])) or result["reason"]

    angle = _normalize_text(payload.get("recommended_angle", result["recommended_angle"]))
    angle = angle.lower().replace(" ", "_")
    if angle not in ALLOWED_ANGLES:
        angle = FALLBACK_RESULT["recommended_angle"]
    result["recommended_angle"] = angle
    return result


def _heuristic_scores(brand_profile: Mapping[str, Any], opportunity: Mapping[str, Any]) -> Dict[str, Any]:
    brand_name = _normalize_text(brand_profile.get("brand_name", ""))
    industry = _normalize_text(brand_profile.get("industry", ""))
    audience = _normalize_text(brand_profile.get("target_audience", ""))
    goals = _normalize_text(brand_profile.get("goals", ""))

    topic = _extract_topic(opportunity)
    summary = _normalize_text(opportunity.get("summary", ""))
    combined_text = f"{brand_name} {industry} {audience} {goals} {topic} {summary}".lower()

    relevance = 20
    audience_overlap = 20
    newsjack_potential = 20
    angle = "informative"

    if any(keyword in combined_text for keyword in ["fitness", "gym", "workout", "training", "protein", "muscle", "nutrition"]):
        relevance += 30
        audience_overlap += 35
        newsjack_potential += 15

    if any(keyword in combined_text for keyword in ["athlete", "sports", "cricket", "football", "soccer", "world cup", "ipl"]):
        relevance += 25
        audience_overlap += 20
        newsjack_potential += 20
        angle = "inspirational"

    if any(keyword in combined_text for keyword in ["launch", "product", "release", "announcement", "shoe", "shoes", "footwear"]):
        relevance += 20
        newsjack_potential += 20

    if any(keyword in combined_text for keyword in ["ai", "openai", "iphone", "apple", "tech"]):
        relevance += 5
        audience_overlap += 5
        newsjack_potential += 10
        if angle == "informative":
            angle = "educational"

    if "virat kohli" in combined_text or "one8" in combined_text:
        relevance += 35
        audience_overlap += 20
        newsjack_potential += 20
        angle = "inspirational"

    if "world cup" in combined_text or "fifa" in combined_text:
        relevance += 20
        audience_overlap += 15
        newsjack_potential += 20

    if "openai" in combined_text or "product launches" in combined_text:
        newsjack_potential += 10
        if angle == "informative":
            angle = "thought_leadership"

    return {
        "relevance_score": max(0, min(100, relevance)),
        "audience_overlap": max(0, min(100, audience_overlap)),
        "newsjack_potential": max(0, min(100, newsjack_potential)),
        "reason": (
            "Deterministic fallback based on overlap between the brand, audience, "
            "industry, goals, and the current trend."
        ),
        "recommended_angle": angle,
    }


def _blend_scores(llm_score: int, heuristic_score: int, llm_weight: float) -> int:
    heuristic_weight = 1.0 - llm_weight
    blended = (llm_score * llm_weight) + (heuristic_score * heuristic_weight)
    return _clamp_score(blended)


def _resolve_angle(llm_angle: str, heuristic_angle: str) -> str:
    if llm_angle in ALLOWED_ANGLES:
        return llm_angle
    if heuristic_angle in ALLOWED_ANGLES:
        return heuristic_angle
    return FALLBACK_RESULT["recommended_angle"]


def _extract_topic(opportunity: Mapping[str, Any]) -> str:
    return _normalize_text(
        opportunity.get("topic")
        or opportunity.get("title")
        or opportunity.get("headline")
        or opportunity.get("summary")
        or ""
    )


def _result_with_topic(topic: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(payload)
    result["topic"] = topic
    return result


def _clamp_score(value: Any) -> int:
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 50


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()
