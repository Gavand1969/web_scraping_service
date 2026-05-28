"""HTML → structured dict extraction.

Pure, deterministic, and easy to unit test: no network, no I/O.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from web_scraper.config import Config


def parse_html(html: str, url: str, config: Config | None = None) -> dict[str, Any]:
    """Extract structured data from an HTML document."""
    cfg = config or Config()
    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(url)
    base = f"{parsed_url.scheme}://{parsed_url.netloc}"

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    headings = [
        {"level": tag.name, "text": tag.get_text(strip=True)}
        for tag in soup.find_all(["h1", "h2", "h3"])
        if tag.get_text(strip=True)
    ]

    paragraphs = [
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if len(p.get_text(strip=True)) > 20
    ]

    links: list[dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = urljoin(base, a["href"])
        if text and href.startswith(("http://", "https://")):
            links.append({"text": text, "url": href})

    images: list[dict[str, str]] = []
    for img in soup.find_all("img", src=True):
        images.append(
            {"src": urljoin(base, img["src"]), "alt": img.get("alt", "")}
        )

    tables: list[list[list[str]]] = []
    for table in soup.find_all("table"):
        rows: list[list[str]] = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    return {
        "url": url,
        "title": title,
        "headings": headings[: cfg.max_headings],
        "paragraphs": paragraphs[: cfg.max_paragraphs],
        "links": links[: cfg.max_links],
        "images": images[: cfg.max_images],
        "tables": tables[: cfg.max_tables],
    }
