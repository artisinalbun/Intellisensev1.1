from flask import Flask
from flask_cors import CORS
from app.database import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.Config')
    CORS(app)

    init_db(app)

    with app.app_context():
        from app import routes

    return app