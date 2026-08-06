"""Web scraping service — library, HTTP API, and CLI."""
from web_scraper.config import Config
from web_scraper.scraper import Scraper, scrape_page

__all__ = ["Config", "Scraper", "scrape_page"]
__version__ = "0.2.0"
