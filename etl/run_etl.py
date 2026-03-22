"""
ETL Orchestrator – run this once to build the full Star Schema.
Usage:  python etl/run_etl.py   (from project root)
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL
from app.db import get_db_conn
from etl.load_dimensions import (
    create_tables,
    load_dim_branch, load_dim_customer, load_dim_product,
    load_dim_collector, load_dim_date, seed_scoring_config
)
from etl.load_fact import FACT_DDL_STATEMENTS, load_fact_corebank, load_fact_corecard

MART_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS dm_daily_collection_tasks (
        task_id            SERIAL PRIMARY KEY,
        snapshot_date      TEXT NOT NULL,
        customer_sk        INTEGER,
        customer_name      TEXT,
        national_id        TEXT,
        phone              TEXT,
        email              TEXT,
        contract_no        TEXT,
        product_source     TEXT,
        product_code       TEXT,
        branch_sk          INTEGER,
        branch_name        TEXT,
        total_outstanding  BIGINT,
        amount_due_current BIGINT,
        dpd_current        INTEGER,
        dpd_bucket         TEXT,
        assigned_channel   TEXT,
        num_overdue_6m     INTEGER DEFAULT 0,
        max_dpd_6m         INTEGER DEFAULT 0,
        risk_score         DOUBLE PRECISION DEFAULT 0,
        priority_rank      INTEGER DEFAULT 0,
        collector_sk       INTEGER,
        collector_name     TEXT,
        task_status        TEXT DEFAULT 'PENDING',
        config_id          INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_mart_snapshot  ON dm_daily_collection_tasks(snapshot_date)",
    "CREATE INDEX IF NOT EXISTS idx_mart_collector ON dm_daily_collection_tasks(collector_sk, snapshot_date)",
    "CREATE INDEX IF NOT EXISTS idx_mart_priority  ON dm_daily_collection_tasks(snapshot_date, priority_rank)",
]

DROP_ORDER = [
    "DROP TABLE IF EXISTS dm_daily_collection_tasks",
    "DROP TABLE IF EXISTS fact_debt_installment",
    "DROP TABLE IF EXISTS dim_date",
    "DROP TABLE IF EXISTS dim_collector",
    "DROP TABLE IF EXISTS dim_product",
    "DROP TABLE IF EXISTS dim_customer",
    "DROP TABLE IF EXISTS dim_branch",
    "DROP TABLE IF EXISTS scoring_config",
]


def drop_and_recreate(conn):
    print("Dropping existing tables...")
    for stmt in DROP_ORDER:
        conn.execute(stmt)
    conn.commit()


def main():
    t0 = time.time()
    print(f"ETL started – DB: {DATABASE_URL[:DATABASE_URL.index('@')+1]}***")

    conn = get_db_conn()

    drop_and_recreate(conn)

    print("\n[1/3] Creating tables...")
    create_tables(conn)
    for stmt in FACT_DDL_STATEMENTS:
        conn.execute(stmt)
    for stmt in MART_DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()

    print("\n[2/3] Loading dimensions...")
    load_dim_branch(conn)
    load_dim_customer(conn)
    load_dim_product(conn)
    load_dim_collector(conn)
    load_dim_date(conn)
    seed_scoring_config(conn)

    print("\n[3/3] Loading fact table...")
    load_fact_corebank(conn)
    load_fact_corecard(conn)

    print("\n--- Row counts ---")
    for tbl in ["dim_customer", "dim_product", "dim_branch",
                "dim_collector", "dim_date", "fact_debt_installment",
                "scoring_config"]:
        n = conn.execute(f"SELECT COUNT(*) AS n FROM {tbl}").fetchone()["n"]
        print(f"  {tbl}: {n:,}")

    conn.close()
    print(f"\nETL completed in {time.time()-t0:.1f}s")
    print("Run 'python mart/build_mart.py' next to populate the data mart.")


if __name__ == "__main__":
    main()
