"""
Web Scraping Service — Flask API
"""
import os

from flask import Flask, jsonify, render_template, request

from scraper import init_db, scrape_page

app = Flask(__name__)

# Initialise the database on startup
init_db()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    """
    POST /scrape
    Body (form or JSON): { "url": "https://example.com" }
    Returns structured scrape result as JSON.
    """
    if request.is_json:
        url = (request.get_json() or {}).get("url", "").strip()
    else:
        url = request.form.get("url", "").strip()

    if not url:
        return jsonify({"error": "url is required"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    result = scrape_page(url)

    if "error" in result:
        return jsonify(result), 502

    return jsonify(result), 200


@app.route("/history", methods=["GET"])
def history():
    """GET /history — returns the last 50 scraped URLs."""
    import sqlite3
    try:
        with sqlite3.connect("scraped_data.db") as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, url, title, scraped_at FROM scrape_results "
                "ORDER BY scraped_at DESC LIMIT 50"
            ).fetchall()
        return jsonify([dict(r) for r in rows]), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    debug = os.environ.get("ENVIRONMENT", "development") != "production"
    app.run(debug=debug, host="0.0.0.0", port=port)
