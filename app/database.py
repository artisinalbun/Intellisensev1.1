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