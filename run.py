from flask import Flask
from flask_cors import CORS
from app import create_app
import os
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("application.log"),
        logging.StreamHandler()
    ]
)

logging.debug("Starting application setup...")

start_time = time.time()
app = create_app()
logging.debug(f"Application created in {time.time() - start_time:.2f} seconds")

@app.route('/')
def index():
    return "Main Application"

if __name__ == '__main__':
    logging.debug("Starting Flask application...")
    print(app.url_map)  # Add this line to print the URL map
    app.run(debug=True)