from flask import Flask
from flask_cors import CORS
from app.database import init_db
from app.devflask import dev_app  # Import the developer tool blueprint
import logging

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

        # Log all registered routes
        logging.debug("Registered routes:")
        for rule in app.url_map.iter_rules():
            logging.debug(f"Route: {rule}")

    return app