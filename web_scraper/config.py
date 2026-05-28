"""Centralised configuration, sourced from environment variables.

All settings have sensible defaults so the service runs out-of-the-box, but
each can be overridden by an env var — convenient for containers, CI, and
production deployments.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the scraper."""

    # HTTP
    request_timeout: float = 10.0
    max_response_bytes: int = 5 * 1024 * 1024  # 5 MiB cap to avoid memory blowups
    user_agent: str = (
        "WebScraper/0.2 (+https://github.com/Gavand1969/web_scraping_service)"
    )

    # Retries
    max_retries: int = 3
    backoff_factor: float = 0.5  # 0.5, 1.0, 2.0 ...

    # Rate limiting (minimum seconds between requests to the same host)
    rate_limit_per_host: float = 1.0

    # Ethics
    respect_robots: bool = True

    # Storage
    db_path: str = "scraped_data.db"

    # Output limits — keep payloads bounded
    max_headings: int = 20
    max_paragraphs: int = 20
    max_links: int = 50
    max_images: int = 20
    max_tables: int = 5

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            request_timeout=_env_float("SCRAPER_TIMEOUT", 10.0),
            max_response_bytes=_env_int("SCRAPER_MAX_BYTES", 5 * 1024 * 1024),
            user_agent=os.environ.get("SCRAPER_USER_AGENT", cls.user_agent),
            max_retries=_env_int("SCRAPER_MAX_RETRIES", 3),
            backoff_factor=_env_float("SCRAPER_BACKOFF", 0.5),
            rate_limit_per_host=_env_float("SCRAPER_RATE_LIMIT", 1.0),
            respect_robots=_env_bool("SCRAPER_RESPECT_ROBOTS", True),
            db_path=os.environ.get("SCRAPER_DB_PATH", "scraped_data.db"),
        )
