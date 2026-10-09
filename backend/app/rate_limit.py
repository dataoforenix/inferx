"""Small in-memory, per-client sliding-window rate limiter (no dependencies).

Good enough for a single-process demo server. State lives in this process only: it resets on
restart and is not shared between workers. Behind a reverse proxy every request may share the
proxy's IP, so set the limit accordingly (or 0 to disable).
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from typing import Callable

WINDOW_SECONDS = 60.0
LIMITED_PATHS = frozenset({"/api/analyze", "/api/analyze/confirm"})


class RateLimiter:
    def __init__(self, limit_per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.limit = limit_per_minute
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self.limit > 0

    def check(self, key: str) -> tuple[bool, int]:
        """Record a request for key. Returns (allowed, retry_after_seconds)."""
        if not self.enabled:
            return True, 0
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= self.limit:
                return False, max(1, math.ceil(hits[0] + WINDOW_SECONDS - now))
            hits.append(now)
            if len(self._hits) > 10_000:  # bound memory: drop clients with no recent hits
                self._hits = {k: v for k, v in self._hits.items() if v and v[-1] > now - WINDOW_SECONDS}
            return True, 0
