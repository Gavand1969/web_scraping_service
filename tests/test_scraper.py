"""Scraper tests — all network calls are mocked, no external traffic."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import requests

from web_scraper.config import Config
from web_scraper.rate_limit import RateLimiter
from web_scraper.robots import RobotsChecker
from web_scraper.scraper import Scraper

SAMPLE = Path(__file__).parent.joinpath("fixtures/sample.html").read_text()


class FakeResponse:
    def __init__(self, *, status_code: int = 200, body: bytes | str = b"",
                 encoding: str = "utf-8") -> None:
        self.status_code = status_code
        if isinstance(body, str):
            body = body.encode(encoding)
        self._body = body
        self.encoding = encoding
        self.apparent_encoding = encoding
        self.closed = False

    def iter_content(self, chunk_size: int = 8192):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def close(self):
        self.closed = True


def _make_scraper(session: MagicMock, *, retries: int = 3,
                  respect_robots: bool = False) -> Scraper:
    cfg = Config(
        request_timeout=1.0,
        max_retries=retries,
        backoff_factor=0.0,  # don't slow tests
        rate_limit_per_host=0.0,
        respect_robots=respect_robots,
        db_path=":memory:",
    )
    return Scraper(
        cfg,
        session=session,
        sleep=lambda _s: None,
        robots=RobotsChecker("test", fetcher=lambda _u: _AllowAll()),
    )


class _AllowAll:
    def can_fetch(self, *_args, **_kwargs):
        return True


# ── Happy path ────────────────────────────────────────────────────────────

def test_scrape_returns_structured_data(tmp_path, monkeypatch):
    session = MagicMock()
    session.headers = {}
    session.get.return_value = FakeResponse(body=SAMPLE)
    scraper = _make_scraper(session)
    monkeypatch.setattr(scraper, "config",
                        Config(db_path=str(tmp_path / "test.db"),
                               rate_limit_per_host=0.0,
                               backoff_factor=0.0,
                               respect_robots=False))
    # init the DB
    from web_scraper.storage import init_db
    init_db(scraper.config.db_path)

    result = scraper.scrape("https://example.com/")
    assert "error" not in result
    assert result["title"] == "Example Page"
    assert result["url"] == "https://example.com/"
    assert any(h["level"] == "h1" for h in result["headings"])


# ── Retry behaviour ───────────────────────────────────────────────────────

def test_retries_on_5xx_then_succeeds():
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [
        FakeResponse(status_code=503),
        FakeResponse(status_code=502),
        FakeResponse(body=SAMPLE),
    ]
    scraper = _make_scraper(session, retries=3)
    result = scraper.scrape("https://example.com/")
    assert "error" not in result
    assert session.get.call_count == 3


def test_retries_on_connection_error():
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [
        requests.ConnectionError("boom"),
        requests.ConnectionError("boom again"),
        FakeResponse(body=SAMPLE),
    ]
    scraper = _make_scraper(session, retries=3)
    result = scraper.scrape("https://example.com/")
    assert "error" not in result
    assert session.get.call_count == 3


def test_retries_exhausted_returns_error():
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = [FakeResponse(status_code=503)] * 4
    scraper = _make_scraper(session, retries=3)
    result = scraper.scrape("https://example.com/")
    assert "error" in result
    assert "HTTP" in result["error"]
    assert session.get.call_count == 4  # initial + 3 retries


def test_non_retryable_4xx_not_retried():
    session = MagicMock()
    session.headers = {}
    session.get.return_value = FakeResponse(status_code=404)
    scraper = _make_scraper(session, retries=3)
    result = scraper.scrape("https://example.com/")
    assert "error" in result
    assert session.get.call_count == 1


def test_timeout_returns_error():
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = requests.exceptions.Timeout("slow")
    scraper = _make_scraper(session, retries=0)
    result = scraper.scrape("https://example.com/")
    assert "timed out" in result["error"]


# ── Response size cap ─────────────────────────────────────────────────────

def test_oversized_response_rejected():
    big = b"<html><body>" + b"x" * 200 + b"</body></html>"
    session = MagicMock()
    session.headers = {}
    session.get.return_value = FakeResponse(body=big)
    cfg = Config(
        max_response_bytes=100,
        max_retries=0,
        rate_limit_per_host=0.0,
        backoff_factor=0.0,
        respect_robots=False,
        db_path=":memory:",
    )
    scraper = Scraper(cfg, session=session, sleep=lambda _s: None,
                      robots=RobotsChecker("t", fetcher=lambda _u: _AllowAll()))
    result = scraper.scrape("https://example.com/", persist=False)
    assert "exceeded max_response_bytes" in result["error"]


# ── Robots.txt enforcement ────────────────────────────────────────────────

def test_robots_disallowed_short_circuits_fetch():
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = AssertionError("should not be called")

    class _DenyAll:
        def can_fetch(self, *_args, **_kwargs):
            return False

    cfg = Config(
        respect_robots=True,
        rate_limit_per_host=0.0,
        backoff_factor=0.0,
        max_retries=0,
        db_path=":memory:",
    )
    scraper = Scraper(
        cfg, session=session, sleep=lambda _s: None,
        robots=RobotsChecker("t", fetcher=lambda _u: _DenyAll()),
    )
    result = scraper.scrape("https://example.com/", persist=False)
    assert result == {"error": "Blocked by robots.txt", "url": "https://example.com/"}
    session.get.assert_not_called()


# ── Rate limiter integration ──────────────────────────────────────────────

def test_rate_limiter_invoked_per_request():
    session = MagicMock()
    session.headers = {}
    session.get.return_value = FakeResponse(body=SAMPLE)
    limiter = MagicMock(spec=RateLimiter)
    limiter.wait.return_value = 0.0
    cfg = Config(
        respect_robots=False,
        rate_limit_per_host=0.0,
        backoff_factor=0.0,
        max_retries=0,
        db_path=":memory:",
    )
    scraper = Scraper(cfg, session=session, rate_limiter=limiter,
                      sleep=lambda _s: None,
                      robots=RobotsChecker("t", fetcher=lambda _u: _AllowAll()))
    scraper.scrape("https://example.com/", persist=False)
    limiter.wait.assert_called_once_with("https://example.com/")
