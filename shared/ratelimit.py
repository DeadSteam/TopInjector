"""A tiny in-process sliding-window limiter for abuse-prone endpoints (e.g. login).

Good enough for a single app process; a multi-process / multi-host deployment should move
this state into Redis. Keyed by an arbitrary string (we use client IP + e-mail for login).
"""

from __future__ import annotations

import threading
import time


class SlidingWindowLimiter:
    def __init__(self, max_hits: int, window_seconds: float) -> None:
        self.max_hits = max_hits
        self.window = window_seconds
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        return [t for t in self._hits.get(key, []) if now - t < self.window]

    def is_blocked(self, key: str) -> bool:
        """True if ``key`` already has at least ``max_hits`` hits inside the window."""
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            self._hits[key] = recent
            return len(recent) >= self.max_hits

    def record(self, key: str) -> None:
        """Count one hit against ``key``."""
        now = time.monotonic()
        with self._lock:
            self._hits[key] = self._recent(key, now) + [now]

    def clear(self, key: str) -> None:
        """Forget a key's history (e.g. after a successful login)."""
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        """Drop all state (used by tests)."""
        with self._lock:
            self._hits.clear()


# Up to 10 failed logins per e-mail+IP every 5 minutes, then 429 until the window clears.
login_limiter = SlidingWindowLimiter(max_hits=10, window_seconds=300)
