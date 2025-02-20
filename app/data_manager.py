import pandas as pd
from app.models import DataEntry, Article
from app.database import db
from transformers import BertTokenizer
import logging

class DataManager:
    def __init__(self):
        self.df = pd.DataFrame(columns=[
            'headline', 'body', 'correct_location'
        ])
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')  # Initialize tokenizer
        logging.debug("DataManager initialized with empty DataFrame")
    
    def load_data_from_db(self):
        logging.debug("Loading data from database")
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
        logging.debug(f"Data loaded into DataFrame: {self.df}")

    def load_articles(self):
        logging.debug("Loading articles from database")
        articles = db.session.execute("SELECT id, headline, body, correct_location FROM ml_articles").fetchall()
        data = [
            {
                'id': article.id,
                'headline': article.headline,
                'body': article.body,
                'correct_location': article.correct_location
            }
            for article in articles
        ]
        self.df = pd.DataFrame(data)
        logging.debug(f"Articles loaded into DataFrame: {self.df}")

    def clean_data(self):
        logging.debug("Cleaning data")
        # Remove null values and duplicates
        self.df.dropna(subset=['headline', 'body', 'correct_location'], inplace=True)
        self.df.drop_duplicates(subset=['headline', 'body'], inplace=True)
        logging.debug(f"Cleaned DataFrame: {self.df}")

    def tokenize_data(self):
        logging.debug("Tokenizing data")
        # Use the tokenizer instance initialized in __init__
        self.df['tokenized_headline'] = self.df['headline'].apply(lambda x: self.tokenizer.encode(x, add_special_tokens=True))
        self.df['tokenized_body'] = self.df['body'].apply(lambda x: self.tokenizer.encode(x, add_special_tokens=True))
        logging.debug(f"Tokenized DataFrame: {self.df}")

    def tokenize_text(self, text):
        """Tokenize a single piece of text using the BERT tokenizer."""
        return self.tokenizer.encode(text, add_special_tokens=True)


    def get_dataframe(self):
        logging.debug(f"Returning DataFrame: {self.df}")
        return self.df