from app import create_app
from app.database import create_tables

app = create_app()

# Create tables before loading data
with app.app_context():
    create_tables(app)
    print("Tables created successfully.")