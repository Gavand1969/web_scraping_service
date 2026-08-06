import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from web_scraper import cli

SAMPLE = Path(__file__).parent.joinpath("fixtures/sample.html").read_text()


def test_cli_emits_json_for_single_url(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SCRAPER_DB_PATH", str(tmp_path / "cli.db"))
    fake = MagicMock()
    fake.scrape.return_value = {"url": "https://example.com/", "title": "X"}
    with patch.object(cli, "Scraper", return_value=fake):
        code = cli.main(["https://example.com/", "--no-persist"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["title"] == "X"


def test_cli_returns_nonzero_on_error(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SCRAPER_DB_PATH", str(tmp_path / "cli.db"))
    fake = MagicMock()
    fake.scrape.return_value = {"error": "nope", "url": "x"}
    with patch.object(cli, "Scraper", return_value=fake):
        code = cli.main(["https://example.com/", "--no-persist"])
    assert code == 1


def test_cli_multiple_urls_emits_list(capsys, tmp_path, monkeypatch):
    monkeypatch.setenv("SCRAPER_DB_PATH", str(tmp_path / "cli.db"))
    fake = MagicMock()
    fake.scrape.side_effect = [
        {"url": "https://a.example.com/", "title": "A"},
        {"url": "https://b.example.com/", "title": "B"},
    ]
    with patch.object(cli, "Scraper", return_value=fake):
        cli.main(["https://a.example.com/", "https://b.example.com/", "--no-persist"])
    out = json.loads(capsys.readouterr().out)
    assert len(out) == 2
    assert {r["title"] for r in out} == {"A", "B"}


def test_cli_flags_propagate_to_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SCRAPER_DB_PATH", str(tmp_path / "cli.db"))
    captured = {}

    def fake_scraper_factory(cfg):
        captured["cfg"] = cfg
        fake = MagicMock()
        fake.scrape.return_value = {"url": "x", "title": "x"}
        return fake

    with patch.object(cli, "Scraper", side_effect=fake_scraper_factory):
        cli.main([
            "https://example.com/",
            "--no-persist",
            "--ignore-robots",
            "--timeout", "2.5",
            "--rate-limit", "3.0",
            "--retries", "5",
        ])
    cfg = captured["cfg"]
    assert cfg.respect_robots is False
    assert cfg.request_timeout == 2.5
    assert cfg.rate_limit_per_host == 3.0
    assert cfg.max_retries == 5
