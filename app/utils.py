import re
from transformers import pipeline
import requests
import torch
import logging
from app.models import db, MapMarker, Article
from geoalchemy2 import WKTElement
from shapely.geometry import Point
from sqlalchemy import func
import threading
from queue import Queue

# Load the Hugging Face NER pipeline
device = 0 if torch.cuda.is_available() else -1  # Use GPU if available, otherwise CPU
ner_pipeline = pipeline("ner", aggregation_strategy="simple", model="dslim/bert-base-NER", device=device)
logging.debug("NER pipeline initialized")

def extract_locations(headline, body, trace):
    """Extract locations using a combination of Hugging Face NER and custom rules."""
    full_text = f"{headline} {body}"
    trace.add_step("Combined headline and body for analysis", full_text)
    logging.debug(f"Full text for NER: {full_text}")
    
    entities = ner_pipeline(full_text)
    locations = [entity["word"] for entity in entities if entity["entity_group"] == "LOC"]
    trace.add_step("Locations extracted using Hugging Face NER", locations)
    logging.debug(f"Extracted locations: {locations}")
    
    # Remove duplicates and limit to 3 locations
    unique_locations = list(set(locations))[:3]
    return unique_locations

def geocode_location(location_name, trace):
    """Geocode a location using Google Maps Geocoding API."""
    trace.add_step("Geocoding location", location_name)
    logging.debug(f"Geocoding location: {location_name}")
    
    params = {
        "address": location_name,
        "key": "AIzaSyC2aRqT60uAdaeeUjcY7bB1V7E7fztKfII"
    }

    try:
        response = requests.get(
            "https://maps.googleapis.com/maps/api/geocode/json",
            params=params,
            timeout=10
        )
        data = response.json()
        trace.add_step("Google Maps API response", data)
        logging.debug(f"Google Maps API response: {data}")
        
        if response.status_code == 200 and data["status"] == "OK":
            if len(data["results"]) > 0:
                result = data["results"][0]
                lon = result["geometry"]["location"]["lng"]
                lat = result["geometry"]["location"]["lat"]
                logging.debug(f"Raw coordinates for {location_name}: ({lon}, {lat})")
                if validate_coordinates(lon, lat, location_name):  # Validate coordinates before returning
                    trace.add_step(f"Geocoded coordinates for {location_name}", (lon, lat))
                    logging.debug(f"Geocoded coordinates: {lon}, {lat}")
                    return lon, lat
                else:
                    logging.debug(f"Coordinates validation failed for {location_name}: ({lon}, {lat})")
            else:
                trace.add_step("No results found in Google Maps API response", data)
                logging.debug("No results found in Google Maps API response")
        else:
            trace.add_step("Google Maps API returned an error", data)
            logging.debug(f"Google Maps API error: {data['status']}")
    except Exception as e:
        trace.add_step("Geocoding error", str(e))
        logging.error(f"Geocoding error: {e}")
    
    return None, None

def validate_coordinates(lon, lat, location_name):
    """Check if coordinates are valid and reasonable."""
    logging.debug(f"Validating coordinates: {lon}, {lat} for location: {location_name}")
    if not lon or not lat:
        logging.debug("Coordinates are None")
        return False
    
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        logging.debug("Coordinates out of bounds")
        return False
    
    lower_name = location_name.lower()
    if "london" in lower_name:
        valid = (-0.5 < lon < 0.5) and (51.0 < lat < 52.0)
        if not valid:
            logging.debug(f"Coordinates for London are invalid: ({lon}, {lat})")
        return valid
    if "new york" in lower_name or "wall street" in lower_name:
        valid = (-74.5 < lon < -73.5) and (40.5 < lat < 41.0)
        if not valid:
            logging.debug(f"Coordinates for New York are invalid: ({lon}, {lat})")
        return valid
    if "washington" in lower_name or "federal reserve" in lower_name:
        valid = (-77.5 < lon < -76.5) and (38.5 < lat < 39.0)
        if not valid:
            logging.debug(f"Coordinates for Washington are invalid: ({lon}, {lat})")
        return valid
    
    return True

def format_postgis_geometry(lat, lon):
    """Format coordinates into PostGIS geometry format."""
    return f'SRID=4326;POINT({lon} {lat})'

def remove_duplicate_articles():
    """Delete duplicate articles from the articles table."""
    db.session.query(Article).filter(
        Article.id.notin_(
            db.session.query(func.min(Article.id)).group_by(Article.headline, Article.body).having(func.count(Article.id) == 1)
        )
    ).delete(synchronize_session=False)
    db.session.commit()

def remove_duplicate_map_markers():
    """Remove duplicate map markers from the map_markers table."""
    logging.debug("Removing duplicate map markers...")
    try:
        # Find duplicate map markers based on name and article_id
        subquery = db.session.query(
            func.min(MapMarker.id).label('id')
        ).group_by(MapMarker.name, MapMarker.article_id).subquery()

        # Log the IDs that will be kept
        unique_ids = [row.id for row in db.session.query(subquery)]
        logging.debug(f"Unique map marker IDs to keep: {unique_ids}")

        # Delete map markers that are not in the subquery
        num_deleted = db.session.query(MapMarker).filter(
            MapMarker.id.notin_(subquery)
        ).delete(synchronize_session=False)

        db.session.commit()
        logging.debug(f"Duplicate map markers removed successfully. Number of map markers deleted: {num_deleted}")
    except Exception as e:
        logging.error(f"Error removing duplicate map markers: {e}")
        db.session.rollback()

is_ensuring_markers = False

def ensure_corresponding_map_markers():
    """Ensure that every article has a corresponding map marker."""
    global is_ensuring_markers
    if is_ensuring_markers:
        logging.debug("ensure_corresponding_map_markers is already running; skipping")
        return

    is_ensuring_markers = True
    try:
        logging.debug("Ensuring corresponding map markers for all articles...")
        articles = Article.query.all()
        for article in articles:
            existing_marker = MapMarker.query.filter_by(article_id=article.id).first()
            if not existing_marker:
                locations = extract_locations(article.headline, article.body, Trace())
                if locations:
                    location_name = locations[0]
                    lon, lat = geocode_location(location_name, Trace())
                    if lon and lat:
                        location = format_postgis_geometry(lat, lon)
                        logging.debug(f"Creating map marker for article: {article.id}")
                        new_marker = MapMarker(name=article.headline, location=location, article_id=article.id)
                        db.session.add(new_marker)
                        logging.debug(f"Map marker created for article: {article.id}")
                        try:
                            db.session.commit()
                            logging.debug(f"Map marker committed for article: {article.id}")
                        except Exception as e:
                            db.session.rollback()
                            logging.error(f"Error committing map marker for article {article.id}: {e}")
        logging.debug("Ensured corresponding map markers for all articles")
    except Exception as e:
        logging.error(f"Error in ensure_corresponding_map_markers: {e}")
    finally:
        is_ensuring_markers = False

def update_map_marker_locations():
    """Update the locations of map markers."""
    logging.debug("Updating map marker locations...")
    map_markers = MapMarker.query.all()
    for marker in map_markers:
        lon, lat = geocode_location(marker.name, Trace())
        if lon and lat and validate_coordinates(lon, lat, marker.name):  # Validate coordinates before updating
            location = format_postgis_geometry(lat, lon)
            marker.location = location
            db.session.add(marker)
    db.session.commit()
    logging.debug("Updated map marker locations")

def repopulate_map_markers():
    """Repopulate the map_markers table from the articles table if necessary."""
    logging.debug("Repopulating map markers from articles...")
    if MapMarker.query.count() == 0:  # Only repopulate if the table is empty
        articles = Article.query.all()
        for article in articles:
            existing_marker = MapMarker.query.filter_by(article_id=article.id).first()
            if not existing_marker:
                locations = extract_locations(article.headline, article.body, Trace())
                if locations:
                    location_name = locations[0]
                    lon, lat = geocode_location(location_name, Trace())
                    if lon and lat:
                        location = format_postgis_geometry(lat, lon)
                        new_marker = MapMarker(name=article.headline, location=location, article_id=article.id)
                        db.session.add(new_marker)
        db.session.commit()
        logging.debug("Repopulated map markers from articles")
    else:
        logging.debug("Map markers table is not empty; skipping repopulation")

class Trace:
    def __init__(self):
        self.steps = []
        logging.debug("Trace initialized")

    def add_step(self, description, data=None):
        self.steps.append({"description": description, "data": data})
        logging.debug(f"Trace step added: {description}, {data}")

    def get_trace(self):
        logging.debug(f"Returning trace: {self.steps}")
        return self.steps