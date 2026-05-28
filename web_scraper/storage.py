"""SQLite persistence for scrape results.

Schema is intentionally small — the goal is auditability of what was scraped,
not a full content store. Writes are best-effort: a DB failure is logged and
the API response is still returned to the caller.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any

logger = logging.getLogger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS scrape_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL,
    title       TEXT,
    scraped_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_scrape_results_scraped_at
    ON scrape_results(scraped_at DESC);

CREATE TABLE IF NOT EXISTS scrape_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id   INTEGER REFERENCES scrape_results(id) ON DELETE CASCADE,
    link_text   TEXT,
    link_url    TEXT
);
"""


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


def save_result(db_path: str, data: dict[str, Any]) -> int | None:
    """Persist a scrape result. Returns the new row id, or None on failure."""
    try:
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO scrape_results (url, title) VALUES (?, ?)",
                (data.get("url", ""), data.get("title", "")),
            )
            result_id = cur.lastrowid
            for link in data.get("links", []):
                cur.execute(
                    "INSERT INTO scrape_links (result_id, link_text, link_url) "
                    "VALUES (?, ?, ?)",
                    (result_id, link.get("text", ""), link.get("url", "")),
                )
            conn.commit()
            return result_id
    except sqlite3.Error as exc:
        logger.warning("DB write failed for %s: %s", data.get("url"), exc)
        return None


def recent_results(db_path: str, limit: int = 50) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, url, title, scraped_at FROM scrape_results "
            "ORDER BY scraped_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]
