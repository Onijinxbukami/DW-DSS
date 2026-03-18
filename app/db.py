"""
app/db.py – Single unified database connection helper.
Used by: app routes, mart/build_mart.py

On Vercel (read-only filesystem), deploy.db is copied to /tmp on first access.
"""
import sqlite3
import shutil
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, PROJECT_ROOT

_DEPLOY_DB  = os.path.join(PROJECT_ROOT, "data", "deploy.db")
_TMP_DB     = "/tmp/database.db"


def _resolve_db_path() -> str:
    """
    On Vercel the filesystem is read-only except /tmp.
    Copy deploy.db to /tmp on the first cold-start, then reuse it.
    Locally, use the full database.db as normal.
    """
    if os.environ.get("VERCEL"):
        if not os.path.exists(_TMP_DB):
            shutil.copy2(_DEPLOY_DB, _TMP_DB)
        return _TMP_DB
    return DB_PATH


def get_db() -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and row factory."""
    conn = sqlite3.connect(_resolve_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# Alias for ETL consumers
get_db_conn = get_db
