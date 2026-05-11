"""
General-purpose web scraper.

Extracts structured data from any URL — links, headings, paragraphs,
images, and tables.  Falls back gracefully when a specific element type
is absent.  Results are stored in SQLite and returned as JSON.
"""
import sqlite3
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Timeout for all outbound requests (seconds)
REQUEST_TIMEOUT = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; WebScraper/1.0; "
        "+https://github.com/Gavand1969/web_scraping_service)"
    )
}


def _get_soup(url: str) -> BeautifulSoup:
    """Fetch a URL and return a BeautifulSoup object."""
    response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def scrape_page(url: str) -> dict[str, Any]:
    """
    Scrape a web page and return structured data.

    Returns a dict with keys:
      url, title, headings, paragraphs, links, images, tables
    """
    try:
        soup = _get_soup(url)
        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # Page title
        title = soup.title.string.strip() if soup.title else ""

        # Headings (h1–h3)
        headings = [
            {"level": tag.name, "text": tag.get_text(strip=True)}
            for tag in soup.find_all(["h1", "h2", "h3"])
            if tag.get_text(strip=True)
        ]

        # Paragraphs
        paragraphs = [
            p.get_text(strip=True)
            for p in soup.find_all("p")
            if len(p.get_text(strip=True)) > 20  # skip tiny/empty tags
        ]

        # Links
        links = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = urljoin(base, a["href"])
            if text and href.startswith("http"):
                links.append({"text": text, "url": href})

        # Images
        images = []
        for img in soup.find_all("img", src=True):
            src = urljoin(base, img["src"])
            alt = img.get("alt", "")
            images.append({"src": src, "alt": alt})

        # Tables
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)

        result = {
            "url": url,
            "title": title,
            "headings": headings[:20],
            "paragraphs": paragraphs[:20],
            "links": links[:50],
            "images": images[:20],
            "tables": tables[:5],
        }

        _save_to_db(result)
        return result

    except requests.exceptions.Timeout:
        return {"error": f"Request timed out after {REQUEST_TIMEOUT}s: {url}"}
    except requests.exceptions.HTTPError as exc:
        return {"error": f"HTTP {exc.response.status_code}: {url}"}
    except requests.exceptions.RequestException as exc:
        return {"error": f"Network error: {exc}"}
    except Exception as exc:
        return {"error": f"Unexpected error: {exc}"}


# ── Database ──────────────────────────────────────────────────────────────────

def init_db(db_path: str = "scraped_data.db") -> None:
    """Create tables if they don't already exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_results (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                url       TEXT NOT NULL,
                title     TEXT,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scrape_links (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER REFERENCES scrape_results(id),
                link_text TEXT,
                link_url  TEXT
            )
        """)


def _save_to_db(data: dict, db_path: str = "scraped_data.db") -> None:
    """Persist a scrape result to SQLite (best-effort, never raises)."""
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scrape_results (url, title) VALUES (?, ?)",
                (data.get("url", ""), data.get("title", ""))
            )
            result_id = cur.lastrowid
            for link in data.get("links", []):
                cur.execute(
                    "INSERT INTO scrape_links (result_id, link_text, link_url) VALUES (?, ?, ?)",
                    (result_id, link.get("text", ""), link.get("url", ""))
                )
            conn.commit()
    except sqlite3.Error:
        pass  # DB write failure should never break the API response


# Backwards-compatible alias used by older routes
def scrape_example(url: str) -> dict:
    return scrape_page(url)
