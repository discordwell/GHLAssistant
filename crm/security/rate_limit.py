"""In-memory rate limiter for public form submissions."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from ..config import settings


class SlidingWindowRateLimiter:
    """Simple in-memory sliding-window rate limiter."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._blocked_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        window = settings.form_rate_limit_window_seconds
        limit = settings.form_rate_limit_max_submissions
        block_seconds = settings.form_rate_limit_block_seconds

        async with self._lock:
            blocked_until = self._blocked_until.get(key)
            if blocked_until and now < blocked_until:
                return False, max(1, int(blocked_until - now))

            events = self._events[key]
            cutoff = now - window
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, int(events[0] + window - now))
                self._blocked_until[key] = now + block_seconds
                return False, retry_after

            events.append(now)
            return True, 0


form_submission_rate_limiter = SlidingWindowRateLimiter()

