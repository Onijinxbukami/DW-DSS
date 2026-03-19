"""
config.py – Centralized configuration for the DW & DSS project.
All paths, constants, and environment-sensitive values live here.
"""
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()  # loads .env file if present

# ---------------------------------------------------------------------------
# Directory layout
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(PROJECT_ROOT, "data", "raw")   # all 12 CSV files

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASE_URL = os.environ["DATABASE_URL"]  # e.g. postgresql://user:pass@host/dbname

# ---------------------------------------------------------------------------
# Business constants
# ---------------------------------------------------------------------------
SNAPSHOT_DATE     = date(2024, 12, 31)          # date object (used in ETL)
SNAPSHOT_DATE_STR = SNAPSHOT_DATE.isoformat()   # "2024-12-31" (used in SQL)

# ---------------------------------------------------------------------------
# Flask settings
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get("SECRET_KEY", "banka-dss-2024-secret")
