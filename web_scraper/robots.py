"""robots.txt fetching and caching.

A tiny wrapper on top of ``urllib.robotparser`` that caches one parser per
host so a long-running service doesn't refetch robots.txt on every request.
A robots.txt that cannot be fetched is treated as *permissive* — this matches
the default behaviour of well-known crawlers and avoids breaking on sites
that simply don't ship a robots file.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from urllib import robotparser
from urllib.parse import urlparse


class RobotsChecker:
    def __init__(
        self,
        user_agent: str,
        fetcher: Callable[[str], robotparser.RobotFileParser] | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._fetcher = fetcher or self._default_fetcher
        self._cache: dict[str, robotparser.RobotFileParser] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _default_fetcher(robots_url: str) -> robotparser.RobotFileParser:
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        try:
            rp.read()
        except Exception:
            # Network failure / 404 → behave as permissive.
            rp.parse([])
        return rp

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.netloc:
            return True
        host_key = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            rp = self._cache.get(host_key)
            if rp is None:
                rp = self._fetcher(f"{host_key}/robots.txt")
                self._cache[host_key] = rp
        try:
            return rp.can_fetch(self._user_agent, url)
        except Exception:
            return True
