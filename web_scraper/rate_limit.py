"""Per-host rate limiter.

Tracks the timestamp of the most recent request to each host and sleeps the
caller just long enough to honour ``min_interval`` seconds between calls.
Thread-safe — multiple workers can share one limiter.
"""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from urllib.parse import urlparse


class RateLimiter:
    """Minimal per-host rate limiter."""

    def __init__(
        self,
        min_interval: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._min_interval = max(0.0, float(min_interval))
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._last_request: dict[str, float] = {}

    def wait(self, url: str) -> float:
        """Block until the host is allowed to be hit again. Returns slept seconds."""
        if self._min_interval <= 0:
            return 0.0

        host = urlparse(url).netloc.lower()
        if not host:
            return 0.0

        with self._lock:
            now = self._clock()
            last = self._last_request.get(host)
            if last is None:
                self._last_request[host] = now
                return 0.0
            elapsed = now - last
            wait_for = self._min_interval - elapsed
            if wait_for <= 0:
                self._last_request[host] = now
                return 0.0
            self._last_request[host] = now + wait_for

        self._sleep(wait_for)
        return wait_for
