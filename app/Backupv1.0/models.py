from app.database import db
from geoalchemy2 import Geometry

class DataEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    organization = db.Column(db.String(100), nullable=False)
    people = db.Column(db.String(100), nullable=False)
    other_data = db.Column(db.JSON, nullable=True)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.Text, nullable=False)
    headline = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    date = db.Column(db.Text, nullable=False)
    source = db.Column(db.Text)
    people = db.Column(db.Text)
    num_people = db.Column(db.Integer)
    locations = db.Column(db.Text)
    organizations = db.Column(db.Text)
    num_organizations = db.Column(db.Integer)
    profiles = db.Column(db.Integer)

class MapMarker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    location = db.Column(Geometry('POINT'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('article.id'), nullable=False)