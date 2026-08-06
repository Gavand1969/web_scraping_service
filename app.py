"""Process entry point (kept for Heroku Procfile compatibility).

The real Flask application lives in :mod:`web_scraper.app`. This module
exposes ``app`` for WSGI servers and runs the dev server when executed
directly.
"""
import os

from web_scraper.app import create_app

app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("ENVIRONMENT", "development").lower() == "development"
    app.run(debug=debug, host="0.0.0.0", port=port)
