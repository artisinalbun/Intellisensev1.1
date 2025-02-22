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

logging.debug("Logging is configured and working.")

from flask import Flask
from flask_cors import CORS
from app import create_app
import os
import time
from werkzeug.middleware.profiler import ProfilerMiddleware

logging.debug("Starting application setup...")

try:
    app = create_app()
    logging.debug("Application created successfully.")
except Exception as e:
    logging.error(f"Error during app creation: {e}")
    raise

# Enable profiling
app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])

@app.route('/')
def index():
    logging.debug("Handling request to '/' route")
    return "Main Application"

if __name__ == '__main__':
    logging.debug("Starting Flask application...")
    try:
        print(app.url_map)  # Add this line to print the URL map
        app.run(debug=True)
    except Exception as e:
        logging.error(f"Error during app run: {e}")
        raise