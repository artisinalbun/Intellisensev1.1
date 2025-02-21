from flask import Flask
from flask_cors import CORS
from app import create_app
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("application.log"),
        logging.StreamHandler()
    ]
)

app = create_app()

@app.route('/')
def index():
    return "Main Application"

if __name__ == '__main__':
    print(app.url_map)  # Add this line to print the URL map
    app.run(debug=True)