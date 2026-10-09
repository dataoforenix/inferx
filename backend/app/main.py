"""ASGI entry point. Run from backend/:  uvicorn app.main:app --reload

Importing this module loads data/categories.csv. Tests and tools import app.factory instead.
"""

from app.factory import create_app

app = create_app()
