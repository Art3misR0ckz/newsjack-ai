"""Central application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "app" / "data"
RUNTIME_DIR = ROOT_DIR / ".newsjack"
CACHE_DIR = RUNTIME_DIR / "cache"
PROFILE_DIR = RUNTIME_DIR / "brands"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "NEWSJACK AI"
    environment: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    serpapi_key: str = os.getenv("SERPAPI_KEY", "")
    newsapi_key: str = os.getenv("NEWS_API_KEY", "")
    trend_geo: str = os.getenv("SERPAPI_GEO", "IN")
    news_country: str = os.getenv("NEWS_COUNTRY", "in")
    cache_ttl_seconds: int = _int("CACHE_TTL_SECONDS", 1800)
    request_timeout_seconds: int = _int("REQUEST_TIMEOUT_SECONDS", 20)
    max_trends: int = _int("MAX_TRENDS", 12)
    enable_llm_relevance: bool = _bool("ENABLE_LLM_RELEVANCE", False)


settings = Settings()

for directory in (RUNTIME_DIR, CACHE_DIR, PROFILE_DIR):
    directory.mkdir(parents=True, exist_ok=True)
