"""
Script to initialize the database with sample herb data.
Run this script to populate the database with initial herb information.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.models import init_db
from services.db_service import init_sample_data

if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Database tables created.")
    
    print("Populating with sample data...")
    init_sample_data()
    print("Database initialized successfully!")

