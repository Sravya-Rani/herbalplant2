#!/usr/bin/env python
"""Check setup and identify any errors"""
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

print("=" * 50)
print("Checking Herbal Plant Identification System Setup")
print("=" * 50)

errors = []
warnings = []

# Check Python version
print("\n1. Checking Python version...")
print(f"   Python {sys.version}")

# Check imports
print("\n2. Checking imports...")
try:
    from app import app
    print("   ✓ app.py")
except Exception as e:
    errors.append(f"app.py import failed: {e}")
    print(f"   ✗ app.py: {e}")

try:
    from database.models import Herb, get_db, init_db
    print("   ✓ database.models")
except Exception as e:
    errors.append(f"database.models import failed: {e}")
    print(f"   ✗ database.models: {e}")

try:
    from services.herb_service import identify_herb
    print("   ✓ services.herb_service")
except Exception as e:
    errors.append(f"services.herb_service import failed: {e}")
    print(f"   ✗ services.herb_service: {e}")

try:
    from routers.user import router
    print("   ✓ routers.user")
except Exception as e:
    errors.append(f"routers.user import failed: {e}")
    print(f"   ✗ routers.user: {e}")

try:
    from schemas.herb_schema import HerbResponse
    print("   ✓ schemas.herb_schema")
except Exception as e:
    errors.append(f"schemas.herb_schema import failed: {e}")
    print(f"   ✗ schemas.herb_schema: {e}")

# Check database
print("\n3. Checking database...")
try:
    from database.models import engine, init_db
    from sqlalchemy import inspect
    
    # Check if database file exists
    db_path = Path(__file__).parent / "database" / "herbs.db"
    if db_path.exists():
        print(f"   ✓ Database file exists: {db_path}")
    else:
        warnings.append("Database file does not exist. Run init_database.py to create it.")
        print(f"   ⚠ Database file not found: {db_path}")
    
    # Try to connect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "herbs" in tables:
        print("   ✓ 'herbs' table exists")
    else:
        warnings.append("'herbs' table does not exist. Run init_database.py to create it.")
        print("   ⚠ 'herbs' table not found")
        
except Exception as e:
    errors.append(f"Database check failed: {e}")
    print(f"   ✗ Database check failed: {e}")

# Check environment variables
print("\n4. Checking environment variables...")
import os

try:
    from dotenv import load_dotenv
    load_dotenv_available = True
except ImportError:
    load_dotenv_available = False
    warnings.append("python-dotenv not installed. Environment variables must be set manually.")

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    if load_dotenv_available:
        load_dotenv(env_path)
    print("   ✓ .env file found")
else:
    warnings.append(".env file not found. API keys may need to be set as environment variables.")
    print("   ⚠ .env file not found")

plant_id_key = os.getenv("PLANT_ID_API_KEY")
plantnet_key = os.getenv("PLANTNET_API_KEY")
plant_provider = os.getenv("PLANT_PROVIDER", "plantid").lower()

if plant_provider == "plantid":
    if plant_id_key:
        print("   ✓ PLANT_ID_API_KEY is set")
    else:
        warnings.append("PLANT_ID_API_KEY is not set. Plant identification may not work.")
        print("   ⚠ PLANT_ID_API_KEY is not set")
elif plant_provider == "plantnet":
    if plantnet_key:
        print("   ✓ PLANTNET_API_KEY is set")
    else:
        warnings.append("PLANTNET_API_KEY is not set. Plant identification may not work.")
        print("   ⚠ PLANTNET_API_KEY is not set")

# Check uploads directory
print("\n5. Checking uploads directory...")
uploads_dir = Path(__file__).parent / "uploads"
if uploads_dir.exists():
    print(f"   ✓ Uploads directory exists: {uploads_dir}")
else:
    print(f"   ⚠ Uploads directory not found (will be created automatically)")

# Summary
print("\n" + "=" * 50)
print("SUMMARY")
print("=" * 50)

if errors:
    print(f"\n❌ Found {len(errors)} error(s):")
    for i, error in enumerate(errors, 1):
        print(f"   {i}. {error}")
    print("\n⚠️  Please fix these errors before running the server.")
    sys.exit(1)
else:
    print("\n✅ No critical errors found!")

if warnings:
    print(f"\n⚠️  Found {len(warnings)} warning(s):")
    for i, warning in enumerate(warnings, 1):
        print(f"   {i}. {warning}")
    print("\n💡 These warnings may affect functionality but won't prevent the server from starting.")

print("\n" + "=" * 50)
print("Setup check complete!")
print("=" * 50)

