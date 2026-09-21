"""A tiny TTL cache on disk.

Market data is slow and rate-limited; every provider call goes through here so
that re-running an analysis is instant and works on a plane.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class DiskCache:
    def __init__(self, directory: Path, ttl_seconds: int = 3600) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self.directory / f"{namespace}_{digest}.json"

    def get(self, namespace: str, key: str) -> Any | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() - payload.get("stored_at", 0) > self.ttl_seconds:
            return None
        return payload.get("value")

    def set(self, namespace: str, key: str, value: Any) -> None:
        path = self._path(namespace, key)
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps({"stored_at": time.time(), "value": value}))
            tmp.replace(path)
        except (OSError, TypeError):
            # A cache miss is always survivable; never fail the request over it.
            tmp.unlink(missing_ok=True)

    def get_or_set(self, namespace: str, key: str, factory: Callable[[], T]) -> T:
        hit = self.get(namespace, key)
        if hit is not None:
            return hit
        value = factory()
        self.set(namespace, key, value)
        return value

    def clear(self) -> int:
        removed = 0
        for path in self.directory.glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        return removed
