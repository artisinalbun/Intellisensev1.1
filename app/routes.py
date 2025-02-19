from flask import Blueprint, request, jsonify, render_template
from app.data_manager import DataManager
from app.ml_models import MLModels
from app.models import db, DataEntry, Article, MapMarker, People, Profile
from geoalchemy2.functions import ST_X, ST_Y
from geoalchemy2 import WKTElement
from shapely.geometry import Point
from scrapers.scraper_manager import ScraperManager
import logging
import joblib
import pandas as pd
import re
from collections import defaultdict
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from .utils import remove_duplicate_articles, remove_duplicate_map_markers, ensure_corresponding_map_markers

app = Blueprint('app', __name__)

data_manager = DataManager()
scraper_manager = ScraperManager()
scraper_manager.load_scrapers()

# Load the trained model
ml_models = MLModels(data_manager)
ml_models.load_model()

# Homepage with map and start scraper
@app.route('/')
def index():
    logging.debug("Rendering index.html")
    return render_template('index.html')

# Add a marker
@app.route('/add_marker', methods=['POST'])
def add_marker():
    data = request.json
    logging.debug(f"Adding marker with data: {data}")
    if not data or 'name' not in data or 'lat' not in data or 'lon' not in data or 'article_id' not in data:
        return jsonify({"status": "error", "message": "Invalid data: name, lat, lon, and article_id are required"}), 400

    name = data['name']
    lat = float(data['lat'])
    lon = float(data['lon'])
    article_id = data['article_id']

    point = Point(lon, lat)
    wkt_point = WKTElement(point.wkt, srid=4326)

    new_marker = MapMarker(name=name, location=wkt_point, article_id=article_id)
    db.session.add(new_marker)
    db.session.commit()
    logging.debug(f"Marker added: {new_marker}")

    return jsonify({"status": "success", "marker": {"id": new_marker.id, "name": name, "lat": lat, "lon": lon, "article_id": article_id}})

# Delete a marker
@app.route('/delete_marker/<int:marker_id>', methods=['DELETE'])
def delete_marker(marker_id):
    logging.debug(f"Deleting marker with ID: {marker_id}")
    marker = MapMarker.query.get(marker_id)
    if marker:
        db.session.delete(marker)
        db.session.commit()
        logging.debug("Marker deleted")
        return jsonify({"status": "success", "message": "Marker deleted"})
    else:
        logging.debug("Marker not found")
        return jsonify({"status": "error", "message": "Marker not found"}), 404

# Update marker position
@app.route('/update_marker/<int:marker_id>', methods=['PUT'])
def update_marker(marker_id):
    data = request.json
    logging.debug(f"Updating marker with ID: {marker_id} and data: {data}")
    if not data or 'name' not in data or 'lat' not in data or 'lon' not in data or 'article_id' not in data:
        return jsonify({"status": "error", "message": "Invalid data: name, lat, lon, and article_id are required"}), 400

    name = data['name']
    lat = float(data['lat'])
    lon = float(data['lon'])
    article_id = data['article_id']

    point = Point(lon, lat)
    wkt_point = WKTElement(point.wkt, srid=4326)

    marker = MapMarker.query.get(marker_id)
    if marker:
        marker.name = name
        marker.location = wkt_point
        marker.article_id = article_id
        db.session.commit()
        logging.debug("Marker updated")
        return jsonify({"status": "success", "message": "Marker updated"})
    else:
        logging.debug("Marker not found")
        return jsonify({"status": "error", "message": "Marker not found"}), 404

# Get all markers
@app.route('/get_markers', methods=['GET'])
def get_markers():
    logging.debug("Getting all markers")
    markers = MapMarker.query.all()
    logging.info(f"Fetched {len(markers)} markers from the database.")
    
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [db.session.scalar(ST_X(marker.location)), db.session.scalar(ST_Y(marker.location))]
                },
                "properties": {
                    "id": marker.id,
                    "name": marker.name,
                    "article_id": marker.article_id
                }
            }
            for marker in markers
        ]
    }
    logging.info(f"GeoJSON data: {geojson}")
    return jsonify(geojson)

# Get article by ID
@app.route('/get_article/<int:article_id>', methods=['GET'])
def get_article(article_id):
    logging.debug(f"Getting article with ID: {article_id}")
    article = Article.query.get(article_id)
    if article:
        return jsonify({
            "headline": article.headline,
            "body": article.body
        })
    else:
        logging.debug("Article not found")
        return jsonify({"status": "error", "message": "Article not found"}), 404

# Add data entry
@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    logging.debug(f"Adding data entry with data: {data}")
    data_manager.add_data(**data)
    return jsonify({'status': 'success'})

# Train model
@app.route('/train_model', methods=['POST'])
def train_model():
    logging.debug("Training model")
    data_manager.load_articles()  # Load articles data to train the model
    data_manager.clean_data()  # Clean the data
    data_manager.tokenize_data()  # Tokenize the data

    ml_models = MLModels(data_manager)
    model, accuracy = ml_models.train_model()
    logging.debug(f"Model trained with accuracy: {accuracy}")
    return jsonify({'accuracy': accuracy})

# Predict location
@app.route('/predict_location', methods=['POST'])
def predict_location():
    logging.debug("Predicting location")
    data = request.json
    headline = data.get('headline')
    body = data.get('body')

    if not headline or not body:
        return jsonify({'status': 'error', 'message': 'Headline and body are required'}), 400

    data_manager.df = pd.DataFrame([{'headline': headline, 'body': body}])  # Create a DataFrame with the input data
    data_manager.tokenize_data()  # Tokenize the input data

    df = data_manager.get_dataframe()
    X = df[['tokenized_headline', 'tokenized_body']]
    
    # Flatten the tokenized columns
    X_headline = pd.DataFrame(X['tokenized_headline'].tolist()).fillna(0).astype(int)
    X_body = pd.DataFrame(X['tokenized_body'].tolist()).fillna(0).astype(int)
    X = pd.concat([X_headline, X_body], axis=1)

    # Load the trained model (assuming it was saved previously)
    model = ml_models.model

    if model is None:
        return jsonify({'status': 'error', 'message': 'Model not loaded'}), 500

    prediction = model.predict(X)
    logging.debug(f"Predicted location: {prediction[0]}")

    return jsonify({'predicted_location': prediction[0]})

# Scrape articles
@app.route('/scrape', methods=['GET'])
def scrape():
    logging.debug("Scraping articles")
    category_url = 'https://apnews.com/business'
    scraper_manager.scrape(category_url)
    return "Scraping complete"

# Load AP News Scraper
@app.route('/load_scraper', methods=['POST'])
def load_scraper():
    try:
        # Load the AP News scraper
        scraper_manager.load_scrapers()
        logging.info("AP News scraper loaded successfully")
        return jsonify({"status": "success", "message": "AP News scraper loaded successfully"})
    except Exception as e:
        logging.error(f"Error loading scraper: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

# Toggle ML Model
@app.route('/toggle_ml_model', methods=['POST'])
def toggle_ml_model():
    try:
        data = request.json
        ml_model_active = data.get('ml_model_active', False)

        # Update the ML model status in the scraper manager
        scraper_manager.ml_model_active = ml_model_active
        logging.info(f"ML model toggled: {ml_model_active}")

        return jsonify({"status": "success", "message": f"ML model toggled to {ml_model_active}"})
    except Exception as e:
        logging.error(f"Error toggling ML model: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

# Data Refresh
@app.route('/data_refresh', methods=['POST'])
def data_refresh():
    try:
        # Step 1: Trigger the news scraper to scrape new articles
        logging.info("Starting to scrape new articles...")
        scraper_manager.run_scrapers()  # Run all loaded scrapers
        logging.info("Scraping completed.")

        # Step 2: Process the newly scraped articles using the ML model (if activated)
        if scraper_manager.ml_model_active:
            logging.info("Processing articles with the ML model...")
            articles = Article.query.all()  # Fetch all articles from the database
            for article in articles:
                # Example: Use the ML model to predict something (e.g., location)
                prediction = ml_models.predict_location(article.headline, article.body)
                logging.debug(f"Predicted location for article {article.id}: {prediction}")
                # Update the article with the prediction (if needed)
                # article.predicted_location = prediction
                # db.session.commit()
            logging.info("ML model processing completed.")

        # Step 3: Reload markers and articles from the database
        markers = MapMarker.query.all()
        logging.info(f"Reloaded {len(markers)} markers from the database.")
        articles = Article.query.all()
        logging.info(f"Reloaded {len(articles)} articles from the database.")

        return jsonify({"status": "success", "message": "Data refreshed successfully"})
    except Exception as e:
        logging.error(f"Error refreshing data: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500

# Ensure the 'people' table exists and populate it
def ensure_people_table():
    inspector = inspect(db.engine)
    if not inspector.has_table('people'):
        db.create_all()

    # Populate 'people' table with unique entries from 'articles' table
    articles = db.session.query(Article).all()
    people_set = set(person.name.lower() for person in db.session.query(People).all())
    people_profiles = defaultdict(bool)  # Assume a profile checking function

    for article in articles:
        for person_name in re.split(r'[;,]', article.people):
            person_name = person_name.strip()
            if person_name and person_name.lower() not in people_set:
                people_set.add(person_name.lower())
                has_profile = people_profiles[person_name.lower()]
                new_person = People(name=person_name, has_profile=has_profile)
                db.session.add(new_person)
    db.session.commit()

# Get people
@app.route('/get_people', endpoint='get_people_list')
def get_people():
    # Ensure the 'people' table exists and populate it
    ensure_people_table()

    # Fetch people data
    people = db.session.query(People).all()
    people_list = [{'id': person.id, 'name': person.name, 'has_profile': 'Yes' if person.has_profile else 'No'} for person in people]

    return jsonify(people_list)

# Save profile
@app.route('/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    person_id = data.get('personId')
    first_name = data.get('firstName')
    last_name = data.get('lastName')
    address = data.get('address')
    address2 = data.get('address2')
    city = data.get('city')
    state = data.get('state')
    zip_code = data.get('zip')
    country = data.get('country')

    if not first_name or not last_name:
        return jsonify({'status': 'error', 'message': 'First Name and Last Name are required'}), 400

    full_name = f"{first_name} {last_name}"

    try:
        if person_id:
            # Update existing person
            person = People.query.get(person_id)
            if not person:
                return jsonify({'status': 'error', 'message': 'Person not found'}), 404
            old_name = person.name
            person.name = full_name
            person.has_profile = True
        else:
            # Add new person
            person = People(name=full_name, has_profile=True)
            db.session.add(person)
            db.session.commit()
            person_id = person.id
            old_name = None

        profile = Profile.query.filter_by(person_id=person_id).first()
        if profile:
            # Update existing profile
            profile.first_name = first_name
            profile.last_name = last_name
            profile.address = address
            profile.address2 = address2
            profile.city = city
            profile.state = state
            profile.zip_code = zip_code
            profile.country = country
        else:
            # Add new profile
            new_profile = Profile(
                person_id=person_id,
                first_name=first_name,
                last_name=last_name,
                address=address,
                address2=address2,
                city=city,
                state=state,
                zip_code=zip_code,
                country=country
            )
            db.session.add(new_profile)

        db.session.commit()

        # Remove old name if it exists without a profile
        if old_name and old_name != full_name:
            old_person = People.query.filter_by(name=old_name, has_profile=False).first()
            if old_person:
                db.session.delete(old_person)
                db.session.commit()

        return jsonify({'status': 'success', 'message': 'Profile saved successfully'})
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'A person with this name already exists.'}), 400

# Get profile
@app.route('/get_profile/<int:person_id>', methods=['GET'])
def get_profile(person_id):
    profile = Profile.query.filter_by(person_id=person_id).first()
    if profile:
        return jsonify({
            'first_name': profile.first_name,
            'last_name': profile.last_name,
            'address': profile.address,
            'address2': profile.address2,
            'city': profile.city,
            'state': profile.state,
            'zip_code': profile.zip_code,
            'country': profile.country
        })
    else:
        return jsonify({'status': 'error', 'message': 'Profile not found'}), 404

# Delete profile
@app.route('/delete_profile/<int:person_id>', methods=['DELETE'])
def delete_profile(person_id):
    logging.debug(f"Deleting profile with person ID: {person_id}")
    profile = Profile.query.filter_by(person_id=person_id).first()
    if profile:
        db.session.delete(profile)
        db.session.commit()
        person = People.query.get(person_id)
        if person:
            person.has_profile = False
            db.session.commit()
        logging.debug("Profile deleted")
        return jsonify({'status': 'success', 'message': 'Profile deleted successfully'})
    else:
        logging.debug("Profile not found")
        return jsonify({'status': 'error', 'message': 'Profile not found'}), 404

# Search articles by headline, person, location, or keyword
@app.route('/search_articles', methods=['GET'])
def search_articles():
    query = request.args.get('query', '')
    search_by = request.args.get('search_by', 'headline')

    if search_by == 'headline':
        articles = Article.query.filter(Article.headline.ilike(f'%{query}%')).all()
    elif search_by == 'person':
        articles = Article.query.filter(Article.people.ilike(f'%{query}%')).all()
    elif search_by == 'location':
        articles = Article.query.filter(Article.locations.ilike(f'%{query}%')).all()
    elif search_by == 'keyword':
        articles = Article.query.filter((Article.headline.ilike(f'%{query}%')) | (Article.body.ilike(f'%{query}%'))).all()
    else:
        return jsonify({'status': 'error', 'message': 'Invalid search_by parameter'}), 400

    article_list = [{'id': article.id, 'headline': article.headline, 'source': article.source, 'date': article.date, 'locations': article.locations, 'people': article.people, 'organizations': article.organizations} for article in articles]
    return jsonify(article_list)

# Get all articles
@app.route('/get_articles', methods=['GET'])
def get_articles():
    logging.debug("Getting all articles")
    articles = Article.query.all()
    article_list = [
        {
            "id": article.id,
            "headline": article.headline,
            "body": article.body,
            "date": article.date,
            "source": article.source,
            "people": article.people.split(';') if article.people else [],  # Convert to list
            "num_people": article.num_people,
            "locations": article.locations.split(';') if article.locations else [],  # Convert to list
            "organizations": article.organizations.split(';') if article.organizations else [],  # Convert to list
            "num_organizations": article.num_organizations,
            "url": article.url
        }
        for article in articles
    ]
    return jsonify(article_list)

@app.route('/remove_duplicates', methods=['POST'])
def remove_duplicates_route():
    remove_duplicate_articles()
    remove_duplicate_map_markers()
    ensure_corresponding_map_markers()  # Ensure this is called after removing duplicates
    return jsonify({"status": "success", "message": "Duplicates removed and map markers refreshed"})



# Ensure the 'profiles_ppl' table exists
def ensure_profiles_table():
    inspector = inspect(db.engine)
    if not inspector.has_table('profiles_ppl'):
        db.create_all()

# Call this function when the app starts to ensure the profiles_ppl table exists
ensure_profiles_table()