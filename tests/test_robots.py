from urllib import robotparser

from web_scraper.robots import RobotsChecker


def _parser_from(text: str) -> robotparser.RobotFileParser:
    rp = robotparser.RobotFileParser()
    rp.parse(text.splitlines())
    return rp


def test_disallowed_path_blocked():
    rp = _parser_from(
        "User-agent: *\n"
        "Disallow: /private/\n"
    )
    checker = RobotsChecker("TestBot/1.0", fetcher=lambda _u: rp)
    assert checker.allowed("https://example.com/public/index.html") is True
    assert checker.allowed("https://example.com/private/secret") is False


def test_unreachable_robots_treated_as_permissive():
    # Default fetcher swallows exceptions; simulate via a parser with no rules.
    rp = _parser_from("")
    checker = RobotsChecker("TestBot/1.0", fetcher=lambda _u: rp)
    assert checker.allowed("https://example.com/anywhere") is True


def test_robots_parser_cached_per_host():
    calls: list[str] = []

    def fetcher(url: str) -> robotparser.RobotFileParser:
        calls.append(url)
        return _parser_from("User-agent: *\nAllow: /\n")

    checker = RobotsChecker("TestBot/1.0", fetcher=fetcher)
    checker.allowed("https://example.com/a")
    checker.allowed("https://example.com/b")
    checker.allowed("https://other.example.com/c")
    assert calls == [
        "https://example.com/robots.txt",
        "https://other.example.com/robots.txt",
    ]
