import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'napakaangas')
    
    # PostgreSQL with PostGIS (fallback to local database.db if testing with SQLite)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        'postgresql://postgres:admin@localhost:5432/punoobservation'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False