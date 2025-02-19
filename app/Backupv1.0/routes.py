from flask import Blueprint, request, jsonify, render_template
from app.data_manager import DataManager
from app.ml_models import MLModels
from app.models import db, DataEntry, Article, MapMarker
from geoalchemy2 import WKTElement
from shapely.geometry import Point
from scrapers.scraper_manager import ScraperManager

app = Blueprint('app', __name__)

data_manager = DataManager()
scraper_manager = ScraperManager()
scraper_manager.load_scrapers()

# Homepage with map and start scraper
@app.route('/')
def index():
    return render_template('index.html')

# Add a marker
@app.route('/add_marker', methods=['POST'])
def add_marker():
    data = request.json
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

    return jsonify({"status": "success", "marker": {"id": new_marker.id, "name": name, "lat": lat, "lon": lon, "article_id": article_id}})

# Delete a marker
@app.route('/delete_marker/<int:marker_id>', methods=['DELETE'])
def delete_marker(marker_id):
    marker = MapMarker.query.get(marker_id)
    if marker:
        db.session.delete(marker)
        db.session.commit()
        return jsonify({"status": "success", "message": "Marker deleted"})
    else:
        return jsonify({"status": "error", "message": "Marker not found"}), 404

# Update marker position
@app.route('/update_marker/<int:marker_id>', methods=['PUT'])
def update_marker(marker_id):
    data = request.json
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
        return jsonify({"status": "success", "message": "Marker updated"})
    else:
        return jsonify({"status": "error", "message": "Marker not found"}), 404

# Get all markers
@app.route('/get_markers', methods=['GET'])
def get_markers():
    markers = MapMarker.query.all()
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [marker.location.x, marker.location.y]
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
    return jsonify(geojson)

# Get article by ID
@app.route('/get_article/<int:article_id>', methods=['GET'])
def get_article(article_id):
    article = Article.query.get(article_id)
    if article:
        return jsonify({
            "headline": article.headline,
            "body": article.body
        })
    else:
        return jsonify({"status": "error", "message": "Article not found"}), 404

# Add data entry
@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    data_manager.add_data(**data)
    return jsonify({'status': 'success'})

# Train model
@app.route('/train_model', methods=['POST'])
def train_model():
    ml_models = MLModels(data_manager)
    model, accuracy = ml_models.train_model()
    return jsonify({'accuracy': accuracy})

# Scrape articles
@app.route('/scrape', methods=['GET'])
def scrape():
    category_url = 'https://apnews.com/business'
    scraper_manager.scrape(category_url)
    return "Scraping complete"