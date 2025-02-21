import importlib
import logging
import threading
from queue import Queue
from .base_scraper import BaseScraper  # Use relative import

class ScraperManager:
    def __init__(self):
        self.scrapers = []
        self.ml_model_active = False

    def load_scraper(self, scraper_name):
        module = importlib.import_module(f"scrapers.{scraper_name}")
        scraper_class =  getattr(module, scraper_name.title().replace("_", ""))
        scraper_instance = scraper_class()
        self.scrapers.append(scraper_instance)
        logging.info(f"Loaded scraper: {scraper_name}")

    def load_scrapers(self):
        scraper_names = ["news_scraper"]  # Add your scraper names here
        for scraper_name in scraper_names:
            self.load_scraper(scraper_name)
        logging.info("All scrapers loaded")

    def run_scrapers(self):
        all_articles = []
        for scraper in self.scrapers:
            articles = scraper.scrape(scraper.base_url)  # Call the scrape method of each scraper
            if articles:  # Check if articles were returned
                all_articles.extend(articles)
                logging.info(f"Scraped {len(articles)} articles using {scraper.__class__.__name__}")
            else:
                logging.warning(f"No articles scraped by {scraper.__class__.__name__}")

        # Optionally, process the scraped articles further (e.g., save to the database)
        if all_articles:
            self.update_database(all_articles)  # Update the database with scraped articles
            logging.info(f"Total articles scraped: {len(all_articles)}")
        else:
            logging.warning("No articles scraped by any scraper.")

    def run_ml_model_on_articles(self, articles):
        from app.ml_models import run_model_on_articles
        return run_model_on_articles(articles)

    def update_database(self, articles):
        from app.models import db, Article, MapMarker
        from app.utils import geocode_location, validate_coordinates, format_postgis_geometry, Trace
        from geoalchemy2 import WKTElement

        for article_data in articles:
            trace = Trace()
            headline = article_data['headline']
            body = article_data['body']
            url = article_data['url']
            date = article_data['date']
            source = article_data['source']
            people = article_data['people']
            locations = article_data['locations']
            organizations = article_data['organizations']

            if Article.query.filter_by(url=url).first():
                logging.info(f"Skipping already existing article: {url}")
                continue

            new_article = Article(
                url=url,
                headline=headline,
                body=body,
                date=date,
                source=source,
                people=people,
                num_people=len(people.split(', ')),
                locations=locations,
                organizations=organizations,
                num_organizations=len(organizations.split(', ')),
                profiles=1
            )
            db.session.add(new_article)
            db.session.commit()
            article_id = new_article.id

            if locations:
                for location_name in locations.split(', '):
                    lon, lat = geocode_location(location_name, trace)
                    if validate_coordinates(lon, lat, location_name):
                        location = format_postgis_geometry(lat, lon)
                        new_map_marker = MapMarker(
                            name=location_name,
                            location=WKTElement(location, srid=4326),
                            article_id=article_id
                        )
                        db.session.add(new_map_marker)
                        db.session.commit()

        logging.info("Database update complete.")