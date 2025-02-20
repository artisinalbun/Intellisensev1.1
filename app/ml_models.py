from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pandas as pd
import logging
import joblib
import os
from app.data_manager import DataManager  # Corrected import

class MLModels:
    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.model = None
        logging.debug("MLModels initialized with DataManager")
    
    def train_model(self):
        logging.debug("Training model with data from DataManager")
        df = self.data_manager.get_dataframe()
        X = df[['tokenized_headline', 'tokenized_body']]
        y = df['correct_location']  # Target variable
        
        # Flatten the tokenized columns
        X_headline = pd.DataFrame(X['tokenized_headline'].tolist()).fillna(0).astype(int)
        X_body = pd.DataFrame(X['tokenized_body'].tolist()).fillna(0).astype(int)
        X = pd.concat([X_headline, X_body], axis=1)
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logging.debug(f"Model trained with accuracy: {accuracy}")
        self.model = model  # Save the trained model

        # Save the model
        joblib.dump(model, 'trained_model.pkl')
        logging.debug("Model saved as 'trained_model.pkl'")
        
        return model, accuracy

    def load_model(self):
        if os.path.exists('trained_model.pkl'):
            self.model = joblib.load('trained_model.pkl')
            logging.debug("Model loaded from 'trained_model.pkl'")
        else:
            logging.warning("Model file 'trained_model.pkl' does not exist")
            self.model = None

    def predict_location(self, article):
        if not self.model:
            logging.error("Model not loaded. Call load_model() first.")
            return None

        # Tokenize headline and body
        tokenized_headline = self.data_manager.tokenize_text(article.headline)
        tokenized_body = self.data_manager.tokenize_text(article.body)

        # Flatten the tokenized columns
        X_headline = pd.DataFrame([tokenized_headline]).fillna(0).astype(int)
        X_body = pd.DataFrame([tokenized_body]).fillna(0).astype(int)
        X = pd.concat([X_headline, X_body], axis=1)

        predicted_location = self.model.predict(X)
        return predicted_location[0]

def run_model_on_articles(articles):
    data_manager = DataManager()  # Assuming DataManager is defined elsewhere
    ml_model = MLModels(data_manager)
    ml_model.load_model()

    results = []
    for article in articles:
        predicted_location = ml_model.predict_location(article)
        article['predicted_location'] = predicted_location
        results.append(article)

    return results