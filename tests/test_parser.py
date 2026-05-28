from pathlib import Path

from web_scraper.config import Config
from web_scraper.parser import parse_html


def _sample() -> str:
    return Path(__file__).parent.joinpath("fixtures/sample.html").read_text()


def test_title_is_extracted_and_stripped():
    result = parse_html(_sample(), "https://example.com/")
    assert result["title"] == "Example Page"


def test_headings_levels_and_text():
    result = parse_html(_sample(), "https://example.com/")
    levels = [h["level"] for h in result["headings"]]
    assert levels == ["h1", "h2", "h3"]
    assert result["headings"][0]["text"] == "Main Heading"


def test_short_paragraphs_filtered_out():
    result = parse_html(_sample(), "https://example.com/")
    assert all(len(p) > 20 for p in result["paragraphs"])
    assert len(result["paragraphs"]) == 2


def test_links_resolved_against_base_and_non_http_excluded():
    result = parse_html(_sample(), "https://example.com/some/page")
    urls = {link["url"] for link in result["links"]}
    assert "https://other.example.com/page" in urls
    assert "https://example.com/relative" in urls
    # mailto: filtered out
    assert not any(u.startswith("mailto:") for u in urls)
    # link with no anchor text excluded
    assert "https://no-text.example.com" not in urls


def test_images_resolved_against_base():
    result = parse_html(_sample(), "https://example.com/")
    srcs = [img["src"] for img in result["images"]]
    assert "https://example.com/img/logo.png" in srcs
    assert "https://cdn.example.com/banner.png" in srcs


def test_tables_extracted_as_rows():
    result = parse_html(_sample(), "https://example.com/")
    assert result["tables"] == [[["Header A", "Header B"], ["1", "2"]]]


def test_output_caps_respected():
    cfg = Config(max_paragraphs=1, max_links=1, max_headings=1,
                 max_images=1, max_tables=0)
    result = parse_html(_sample(), "https://example.com/", cfg)
    assert len(result["paragraphs"]) == 1
    assert len(result["links"]) == 1
    assert len(result["headings"]) == 1
    assert len(result["images"]) == 1
    assert result["tables"] == []


def test_missing_title_returns_empty_string():
    result = parse_html("<html><body><p>nothing here</p></body></html>",
                        "https://example.com/")
    assert result["title"] == ""
