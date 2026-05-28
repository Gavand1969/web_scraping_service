# Web Scraping Service

A polite, general-purpose web scraping service in Python — Flask HTTP API,
command-line tool, and importable library. Extracts titles, headings,
paragraphs, links, images, and tables from any URL and persists a compact
audit log to SQLite.

Designed to be **safe and ethical by default**: respects `robots.txt`,
enforces per-host rate limits, retries with exponential backoff on transient
failures, identifies itself with a descriptive User-Agent, and caps response
size to avoid resource exhaustion.

---

## Features

- **HTTP API** — Flask service with `/scrape`, `/history`, and `/healthz`
  endpoints.
- **CLI** — `web-scraper https://example.com` for one-off jobs and pipelines.
- **Library** — `from web_scraper import Scraper` to embed in your own code.
- **Polite by default** — `robots.txt` is consulted and cached per host;
  requests to the same host are spaced by a configurable interval.
- **Robust** — retries on 429 / 5xx and network errors with exponential
  backoff; bounded response size; structured JSON errors on failure.
- **Configurable via environment** — every behaviour can be tuned without
  touching code (see [Configuration](#configuration)).
- **Tested** — 40+ unit tests covering parsing, rate limiting, retries,
  robots handling, storage, and the Flask routes; no external network in the
  test suite.

---

## Installation

Python **3.10+** is required.

```sh
git clone https://github.com/Gavand1969/web_scraping_service.git
cd web_scraping_service
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

For development (tests + linting):

```sh
pip install -r requirements-dev.txt
```

Or install as a package (provides the `web-scraper` console script):

```sh
pip install -e .
```

---

## Quick start

### HTTP API

```sh
python app.py                                # dev server on :8000
gunicorn --bind 0.0.0.0:8000 app:app         # production
```

Then:

```sh
curl -s -X POST http://localhost:8000/scrape \
     -H 'Content-Type: application/json' \
     -d '{"url": "https://example.com"}' | jq
```

Response (truncated):

```json
{
  "url": "https://example.com/",
  "title": "Example Domain",
  "headings": [{"level": "h1", "text": "Example Domain"}],
  "paragraphs": ["This domain is for use in illustrative examples ..."],
  "links": [{"text": "More information...", "url": "https://www.iana.org/domains/example"}],
  "images": [],
  "tables": []
}
```

The browser UI is served at `/` and lets you submit URLs interactively.

### CLI

```sh
web-scraper https://example.com
web-scraper https://example.com https://other.example.com --rate-limit 2.0
web-scraper https://example.com --ignore-robots --no-persist -v
```

Exit code is `0` on success, `1` if any URL produced an error.

### Library

```python
from web_scraper import Config, Scraper

scraper = Scraper(Config(rate_limit_per_host=2.0))
result = scraper.scrape("https://example.com")
if "error" in result:
    print("scrape failed:", result["error"])
else:
    print(result["title"], "with", len(result["links"]), "links")
```

---

## HTTP API reference

| Method | Path         | Description                                    |
| ------ | ------------ | ---------------------------------------------- |
| `GET`  | `/`          | HTML UI for ad-hoc scraping.                   |
| `POST` | `/scrape`    | Scrape a URL. Body: `{"url": "..."}`.           |
| `GET`  | `/history`   | Last N scrape results (default 50, max 200).   |
| `GET`  | `/healthz`   | Liveness probe — returns `{"status": "ok"}`.   |

**Error responses** are JSON with an `error` field. Scrape failures return
HTTP `502` so callers can distinguish "your request was malformed" (`400`)
from "the upstream site failed" (`502`).

---

## Configuration

All settings come from environment variables. Defaults are tuned for polite,
hands-off operation.

| Variable                  | Default  | Description                                                  |
| ------------------------- | -------- | ------------------------------------------------------------ |
| `SCRAPER_TIMEOUT`         | `10`     | Per-request timeout in seconds.                              |
| `SCRAPER_MAX_BYTES`       | `5242880`| Response size cap (5 MiB) — protects against giant pages.    |
| `SCRAPER_USER_AGENT`      | *(self)* | User-Agent header. Override to identify your deployment.     |
| `SCRAPER_MAX_RETRIES`     | `3`      | Retry attempts on 429 / 5xx / connection errors.             |
| `SCRAPER_BACKOFF`         | `0.5`    | Backoff factor: sleep = `factor * 2**attempt`.               |
| `SCRAPER_RATE_LIMIT`      | `1.0`    | Minimum seconds between requests **to the same host**.       |
| `SCRAPER_RESPECT_ROBOTS`  | `true`   | If true, fetches/honours `robots.txt`.                       |
| `SCRAPER_DB_PATH`         | `scraped_data.db` | SQLite database path.                               |
| `PORT`                    | `8000`   | Port for the dev/Heroku server.                              |
| `ENVIRONMENT`             | `development` | Anything other than `development` disables Flask debug. |

---

## Ethical / responsible use

This service is intentionally biased toward being a good web citizen, but
the operator is still responsible for **what** they scrape and **how often**:

1. **Respect `robots.txt`.** Enabled by default. Override per-request only
   with consent of the site owner. The `--ignore-robots` flag exists for
   testing your own sites.
2. **Rate-limit yourself.** The 1 request/sec/host default is conservative.
   Increase the interval for small sites; decrease only if the target has
   given you permission (e.g. published API limits).
3. **Identify yourself.** Set `SCRAPER_USER_AGENT` to include a contact URL
   or email so site owners can reach you.
4. **Respect Terms of Service.** robots.txt is a hint, not a licence —
   check the target site's terms before scraping at scale.
5. **Don't scrape what you don't need.** Cache results (this service writes
   to SQLite by default); back off when you get 429s; stop on repeated 4xx.
6. **Personal data.** Scraping personal data may be subject to GDPR / CCPA
   and similar laws in your jurisdiction. When in doubt, don't.

---

## Architecture

```
web_scraper/
├── app.py          # Flask application factory
├── cli.py          # Command-line entry point
├── config.py       # Environment-driven Config dataclass
├── parser.py       # HTML → structured dict (pure, no I/O)
├── rate_limit.py   # Per-host rate limiter (thread-safe)
├── robots.py       # robots.txt fetcher + per-host cache
├── scraper.py      # Orchestrates fetch/retry/parse/persist
└── storage.py      # SQLite read/write
```

The split keeps each concern testable in isolation: `parser` has no
network, `rate_limit` accepts injected clock and sleep functions for
deterministic tests, `robots` accepts an injected fetcher, and `scraper`
accepts an injected `requests.Session` so test fakes can replace it
without monkey-patching globals.

---

## Development

```sh
# install dev deps
pip install -r requirements-dev.txt

# run tests
pytest -q

# coverage
pytest --cov=web_scraper --cov-report=term-missing

# lint
ruff check .
```

CI runs lint + tests against Python 3.10, 3.11, and 3.12 on every push
and pull request (`.github/workflows/ci.yml`).

---

## Deployment

The Procfile launches `gunicorn` with two workers and a 30s timeout:

```
web: gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 30 app:app
```

Live demo: <https://gja-web-scraper-bf807c2e68d5.herokuapp.com/>

To deploy your own:

```sh
heroku create your-app-name
git push heroku main
heroku open
```

---

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feat/your-change`).
3. Run `pytest` and `ruff check .` until both are clean.
4. Open a pull request describing the change and its motivation.

---

## License

MIT — see `LICENSE`.

## Contact

Gavin Anderson · <gavanderson13@gmail.com>
[github.com/Gavand1969/web_scraping_service](https://github.com/Gavand1969/web_scraping_service)
