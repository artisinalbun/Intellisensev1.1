import pandas as pd
from app.models import DataEntry
from app.database import db

class DataManager:
    def __init__(self):
        self.df = pd.DataFrame(columns=[
            'timestamp', 'location', 'topic', 'organization', 'people', 'other_data'
        ])
    
    def load_data_from_db(self):
        data_entries = DataEntry.query.all()
        data = [
            {
                'timestamp': entry.timestamp,
                'location': entry.location,
                'topic': entry.topic,
                'organization': entry.organization,
                'people': entry.people,
                'other_data': entry.other_data
            }
            for entry in data_entries
        ]
        self.df = pd.DataFrame(data)
    
    def add_data(self, timestamp, location, topic, organization, people, other_data=None):
        new_entry = DataEntry(
            timestamp=timestamp,
            location=location,
            topic=topic,
            organization=organization,
            people=people,
            other_data=other_data
        )
        db.session.add(new_entry)
        db.session.commit()
        self.load_data_from_db()
    
    def get_dataframe(self):
        return self.df