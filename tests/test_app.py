from unittest.mock import MagicMock

import pytest

from web_scraper.app import create_app
from web_scraper.config import Config


@pytest.fixture
def client(tmp_path):
    cfg = Config(db_path=str(tmp_path / "test.db"))
    scraper = MagicMock()
    scraper.scrape.return_value = {
        "url": "https://example.com/",
        "title": "Example",
        "headings": [],
        "paragraphs": [],
        "links": [],
        "images": [],
        "tables": [],
    }
    app = create_app(config=cfg, scraper=scraper)
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.scraper = scraper  # type: ignore[attr-defined]
        yield c


def test_home_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"Web Scraping Service" in r.data


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_scrape_requires_url(client):
    r = client.post("/scrape", json={})
    assert r.status_code == 400
    assert "url is required" in r.get_json()["error"]


def test_scrape_happy_path_json(client):
    r = client.post("/scrape", json={"url": "https://example.com/"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["title"] == "Example"
    client.scraper.scrape.assert_called_once_with("https://example.com/")


def test_scrape_adds_https_scheme(client):
    client.post("/scrape", json={"url": "example.com"})
    client.scraper.scrape.assert_called_once_with("https://example.com")


def test_scrape_form_body(client):
    r = client.post("/scrape", data={"url": "https://example.com/"})
    assert r.status_code == 200


def test_scrape_returns_502_on_error(client):
    client.scraper.scrape.return_value = {"error": "boom", "url": "x"}
    r = client.post("/scrape", json={"url": "https://example.com/"})
    assert r.status_code == 502
    assert r.get_json()["error"] == "boom"


def test_history_returns_recent_entries(client, tmp_path):
    # Insert directly so we don't depend on the mocked scraper.
    from web_scraper.storage import save_result
    save_result(client.application.config["SCRAPER_CONFIG"].db_path, {
        "url": "https://example.com/", "title": "Example", "links": [],
    })
    r = client.get("/history")
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/"
