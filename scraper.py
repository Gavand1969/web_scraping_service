"""Backwards-compatible re-exports.

The original ``scraper`` module was the only entry point in earlier
versions. The implementation now lives in :mod:`web_scraper`; this shim
preserves the old imports for existing callers.
"""
from web_scraper.scraper import Scraper, scrape_page  # noqa: F401
from web_scraper.storage import init_db  # noqa: F401


def scrape_example(url: str) -> dict:
    """Deprecated alias for :func:`scrape_page`."""
    return scrape_page(url)
