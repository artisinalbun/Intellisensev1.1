from flask import Flask
from flask_cors import CORS
from app.database import init_db, db
from app.devflask import dev_app  # Import the developer tool blueprint
from app.utils import remove_duplicate_map_markers, ensure_corresponding_map_markers  # Import the necessary functions
from app.models import MapMarker, Article  # Import Article model
import logging
from sqlalchemy import func
import time

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("application.log"),
        logging.StreamHandler()
    ]
)

def create_app():
    logging.debug("Creating Flask application...")
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    CORS(app)

    init_db(app)
    logging.debug("Database initialized")

    with app.app_context():
        from app.routes import app as routes_blueprint
        app.register_blueprint(routes_blueprint, url_prefix='/app')
        logging.debug("Routes blueprint registered with prefix '/app'")

        
        # Register the developer tool blueprint
        app.register_blueprint(dev_app, url_prefix='/dev')
        logging.debug("Developer tool blueprint registered with prefix '/dev'")

        # Check if map markers already exist
        if MapMarker.query.count() == 0:
            logging.debug("No map markers found, initializing...")
            # Remove duplicate map markers
            remove_duplicate_map_markers()

            # Ensure corresponding map markers for all articles
            ensure_corresponding_map_markers()
            logging.debug("Ensured corresponding map markers for all articles")
        else:
            logging.debug("Map markers already exist, skipping initialization")

        # Log all registered routes
        logging.debug("Registered routes:")
        for rule in app.url_map.iter_rules():
            logging.debug(f"Route: {rule}")

    return app