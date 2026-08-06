"""Public scraping API.

Composes the HTTP fetcher (with retries + rate limiting + robots.txt),
the HTML parser, and the storage layer behind a single ``Scraper`` class
and a convenience ``scrape_page`` function for the common case.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests

from web_scraper.config import Config
from web_scraper.parser import parse_html
from web_scraper.rate_limit import RateLimiter
from web_scraper.robots import RobotsChecker
from web_scraper.storage import init_db, save_result

logger = logging.getLogger(__name__)


class RobotsDisallowedError(Exception):
    """Raised when robots.txt forbids fetching a URL."""


# Retry on common transient failures and on 5xx / 429.
_RETRY_STATUS = {429, 500, 502, 503, 504}


class Scraper:
    """Reusable scraper bundling config, rate limit state, and robots cache."""

    def __init__(
        self,
        config: Config | None = None,
        session: requests.Session | None = None,
        rate_limiter: RateLimiter | None = None,
        robots: RobotsChecker | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config or Config()
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", self.config.user_agent)
        self.rate_limiter = rate_limiter or RateLimiter(
            self.config.rate_limit_per_host
        )
        self.robots = robots or RobotsChecker(self.config.user_agent)
        self._sleep = sleep

    # ── HTTP ──────────────────────────────────────────────────────────────

    def _fetch(self, url: str) -> str:
        """Fetch ``url`` with retry/backoff. Returns the response text."""
        cfg = self.config
        last_exc: Exception | None = None
        for attempt in range(cfg.max_retries + 1):
            self.rate_limiter.wait(url)
            try:
                response = self.session.get(
                    url,
                    timeout=cfg.request_timeout,
                    stream=True,
                )
            except requests.RequestException as exc:
                last_exc = exc
                logger.info("fetch attempt %d failed for %s: %s",
                            attempt + 1, url, exc)
            else:
                if response.status_code in _RETRY_STATUS:
                    logger.info("retryable status %d for %s (attempt %d)",
                                response.status_code, url, attempt + 1)
                    response.close()
                    last_exc = requests.HTTPError(
                        f"HTTP {response.status_code}", response=response
                    )
                else:
                    response.raise_for_status()
                    return self._read_capped(response)

            if attempt < cfg.max_retries:
                self._sleep(cfg.backoff_factor * (2 ** attempt))

        assert last_exc is not None
        raise last_exc

    def _read_capped(self, response: requests.Response) -> str:
        """Read response body, refusing to buffer more than ``max_response_bytes``."""
        cap = self.config.max_response_bytes
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_content(chunk_size=8192):
            if not chunk:
                continue
            total += len(chunk)
            if total > cap:
                response.close()
                raise ValueError(
                    f"Response exceeded max_response_bytes ({cap} bytes)"
                )
            chunks.append(chunk)
        raw = b"".join(chunks)
        encoding = response.encoding or response.apparent_encoding or "utf-8"
        return raw.decode(encoding, errors="replace")

    # ── Public API ────────────────────────────────────────────────────────

    def scrape(self, url: str, *, persist: bool = True) -> dict[str, Any]:
        """Scrape one URL and return structured data.

        On failure, returns ``{"error": "..."}`` rather than raising — this
        keeps the HTTP layer simple and mirrors the original behaviour.
        """
        try:
            if self.config.respect_robots and not self.robots.allowed(url):
                return {
                    "error": "Blocked by robots.txt",
                    "url": url,
                }
            html = self._fetch(url)
            result = parse_html(html, url, self.config)
            if persist:
                save_result(self.config.db_path, result)
            return result
        except requests.exceptions.Timeout:
            return {"error": f"Request timed out after {self.config.request_timeout}s",
                    "url": url}
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", "?")
            return {"error": f"HTTP {status}", "url": url}
        except requests.exceptions.RequestException as exc:
            return {"error": f"Network error: {exc}", "url": url}
        except ValueError as exc:
            return {"error": str(exc), "url": url}
        except Exception as exc:
            logger.exception("Unexpected error scraping %s", url)
            return {"error": f"Unexpected error: {exc}", "url": url}


# ── Module-level convenience for backwards compatibility ──────────────────

_DEFAULT: Scraper | None = None


def _default_scraper() -> Scraper:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = Scraper(Config.from_env())
    return _DEFAULT


def scrape_page(url: str) -> dict[str, Any]:
    """One-shot scrape using a process-wide default ``Scraper``."""
    return _default_scraper().scrape(url)


def ensure_db() -> None:
    """Initialise the default DB. Safe to call repeatedly."""
    init_db(_default_scraper().config.db_path)
