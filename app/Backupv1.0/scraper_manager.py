import importlib
import os
import logging
from scrapers.base_scraper import BaseScraper

class ScraperManager:
    def __init__(self):
        self.scrapers = []

    def load_scrapers(self):
        scraper_files = [f for f in os.listdir(os.path.dirname(__file__)) if f.endswith('_scraper.py')]
        for scraper_file in scraper_files:
            module_name = f"scrapers.{scraper_file[:-3]}"
            try:
                logging.info(f"Attempting to import {module_name}")
                module = importlib.import_module(module_name)
                logging.info(f"Successfully imported {module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseScraper) and attr is not BaseScraper:
                        self.scrapers.append(attr())
                        logging.info(f"Loaded scraper: {attr_name} from {module_name}")
            except Exception as e:
                logging.error(f"Failed to load scraper {module_name}: {e}", exc_info=True)

    def scrape(self, category_url):
        for scraper in self.scrapers:
            try:
                scraper.scrape(category_url)
                logging.info(f"Scraped {category_url} using {scraper.__class__.__name__}")
            except Exception as e:
                logging.error(f"Scraper {scraper.__class__.__name__} failed to scrape {category_url}: {e}", exc_info=True)