"""Project-root environment loading and safe configuration reporting."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT_DIR / ".env"

ENV_ALIASES = {
    "NOTION_API_KEY": ("NOTION_TOKEN",),
}


def load_project_env() -> None:
    """Load `.env` from the repository root and normalize supported aliases."""
    load_dotenv(ENV_PATH, override=False)
    for primary, aliases in ENV_ALIASES.items():
        if os.getenv(primary):
            continue
        for alias in aliases:
            value = os.getenv(alias)
            if value:
                os.environ[primary] = value
                break


def env_value(name: str, default: str = "") -> str:
    """Return a stripped environment value after loading the project `.env`."""
    load_project_env()
    return os.getenv(name, default).strip()


def env_presence_report(names: Iterable[str]) -> dict[str, bool]:
    """Return debug-safe environment presence flags without exposing secret values."""
    load_project_env()
    return {name: bool(os.getenv(name, "").strip()) for name in names}


def missing_env(names: Iterable[str]) -> list[str]:
    """Return names that are empty after root `.env` loading and alias normalization."""
    report = env_presence_report(names)
    return [name for name, present in report.items() if not present]
