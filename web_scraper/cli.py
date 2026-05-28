"""Command-line interface.

Usage examples are in the README. This module exposes ``main()`` as the
entry point referenced by ``pyproject.toml`` (``web-scraper`` console script).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence

from web_scraper.config import Config
from web_scraper.scraper import Scraper


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="web-scraper",
        description="Scrape one or more URLs and emit structured JSON.",
    )
    p.add_argument("urls", nargs="+", help="URL(s) to scrape")
    p.add_argument("--no-persist", action="store_true",
                   help="Skip writing results to SQLite")
    p.add_argument("--ignore-robots", action="store_true",
                   help="Do not consult robots.txt (use with care)")
    p.add_argument("--timeout", type=float, default=None,
                   help="Per-request timeout in seconds")
    p.add_argument("--rate-limit", type=float, default=None,
                   help="Minimum seconds between requests to the same host")
    p.add_argument("--retries", type=int, default=None,
                   help="Maximum retry attempts on transient failures")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    base = Config.from_env()
    cfg = Config(
        request_timeout=args.timeout if args.timeout is not None else base.request_timeout,
        max_response_bytes=base.max_response_bytes,
        user_agent=base.user_agent,
        max_retries=args.retries if args.retries is not None else base.max_retries,
        backoff_factor=base.backoff_factor,
        rate_limit_per_host=(
            args.rate_limit if args.rate_limit is not None else base.rate_limit_per_host
        ),
        respect_robots=False if args.ignore_robots else base.respect_robots,
        db_path=base.db_path,
    )
    scraper = Scraper(cfg)

    results = [scraper.scrape(u, persist=not args.no_persist) for u in args.urls]
    json.dump(results if len(results) > 1 else results[0], sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if all("error" not in r for r in results) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
