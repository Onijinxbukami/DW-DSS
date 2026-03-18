"""
api/index.py – Vercel WSGI entry point.
Vercel routes all HTTP requests here via vercel.json.
"""
import sys
import os

# Add project root to path so all imports (app, models, config) resolve correctly.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Ensure VERCEL flag is set so app/db.py copies deploy.db → /tmp
os.environ.setdefault("VERCEL", "1")

from app import create_app

app = create_app()
