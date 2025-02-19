import logging
import sys
import spacy

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

try:
    import torch
    logging.info(f"Torch version: {torch.__version__}")
except ImportError as e:
    logging.error(f"Failed to import torch: {str(e)}")
    raise

import time
import random
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests
from bs4 import BeautifulSoup
from transformers import pipeline
from scrapers.base_scraper import BaseScraper
from app.models import Article, MapMarker
from app.database import db
from app.utils import extract_locations, geocode_location, validate_coordinates, Trace

# Download the spaCy transformer model if not already installed
try:
    nlp = spacy.load("en_core_web_trf")
except OSError:
    logging.info("Downloading spaCy transformer model 'en_core_web_trf'...")
    from spacy.cli import download
    download("en_core_web_trf")
    nlp = spacy.load("en_core_web_trf")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36"
]

RETRY_CONFIG = {
    "stop": stop_after_attempt(3),
    "wait": wait_exponential(multiplier=1, min=4, max=10),
    "retry": retry_if_exception_type(Exception),
    "before_sleep": lambda retry_state: logging.warning(
        f"Retrying {retry_state.fn.__name__} after failure: {retry_state.outcome.exception()}"
    )
}

device = 0 if torch.cuda.is_available() else -1
ner_pipeline = pipeline("ner", grouped_entities=True, model="dslim/bert-base-NER", device=device)

class NewsScraper(BaseScraper):
    def __init__(self):
        self.base_url = "https://apnews.com/"
        self.headers = {
            "User-Agent": random.choice(USER_AGENTS)
        }

    @retry(**RETRY_CONFIG)
    def fetch_page(self, url):
        logging.info(f"Fetching page: {url}")
        response = requests.get(url, headers=self.headers, timeout=10)
        response.raise_for_status()
        return response.text

    def extract_article_links(self, category_url):
        articles = []
        try:
            html = self.fetch_page(category_url)
            logging.info(f"Fetched category page: {category_url}")
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.select("a.Link[href]"):
                article_url = a_tag["href"]
                if article_url not in articles:
                    articles.append(article_url)
            logging.info(f"Extracted {len(articles)} article links")
        except Exception as e:
            logging.error(f"Error extracting article links: {str(e)}", exc_info=True)
        return articles

    def scrape(self, category_url):
        article_links = self.extract_article_links(category_url)
        for url in article_links:
            if Article.query.filter_by(url=url).first():
                logging.info(f"Skipping already scraped article: {url}")
                continue

            try:
                logging.info(f"Fetching article: {url}")
                html = self.fetch_page(url)
                if not html:
                    logging.warning(f"Failed to fetch HTML for: {url}")
                    continue

                soup = BeautifulSoup(html, "html.parser")

                headline_tag = soup.find("h1") or soup.find("h2") or soup.find(class_="Page-headline")
                if not headline_tag:
                    logging.warning(f"No headline found for: {url}")
                    continue
                headline = headline_tag.text.strip()

                paragraphs = [
                    p.text.strip() for p in soup.find_all("p")
                    if "Copyright" not in p.text and len(p.text.split()) > 5
                ][:4]

                if not paragraphs:
                    logging.warning(f"No valid paragraphs found in {url}")
                    continue

                body = "\n".join(paragraphs)

                trace = Trace()
                locations = extract_locations(headline, body, trace)
                if locations:
                    lon, lat = geocode_location(locations[0], trace)
                else:
                    lon, lat = None, None

                logging.info(f"Trace for {url}: {trace.get_trace()}")

                article = Article(
                    url=url,
                    headline=headline,
                    body=body,
                    date=self.extract_date(soup),
                    source="AP News",
                    people=", ".join(self.extract_people_and_organizations(f"{headline} {body}")[0]),
                    num_people=len(self.extract_people_and_organizations(f"{headline} {body}")[0]),
                    locations=", ".join(locations),
                    organizations=", ".join(self.extract_people_and_organizations(f"{headline} {body}")[1]),
                    num_organizations=len(self.extract_people_and_organizations(f"{headline} {body}")[1]),
                    profiles=1
                )
                db.session.add(article)
                db.session.commit()

                if locations and validate_coordinates(lon, lat, locations[0]):
                    marker = MapMarker(
                        name=headline,
                        location=f"SRID=4326;POINT({lon} {lat})",
                        article_id=article.id
                    )
                    db.session.add(marker)
                    db.session.commit()

                time.sleep(random.uniform(1, 3))
            except Exception as e:
                logging.error(f"Error scraping article {url}: {str(e)}", exc_info=True)

    def extract_date(self, soup):
        date_tag = soup.find("meta", {"property": "article:published_time"})
        if date_tag:
            return date_tag["content"]
        return datetime.now().strftime("%Y-%m-%d")

    def extract_people_and_organizations(self, text):
        doc = nlp(text)
        people = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        organizations = [ent.text for ent in doc.ents if ent.label_ == "ORG"]
        return people, organizations