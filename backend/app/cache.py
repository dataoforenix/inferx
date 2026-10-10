"""Optional SQLite response cache and search counter (Python's built-in sqlite3 only).

Fail-open: every database problem (missing directory, locked or corrupt file, disk full, ...) is logged and
ignored, and the request continues exactly as if there were no cache.

Privacy: no raw image is ever stored, only a SHA-256 hash of the sanitised image bytes as part of the cache key.
The search counter stores category / HS code, product names and counts: no IP address, no request text.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("sannaha.cache")

CONNECT_TIMEOUT_SECONDS = 0.5  # a locked database must not slow the request down noticeably

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyze_cache (
    key TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    response_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS searches (
    key TEXT PRIMARY KEY,
    category_id TEXT,
    hs6_guess TEXT,
    name_en TEXT NOT NULL,
    name_ar TEXT NOT NULL,
    count INTEGER NOT NULL,
    last_seen REAL NOT NULL
);
"""


def normalize_text(text: str | None) -> str:
    return " ".join((text or "").casefold().split())


def cache_key(text: str | None, image_sha256: str | None, language: str) -> str:
    raw = json.dumps([normalize_text(text), image_sha256 or "", language], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AnalysisCache:
    def __init__(self, path: Path, ttl_seconds: float, clock: Callable[[], float] = time.time):
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self.clock = clock

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=CONNECT_TIMEOUT_SECONDS)
        conn.executescript(_SCHEMA)
        return conn

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("SELECT created_at, response_json FROM analyze_cache WHERE key = ?", (key,)).fetchone()
            if row is None or self.clock() - row[0] >= self.ttl_seconds:
                return None
            return json.loads(row[1])
        except Exception as exc:  # fail-open
            logger.warning("cache get failed (ignored): %s", type(exc).__name__)
            return None

    def put(self, key: str, response: dict[str, Any]) -> None:
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute("INSERT OR REPLACE INTO analyze_cache (key, created_at, response_json) VALUES (?, ?, ?)",
                             (key, self.clock(), json.dumps(response, ensure_ascii=False)))
        except Exception as exc:  # fail-open
            logger.warning("cache put failed (ignored): %s", type(exc).__name__)

    def record_search(self, category_id: str | None, hs6_guess: str | None, name_en: str, name_ar: str) -> None:
        key = f"category:{category_id}" if category_id else f"hs6:{hs6_guess}"
        try:
            with closing(self._connect()) as conn, conn:
                conn.execute(
                    "INSERT INTO searches (key, category_id, hs6_guess, name_en, name_ar, count, last_seen) "
                    "VALUES (?, ?, ?, ?, ?, 1, ?) ON CONFLICT(key) DO UPDATE SET count = count + 1, "
                    "name_en = excluded.name_en, name_ar = excluded.name_ar, last_seen = excluded.last_seen",
                    (key, category_id, hs6_guess, name_en, name_ar, self.clock()))
        except Exception as exc:  # fail-open
            logger.warning("search count failed (ignored): %s", type(exc).__name__)

    def top_searches(self, limit: int) -> list[dict[str, Any]]:
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute("SELECT category_id, hs6_guess, name_en, name_ar, count FROM searches "
                                    "ORDER BY count DESC, last_seen DESC LIMIT ?", (limit,)).fetchall()
            return [{"category_id": r[0], "hs6_guess": r[1], "name_en": r[2], "name_ar": r[3], "count": r[4]}
                    for r in rows]
        except Exception as exc:  # fail-open
            logger.warning("top searches failed (ignored): %s", type(exc).__name__)
            return []
