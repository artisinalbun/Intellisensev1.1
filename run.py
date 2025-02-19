from flask import Flask
from flask_cors import CORS
from app import create_app
from scrapers.scraper_manager import ScraperManager
import os

app = create_app()

scraper_manager = ScraperManager()
scraper_manager.load_scrapers()

@app.route('/')
def index():
    return "Main Application"

@app.route('/scrape')
def scrape():
    category_url = 'https://apnews.com/business'
    scraper_manager.scrape(category_url)
    return "Scraping complete"

if __name__ == '__main__':
    print(app.url_map)  # Add this line to print the URL map
    app.run(debug=True)