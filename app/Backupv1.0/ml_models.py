from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pandas as pd

class MLModels:
    def __init__(self, data_manager):
        self.data_manager = data_manager
    
    def train_model(self):
        df = self.data_manager.get_dataframe()
        X = df[['location', 'topic', 'organization', 'people']]
        y = df['other_data']  # Assuming 'other_data' contains the target variable
        
        # Encoding categorical variables
        X = pd.get_dummies(X)
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        model = RandomForestClassifier(n_estimators=100, random_state=42)
        model.fit(X_train, y_train)
        
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        return model, accuracy