"""OpenRouter JSON client with validation-friendly parsing."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from app.config import settings
from app.services.cache_service import cached_call
from app.services.env_service import env_value

logger = logging.getLogger(__name__)


def generate_json(
    *,
    system_prompt: str,
    user_prompt: str,
    fallback: dict[str, Any],
    cache_key: str,
    temperature: float = 0.2,
) -> dict[str, Any]:
    openrouter_api_key = env_value("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        return fallback
    openrouter_base_url = env_value("OPENROUTER_BASE_URL", settings.openrouter_base_url)
    openrouter_model = env_value("OPENROUTER_MODEL", settings.openrouter_model)

    def produce() -> dict[str, Any]:
        try:
            response = requests.post(
                f"{openrouter_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://newsjack.ai",
                    "X-Title": settings.app_name,
                },
                json={
                    "model": openrouter_model,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                timeout=settings.request_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return _parse_json(content)
        except Exception as exc:
            logger.warning(
                "OpenRouter generation failed; using deterministic fallback: %s",
                exc.__class__.__name__,
                extra={"event": "llm_error"},
            )
            return fallback

    result = cached_call("openrouter", cache_key, produce)
    return result if isinstance(result, dict) else fallback


def _parse_json(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.I | re.M).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response must be a JSON object")
    return parsed
