import threading
from queue import Queue
import importlib
import logging
from .base_scraper import BaseScraper  # Use relative import
from app.models import db, Article, MapMarker
from app.utils import geocode_location, validate_coordinates, format_postgis_geometry, Trace
from geoalchemy2 import WKTElement

class ScraperManager:
    def __init__(self):
        self.scrapers = []
        self.results_queue = Queue()
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

    def scrape_page(self, scraper, url):
        articles = scraper.scrape(url)
        self.results_queue.put(articles)

    def run_scrapers(self):
        all_articles = []
        threads = []

        for scraper in self.scrapers:
            thread = threading.Thread(target=self.scrape_page, args=(scraper, scraper.base_url))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        while not self.results_queue.empty():
            all_articles.extend(self.results_queue.get())

        if all_articles:
            self.update_database(all_articles)
            logging.info(f"Total articles scraped: {len(all_articles)}")
        else:
            logging.warning("No articles scraped by any scraper.")

    def run_ml_model_on_articles(self, articles):
        from app.ml_models import run_model_on_articles
        return run_model_on_articles(articles)

    def update_database(self, articles):
        batch_size = 100
        article_batch = []
        map_marker_batch = []

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
            article_batch.append(new_article)

            if locations:
                for location_name in locations.split(', '):
                    lon, lat = geocode_location(location_name, trace)
                    if validate_coordinates(lon, lat, location_name):
                        location = format_postgis_geometry(lat, lon)
                        new_map_marker = MapMarker(
                            name=location_name,
                            location=WKTElement(location, srid=4326),
                            article_id=new_article.id
                        )
                        map_marker_batch.append(new_map_marker)

            if len(article_batch) >= batch_size:
                db.session.bulk_save_objects(article_batch)
                db.session.bulk_save_objects(map_marker_batch)
                db.session.commit()
                article_batch.clear()
                map_marker_batch.clear()

        if article_batch:
            db.session.bulk_save_objects(article_batch)
            db.session.bulk_save_objects(map_marker_batch)
            db.session.commit()

        logging.info("Database update complete.")