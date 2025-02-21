from app.database import db
from geoalchemy2 import Geometry
from shapely import wkb
import logging

class DataEntry(db.Model):
    __tablename__ = 'data_entries'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    organization = db.Column(db.String(100), nullable=False)
    people = db.Column(db.String(100), nullable=False)
    other_data = db.Column(db.JSON, nullable=True)

class Article(db.Model):
    __tablename__ = 'articles'
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
    tags = db.Column(db.Text)
    
    def as_dict(self):
        return {
            "id": self.id,
            "url": self.url,
            "headline": self.headline,
            "body": self.body,
            "date": self.date,
            "source": self.source,
            "people": self.people,
            "num_people": self.num_people,
            "locations": self.locations,
            "organizations": self.organizations,
            "num_organizations": self.num_organizations,
            "profiles": self.profiles,
            "tags": self.tags
        }

class MapMarker(db.Model):
    __tablename__ = 'map_markers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    location = db.Column(Geometry('POINT'), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey('articles.id'), nullable=False)
    article = db.relationship('Article', backref=db.backref('map_markers', lazy=True))

    def as_dict(self):
        location_point = wkb.loads(bytes(self.location.data))
        return {
            "id": self.id,
            "name": self.name,
            "location": (location_point.x, location_point.y) if self.location else None,
            "article_id": self.article_id
        }

class People(db.Model):
    __tablename__ = 'people'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    has_profile = db.Column(db.Boolean, nullable=False, default=False)

class Profile(db.Model):
    __tablename__ = 'profiles_ppl'
    id = db.Column(db.Integer, primary_key=True)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255))
    address2 = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(100))
    zip_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    person = db.relationship('People', backref=db.backref('profiles', lazy=True))
