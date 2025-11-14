#!/usr/bin/env python
"""Startup script for the FastAPI server"""
import sys
from pathlib import Path
import uvicorn

# Add current directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    try:
        print("Starting Herbal Identification API server...")
        print("Server will be available at http://127.0.0.1:8000")
        print("API docs will be available at http://127.0.0.1:8000/docs")
        uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

