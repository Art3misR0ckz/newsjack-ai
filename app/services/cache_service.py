"""Thread-safe local JSON cache with TTL and atomic writes."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from app.config import CACHE_DIR, settings

T = TypeVar("T")
_lock = threading.RLock()


def _path(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    directory = CACHE_DIR / namespace
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.json"


def get_cached(namespace: str, key: str, ttl_seconds: int | None = None) -> Any | None:
    path = _path(namespace, key)
    if not path.exists():
        return None
    ttl = ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
    try:
        with _lock:
            payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - float(payload["created_at"]) > ttl:
            path.unlink(missing_ok=True)
            return None
        return payload["value"]
    except (OSError, ValueError, KeyError, TypeError):
        path.unlink(missing_ok=True)
        return None


def set_cached(namespace: str, key: str, value: Any) -> Any:
    path = _path(namespace, key)
    temp = path.with_suffix(".tmp")
    payload = {"created_at": time.time(), "value": value}
    with _lock:
        temp.write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
        temp.replace(path)
    return value


def cached_call(namespace: str, key: str, producer: Callable[[], T], ttl_seconds: int | None = None) -> T:
    cached = get_cached(namespace, key, ttl_seconds)
    if cached is not None:
        return cached
    return set_cached(namespace, key, producer())


def clear_cache(namespace: str | None = None) -> int:
    root = CACHE_DIR / namespace if namespace else CACHE_DIR
    files = list(root.rglob("*.json")) if root.exists() else []
    for file in files:
        file.unlink(missing_ok=True)
    return len(files)
