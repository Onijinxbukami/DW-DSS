"""
app/db.py – Single unified database connection helper (PostgreSQL).
Used by: app routes, ETL scripts, mart/build_mart.py
"""
import os
import sys
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_URL


class PgConn:
    """
    Thin wrapper around a psycopg2 connection that mimics the sqlite3
    connection API used throughout this project (.execute, .executemany,
    .commit, .close).  All .execute() calls use RealDictCursor so rows
    support both dict-style (row["col"]) and standard attribute access.
    Expose the raw psycopg2 connection via .raw for pandas read_sql_query.
    """

    def __init__(self, raw_conn):
        self.raw = raw_conn  # raw psycopg2 connection (for pandas)

    def execute(self, sql, params=None):
        cur = self.raw.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, seq_of_params):
        cur = self.raw.cursor()
        cur.executemany(sql, seq_of_params)
        return cur

    def execute_values(self, sql, seq_of_params, page_size=1000):
        """Bulk insert using psycopg2.extras.execute_values (much faster than executemany)."""
        cur = self.raw.cursor()
        psycopg2.extras.execute_values(cur, sql, seq_of_params, page_size=page_size)
        return cur

    def commit(self):
        self.raw.commit()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.raw.rollback()
        else:
            self.raw.commit()
        self.raw.close()


def get_db() -> PgConn:
    """
    Open a PostgreSQL connection and return a PgConn wrapper.

    If DB_PASSWORD is set in the environment, it is injected after parsing
    DATABASE_URL so that passwords containing special characters (@, |, #, etc.)
    do not need to be URL-encoded.
    """
    db_password = os.environ.get("DB_PASSWORD")
    keepalive_kwargs = {
        "keepalives": 1,
        "keepalives_idle": 10,
        "keepalives_interval": 5,
        "keepalives_count": 3,
        "connect_timeout": 10,
    }
    if db_password:
        p = urlparse(DATABASE_URL)
        raw = psycopg2.connect(
            host=p.hostname,
            port=p.port or 5432,
            dbname=p.path.lstrip("/"),
            user=p.username,
            password=db_password,
            sslmode="require",
            **keepalive_kwargs,
        )
    else:
        raw = psycopg2.connect(DATABASE_URL, sslmode="require", **keepalive_kwargs)
    return PgConn(raw)


# Alias for ETL consumers
get_db_conn = get_db
