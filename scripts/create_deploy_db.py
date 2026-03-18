"""
scripts/create_deploy_db.py
Creates data/deploy.db – a slim database for Vercel deployment.

Contents:
  - dim_branch, dim_collector, dim_customer, dim_product, dim_date  (all rows)
  - scoring_config                                                   (all rows)
  - dm_daily_collection_tasks                                       (all rows)
  - fact_history_6m   – top 6 installments per (customer_sk, contract_no)
                         from 2024-06-30 onward (for task_detail popup)

Usage:
    python scripts/create_deploy_db.py
"""
import os
import sys
import sqlite3
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, PROJECT_ROOT

DEPLOY_DB = os.path.join(PROJECT_ROOT, "data", "deploy.db")


DIM_TABLES = [
    "dim_branch",
    "dim_collector",
    "dim_customer",
    "dim_product",
    "dim_date",
]

FACT_HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS fact_history_6m (
    customer_sk  INTEGER NOT NULL,
    contract_no  TEXT    NOT NULL,
    due_date     TEXT,
    amount_due   INTEGER,
    amount_paid  INTEGER,
    dpd          INTEGER,
    status       TEXT
);
CREATE INDEX IF NOT EXISTS idx_fh_cust ON fact_history_6m(customer_sk, contract_no);
"""

SCORING_CONFIG_DDL = """
CREATE TABLE IF NOT EXISTS scoring_config (
    config_id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_date                   TEXT,
    alpha_num_overdue_6m             REAL,
    beta_max_dpd_6m                  REAL,
    gamma_dpd_current                REAL,
    delta_amount_band                REAL,
    epsilon_product_source_mortgage  REAL,
    applied_by                       TEXT,
    description                      TEXT
);
"""

MART_DDL = """
CREATE TABLE IF NOT EXISTS dm_daily_collection_tasks (
    task_id            INTEGER PRIMARY KEY AUTOINCREMENT,
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
    total_outstanding  INTEGER,
    amount_due_current INTEGER,
    dpd_current        INTEGER,
    dpd_bucket         TEXT,
    assigned_channel   TEXT,
    num_overdue_6m     INTEGER DEFAULT 0,
    max_dpd_6m         INTEGER DEFAULT 0,
    risk_score         REAL DEFAULT 0,
    priority_rank      INTEGER DEFAULT 0,
    collector_sk       INTEGER,
    collector_name     TEXT,
    task_status        TEXT DEFAULT 'PENDING',
    config_id          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_mart_snapshot  ON dm_daily_collection_tasks(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_mart_collector ON dm_daily_collection_tasks(collector_sk, snapshot_date);
CREATE INDEX IF NOT EXISTS idx_mart_priority  ON dm_daily_collection_tasks(snapshot_date, priority_rank);
"""


def copy_table(src: sqlite3.Connection, dst: sqlite3.Connection, table: str):
    """Copy all rows from src table to dst table (table must already exist in dst)."""
    # Get DDL from source
    ddl_row = src.execute(
        f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if ddl_row is None:
        raise RuntimeError(f"Table {table} not found in source DB")

    dst.executescript(ddl_row[0] + ";")

    # Copy indices
    for idx_row in src.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table,)
    ).fetchall():
        try:
            dst.executescript(idx_row[0] + ";")
        except Exception:
            pass  # index may already exist

    rows = src.execute(f"SELECT * FROM {table}").fetchall()
    if rows:
        n_cols = len(rows[0])
        placeholders = ",".join(["?"] * n_cols)
        dst.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
    print(f"  {table}: {len(rows):,} rows copied")


def build_fact_history(src: sqlite3.Connection, dst: sqlite3.Connection):
    """
    Pre-compute top-6 installments per (customer_sk, contract_no)
    from 2024-06-30 onward, only for customers in the mart.
    """
    print("  Building fact_history_6m...")
    df = pd.read_sql_query(
        """
        SELECT f.customer_sk, f.contract_no, d.full_date AS due_date,
               f.amount_due, f.amount_paid, f.dpd, f.status
        FROM fact_debt_installment f
        JOIN dim_date d ON f.due_date_sk = d.date_sk
        WHERE f.due_date_sk >= 20240630
          AND f.customer_sk IN (
              SELECT DISTINCT customer_sk FROM dm_daily_collection_tasks
          )
        ORDER BY f.customer_sk, f.contract_no, f.due_date_sk DESC
        """,
        src,
    )

    # Keep top 6 per (customer_sk, contract_no)
    df = (
        df.groupby(["customer_sk", "contract_no"], group_keys=False)
        .head(6)
        .reset_index(drop=True)
    )

    dst.executescript(FACT_HISTORY_DDL)
    rows = list(df.itertuples(index=False, name=None))
    if rows:
        dst.executemany(
            "INSERT INTO fact_history_6m VALUES (?,?,?,?,?,?,?)", rows
        )
    print(f"  fact_history_6m: {len(rows):,} rows inserted")


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found. Run 'python etl/run_etl.py' first.")
        sys.exit(1)

    if os.path.exists(DEPLOY_DB):
        os.remove(DEPLOY_DB)
        print(f"Removed existing {DEPLOY_DB}")

    src = sqlite3.connect(DB_PATH)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(DEPLOY_DB)

    print(f"\nCreating {DEPLOY_DB} ...")

    # 1. Dimension tables
    print("\n[1/4] Copying dimension tables...")
    for tbl in DIM_TABLES:
        copy_table(src, dst, tbl)

    # 2. scoring_config
    print("\n[2/4] Copying scoring_config...")
    dst.executescript(SCORING_CONFIG_DDL)
    rows = src.execute("SELECT * FROM scoring_config").fetchall()
    if rows:
        dst.executemany(
            "INSERT INTO scoring_config VALUES (?,?,?,?,?,?,?,?,?)", rows
        )
    print(f"  scoring_config: {len(rows)} rows copied")

    # 3. dm_daily_collection_tasks
    print("\n[3/4] Copying dm_daily_collection_tasks...")
    dst.executescript(MART_DDL)
    mart_rows = src.execute("SELECT * FROM dm_daily_collection_tasks").fetchall()
    if mart_rows:
        dst.executemany(
            f"INSERT INTO dm_daily_collection_tasks VALUES ({','.join(['?']*25)})",
            mart_rows,
        )
    print(f"  dm_daily_collection_tasks: {len(mart_rows):,} rows copied")

    # 4. fact_history_6m (pre-computed)
    print("\n[4/4] Building fact_history_6m (pre-computed 6m history)...")
    build_fact_history(src, dst)

    dst.commit()
    src.close()
    dst.close()

    size_mb = os.path.getsize(DEPLOY_DB) / 1024 / 1024
    print(f"\ndeploy.db created: {size_mb:.1f} MB")
    if size_mb > 100:
        print("WARNING: File is >100MB – GitHub will reject it. Consider Git LFS.")
    else:
        print("OK – fits within GitHub's 100MB file limit.")


if __name__ == "__main__":
    main()
