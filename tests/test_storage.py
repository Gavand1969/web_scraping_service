from web_scraper.storage import init_db, recent_results, save_result


def test_init_db_creates_tables(tmp_path):
    db = tmp_path / "x.db"
    init_db(str(db))
    init_db(str(db))  # second call is idempotent
    assert db.exists()


def test_save_and_recent_roundtrip(tmp_path):
    db = str(tmp_path / "x.db")
    init_db(db)
    rid = save_result(db, {
        "url": "https://example.com/",
        "title": "Example",
        "links": [
            {"text": "Home", "url": "https://example.com/"},
            {"text": "About", "url": "https://example.com/about"},
        ],
    })
    assert rid is not None

    rows = recent_results(db, limit=10)
    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/"
    assert rows[0]["title"] == "Example"


def test_save_result_swallows_db_errors(tmp_path):
    # Pointing at a non-DB file makes sqlite3 fail; save_result must return None.
    bogus = tmp_path / "not-a-db"
    bogus.write_text("not a sqlite db")
    rid = save_result(str(bogus), {"url": "x", "title": "y", "links": []})
    assert rid is None
