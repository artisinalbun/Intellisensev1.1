from app import create_app
from app.models import MapMarker, Article
from app.database import db
from app.utils import geocode_location, Trace, format_postgis_geometry

app = create_app()

def update_map_marker_locations():
    with app.app_context():
        map_markers = MapMarker.query.all()
        for marker in map_markers:
            lon, lat = geocode_location(marker.name, Trace())
            if lon and lat:
                location = format_postgis_geometry(lat, lon)
                marker.location = location
                db.session.add(marker)
        db.session.commit()

update_map_marker_locations()