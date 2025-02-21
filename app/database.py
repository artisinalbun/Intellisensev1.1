from flask_sqlalchemy import SQLAlchemy
import logging

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    logging.debug("SQLAlchemy initialized with Flask app")

def create_tables(app):
    with app.app_context():
        db.create_all()
        logging.debug("Database tables created")

def bulk_save_objects(objects):
    """Save multiple objects to the database in a single transaction."""
    try:
        db.session.bulk_save_objects(objects)
        db.session.commit()
        logging.debug(f"Bulk saved {len(objects)} objects to the database")
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error bulk saving objects: {e}")