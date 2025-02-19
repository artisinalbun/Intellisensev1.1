from flask import Blueprint, request, jsonify, render_template
from sqlalchemy.sql import text
from app.models import db, MapMarker, Article
from app.utils import extract_locations, geocode_location, Trace, validate_coordinates
from geoalchemy2 import WKTElement
from shapely.geometry import Point
from app.data_manager import DataManager
from app.ml_models import MLModels
import logging
import joblib
import pandas as pd
from transformers import BertTokenizer

# Create a Blueprint for the developer tool
dev_app = Blueprint('dev', __name__)

data_manager = DataManager()
ml_models = MLModels(data_manager)
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

@dev_app.route("/trace_location", methods=["POST", "OPTIONS"])
def trace_location():
    if request.method == "OPTIONS":
        logging.debug("Handling OPTIONS preflight request for /dev/trace_location")
        return jsonify({"status": "success"}), 200

    logging.debug("trace_location endpoint called")
    
    if not request.is_json:
        logging.error("Request Content-Type is not application/json")
        return jsonify({"status": "error", "message": "Content-Type must be application/json"}), 415
    
    data = request.get_json()
    logging.debug(f"Received data: {data}")
    
    if not data:
        logging.error("No data received in request")
        return jsonify({"status": "error", "message": "No data received"}), 400

    article_id = data.get("article_id")
    headline = data.get("headline")
    logging.debug(f"Processing article_id: {article_id}, headline: {headline}")

    trace = Trace()
    try:
        if article_id:
            logging.debug(f"Processing article_id: {article_id}")
            article = db.session.query(Article).filter_by(id=article_id).first()
            if article:
                headline = article.headline
                body = article.body
                locations = extract_locations(headline, body, trace)
                trace.add_step("Extracted locations", locations)
                if locations:
                    lon, lat = geocode_location(locations[0], trace)
                    trace.add_step("Geocoded location", {"lon": lon, "lat": lat})
                    if validate_coordinates(lon, lat, locations[0]):
                        trace.add_step("Validated coordinates", {"lon": lon, "lat": lat})
                        return jsonify(trace.get_trace())
                    else:
                        trace.add_step("Invalid coordinates", {"lon": lon, "lat": lat})
                        return jsonify(trace.get_trace()), 404
                else:
                    trace.add_step("No locations found")
                    return jsonify(trace.get_trace()), 404
            else:
                trace.add_step("Article not found", {"article_id": article_id})
                return jsonify(trace.get_trace()), 404
        elif headline:
            logging.debug(f"Processing headline: {headline}")
            locations = extract_locations(headline, "", trace)
            trace.add_step("Extracted locations", locations)
            if locations:
                lon, lat = geocode_location(locations[0], trace)
                trace.add_step("Geocoded location", {"lon": lon, "lat": lat})
                if validate_coordinates(lon, lat, locations[0]):
                    trace.add_step("Validated coordinates", {"lon": lon, "lat": lat})
                    return jsonify(trace.get_trace())
                else:
                    trace.add_step("Invalid coordinates", {"lon": lon, "lat": lat})
                    return jsonify(trace.get_trace()), 404
            else:
                trace.add_step("No locations found")
                return jsonify(trace.get_trace()), 404
        else:
            trace.add_step("No valid input provided")
            return jsonify(trace.get_trace()), 400
        
    except Exception as e:
        logging.error(f"Error in trace_location: {str(e)}", exc_info=True)
        trace.add_step("Exception occurred", str(e))
        return jsonify(trace.get_trace()), 500

@dev_app.route("/articles", methods=["GET"])
def get_articles():
    filter_no_markers = request.args.get("filter_no_markers", "false").lower() == "true"
    logging.debug(f"Fetching articles with filter_no_markers: {filter_no_markers}")
    try:
        if filter_no_markers:
            articles = db.session.query(Article).outerjoin(MapMarker, Article.id == MapMarker.article_id).filter(MapMarker.id.is_(None)).all()
        else:
            articles = db.session.query(Article).all()

        logging.debug(f"Fetched {len(articles)} articles")

        articles_with_marker_info = []
        for article in articles:
            has_marker = db.session.query(MapMarker).filter_by(article_id=article.id).first() is not None
            article_dict = article.as_dict()
            article_dict["has_marker"] = "Yes" if has_marker else "No"
            articles_with_marker_info.append(article_dict)

        return jsonify(articles_with_marker_info)
    except Exception as e:
        logging.error(f"Error in get_articles: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@dev_app.route("/reprocess_articles", methods=["POST", "OPTIONS"])
def reprocess_articles():
    if request.method == "OPTIONS":
        logging.debug("Handling OPTIONS preflight request for /dev/reprocess_articles")
        return jsonify({"status": "success"}), 200

    data = request.get_json()
    article_ids = data.get("article_ids", [])
    logging.debug(f"Reprocessing articles with IDs: {article_ids}")

    trace = Trace()
    reprocessed_results = []

    try:
        for article_id in article_ids:
            logging.debug(f"Processing article_id: {article_id}")
            article = db.session.query(Article).filter_by(id=article_id).first()
            if article:
                headline = article.headline
                body = article.body
                locations = extract_locations(headline, body, trace)
                if locations:
                    lon, lat = geocode_location(locations[0], trace)
                    if validate_coordinates(lon, lat, locations[0]):
                        map_marker = db.session.query(MapMarker).filter_by(article_id=article_id).first()
                        if not map_marker:
                            map_marker = MapMarker(name=article.headline, location=WKTElement(Point(lon, lat).wkt, srid=4326), article_id=article_id)
                            db.session.add(map_marker)
                        else:
                            map_marker.location = WKTElement(Point(lon, lat).wkt, srid=4326)
                        db.session.commit()
                        reprocessed_results.append({
                            "article_id": article_id,
                            "trace": trace.get_trace()
                        })
                    else:
                        reprocessed_results.append({
                            "article_id": article_id,
                            "error": "Invalid coordinates"
                        })
                else:
                    reprocessed_results.append({
                        "article_id": article_id,
                        "error": "No locations found"
                    })
            else:
                reprocessed_results.append({
                    "article_id": article_id,
                    "error": "Article not found"
                })

        return jsonify(reprocessed_results)
    
    except Exception as e:
        logging.error(f"Error in reprocess_articles: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@dev_app.route("/annotate")
def annotate():
    logging.debug("Rendering annotate.html")
    return render_template("annotate.html")

@dev_app.route("/training")
def training():
    logging.debug("Rendering training.html")
    return render_template("training.html")

@dev_app.route("/ml_articles", methods=["GET"])
def get_ml_articles():
    logging.debug("Fetching ml_articles for annotation")
    try:
        query = text("SELECT id, correct_location, headline, body, url FROM ml_articles")
        ml_articles = db.session.execute(query).fetchall()
        ml_articles_data = [
            {
                "id": article.id,
                "correct_location": article.correct_location,
                "headline": article.headline,
                "body": article.body,
                "url": article.url
            }
            for article in ml_articles
        ]
        return jsonify(ml_articles_data)
    except Exception as e:
        logging.error(f"Error fetching ml_articles: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@dev_app.route("/save_annotations", methods=["POST"])
def save_annotations():
    logging.debug("Saving annotations for ml_articles")
    data = request.get_json()
    annotations = data.get("annotations", [])

    try:
        for annotation in annotations:
            article_id = annotation.get("id")
            correct_location = annotation.get("correct_location")
            query = text("UPDATE ml_articles SET correct_location = :correct_location WHERE id = :id")
            db.session.execute(query, {"correct_location": correct_location, "id": article_id})
        db.session.commit()
        logging.debug("Annotations saved successfully")
        return jsonify({"status": "success"})
    except Exception as e:
        logging.error(f"Error saving annotations: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@dev_app.route("/process_data", methods=["GET"])
def process_data():
    table = request.args.get('table')
    logging.debug(f"Processing data from table: {table}")

    try:
        data_manager.load_articles()
        data_manager.clean_data()
        data_manager.tokenize_data()
        logging.debug("Data processed and tokenized")
        return jsonify({"status": "success", "message": "Data processed and tokenized"})
    except Exception as e:
        logging.error(f"Error processing data: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@dev_app.route("/train_model", methods=["POST"])
def train_model():
    logging.debug("Training model")
    try:
        model, accuracy = ml_models.train_model()
        logging.debug(f"Model trained with accuracy: {accuracy}")
        return jsonify({"status": "success", "message": "Model trained", "accuracy": accuracy})
    except Exception as e:
        logging.error(f"Error training model: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@dev_app.route("/load_table", methods=["GET"])
def load_table():
    table = request.args.get('table')
    logging.debug(f"Loading table: {table}")

    try:
        query = text(f"SELECT id, headline, body FROM {table}")
        articles = db.session.execute(query).fetchall()
        articles_data = [
            {
                "id": article.id,
                "headline": article.headline,
                "body": article.body
            }
            for article in articles
        ]
        return jsonify(articles_data)
    except Exception as e:
        logging.error(f"Error loading table: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@dev_app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json()
    table = data.get('table')
    model_path = data.get('model')
    logging.debug(f"Predicting using model: {model_path} on table: {table}")

    try:
        model = joblib.load(model_path)
        logging.debug("Model loaded")

        query = text(f"SELECT id, headline, body FROM {table}")
        articles = db.session.execute(query).fetchall()
        articles_data = [
            {
                "id": article.id,
                "headline": article.headline,
                "body": article.body
            }
            for article in articles
        ]

        df = pd.DataFrame(articles_data)
        df['tokenized_headline'] = df['headline'].apply(lambda x: tokenizer.encode(x, add_special_tokens=True))
        df['tokenized_body'] = df['body'].apply(lambda x: tokenizer.encode(x, add_special_tokens=True))

        X = df[['tokenized_headline', 'tokenized_body']]
        X_headline = pd.DataFrame(X['tokenized_headline'].tolist()).fillna(0).astype(int)
        X_body = pd.DataFrame(X['tokenized_body'].tolist()).fillna(0).astype(int)
        X = pd.concat([X_headline, X_body], axis=1)

        predictions = model.predict(X)
        for i, prediction in enumerate(predictions):
            articles_data[i]['predicted_location'] = prediction

        logging.debug("Predictions made")

        # Save predictions to a new table
        new_table_name = 'predicted_articles'
        db.session.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {new_table_name} (
                id SERIAL PRIMARY KEY,
                original_id INTEGER,
                headline TEXT,
                body TEXT,
                predicted_location TEXT
            )
        """))

        for article in articles_data:
            db.session.execute(text(f"""
                INSERT INTO {new_table_name} (original_id, headline, body, predicted_location)
                VALUES (:original_id, :headline, :body, :predicted_location)
            """), {
                'original_id': article['id'],
                'headline': article['headline'],
                'body': article['body'],
                'predicted_location': article['predicted_location']
            })
        
        db.session.commit()
        logging.debug(f"Predictions saved to table {new_table_name}")

        return jsonify(articles_data)
    except Exception as e:
        logging.error(f"Error making predictions: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@dev_app.route("/integrate_map_markers", methods=["POST"])
def integrate_map_markers():
    logging.debug("Integrating map markers")
    try:
        query = text("SELECT id, original_id, headline, predicted_location FROM predicted_articles")
        predicted_articles = db.session.execute(query).fetchall()
        
        for article in predicted_articles:
            trace = Trace()
            locations = extract_locations(article.predicted_location, "", trace)
            if locations:
                lon, lat = geocode_location(locations[0], trace)
                if validate_coordinates(lon, lat, locations[0]):
                    map_marker = db.session.query(MapMarker).filter_by(article_id=article.original_id).first()
                    if not map_marker:
                        map_marker = MapMarker(name=article.headline, location=WKTElement(Point(lon, lat).wkt, srid=4326), article_id=article.original_id)
                        db.session.add(map_marker)
                    else:
                        map_marker.location = WKTElement(Point(lon, lat).wkt, srid=4326)
                    db.session.commit()

        # Remove duplicates
        db.session.execute(text("""
            DELETE FROM map_markers
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT id, ROW_NUMBER() OVER (PARTITION BY name, article_id ORDER BY id) AS rnum
                    FROM map_markers
                ) t
                WHERE t.rnum > 1
            )
        """))
        db.session.commit()

        logging.debug("Map markers integration complete")
        return jsonify({"status": "success", "message": "Map markers integrated successfully"})
    except Exception as e:
        logging.error(f"Error integrating map markers: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@dev_app.route("/")
def index():
    logging.debug("Rendering dev.html")
    return render_template("dev.html")