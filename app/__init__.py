from flask import Flask
from flask_cors import CORS
from app.database import init_db, db
from app.devflask import dev_app  # Import the developer tool blueprint
from app.utils import update_map_marker_locations, repopulate_map_markers  # Import the repopulate function
from app.models import MapMarker, Article  # Import Article model
import logging
from sqlalchemy import func

logging.basicConfig(level=logging.DEBUG)

def create_app():
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

        # Remove duplicate map markers
        db.session.query(MapMarker).filter(
            MapMarker.id.notin_(
                db.session.query(func.min(MapMarker.id)).group_by(MapMarker.name, MapMarker.article_id).having(func.count(MapMarker.id) > 1)
            )
        ).delete(synchronize_session=False)
        db.session.commit()
        logging.debug("Removed duplicate map markers")

        # Repopulate map markers from articles (only if necessary)
        if MapMarker.query.count() == 0 or Article.query.count() > MapMarker.query.count():
            repopulate_map_markers()  # Call the repopulate function
            logging.debug("Repopulated map markers from articles (if necessary)")
        else:
            logging.debug("Map markers table is not empty; skipping repopulation")

        # Update map marker locations
        update_map_marker_locations()
        logging.debug("Updated map marker locations")

        # Log all registered routes
        logging.debug("Registered routes:")
        for rule in app.url_map.iter_rules():
            logging.debug(f"Route: {rule}")

    return app