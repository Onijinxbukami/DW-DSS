"""
app/db.py – Single unified database connection helper (PostgreSQL).
Used by: app routes, ETL scripts, mart/build_mart.py
"""
import os
import sys

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
    """Open a PostgreSQL connection and return a PgConn wrapper."""
    raw = psycopg2.connect(DATABASE_URL)
    return PgConn(raw)


# Alias for ETL consumers
get_db_conn = get_db
