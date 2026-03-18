"""
api/index.py – Vercel WSGI entry point.
Vercel routes all HTTP requests here via vercel.json.
"""
import sys
import os

# Ensure project root is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app()
