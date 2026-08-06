"""Flask HTTP API for the scraping service."""
from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, render_template, request

from web_scraper.config import Config
from web_scraper.scraper import Scraper
from web_scraper.storage import init_db, recent_results

logger = logging.getLogger(__name__)


def create_app(config: Config | None = None, scraper: Scraper | None = None) -> Flask:
    """Application factory. Pass injected ``Scraper`` for tests."""
    cfg = config or Config.from_env()
    scraper = scraper or Scraper(cfg)
    init_db(cfg.db_path)

    app = Flask(__name__, template_folder=os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "templates"
    ))
    app.config["SCRAPER"] = scraper
    app.config["SCRAPER_CONFIG"] = cfg

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    @app.route("/scrape", methods=["POST"])
    def scrape():
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            url = (payload.get("url") or "").strip()
        else:
            url = (request.form.get("url") or "").strip()

        if not url:
            return jsonify({"error": "url is required"}), 400

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        result = scraper.scrape(url)
        if "error" in result:
            return jsonify(result), 502
        return jsonify(result), 200

    @app.route("/history", methods=["GET"])
    def history():
        try:
            limit = min(int(request.args.get("limit", 50)), 200)
        except ValueError:
            limit = 50
        try:
            return jsonify(recent_results(cfg.db_path, limit)), 200
        except Exception as exc:
            logger.exception("history failed")
            return jsonify({"error": str(exc)}), 500

    return app
