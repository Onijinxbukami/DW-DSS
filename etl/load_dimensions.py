"""
ETL Phase 1: Load all 5 dimension tables into the Star Schema.
Run order: branch → customer → product → collector → date
"""
import os
import sys

import pandas as pd
from datetime import date, timedelta
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR
from etl.utils import RAW_TO_CLEAN, clean_branch

# ---------------------------------------------------------------------------
# DDL – individual statements (no executescript in psycopg2)
# ---------------------------------------------------------------------------
DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS dim_branch (
        branch_sk         SERIAL PRIMARY KEY,
        branch_code_clean TEXT UNIQUE NOT NULL,
        branch_name       TEXT,
        city              TEXT,
        region            TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_customer (
        customer_sk         SERIAL PRIMARY KEY,
        national_id         TEXT UNIQUE NOT NULL,
        full_name           TEXT,
        phone               TEXT,
        email               TEXT,
        address             TEXT,
        has_mortgage        INTEGER DEFAULT 0,
        has_credit_card     INTEGER DEFAULT 0,
        source_cif          TEXT,
        source_cc_user_id   INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_product (
        product_sk     SERIAL PRIMARY KEY,
        product_source TEXT NOT NULL,
        product_code   TEXT NOT NULL,
        product_name   TEXT,
        card_type      TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_collector (
        collector_sk     SERIAL PRIMARY KEY,
        collector_code   TEXT UNIQUE NOT NULL,
        collector_name   TEXT,
        team             TEXT,
        branch_sk        INTEGER REFERENCES dim_branch(branch_sk),
        max_daily_cases  INTEGER,
        email            TEXT,
        phone            TEXT,
        is_active        INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dim_date (
        date_sk        INTEGER PRIMARY KEY,
        full_date      TEXT NOT NULL,
        day_of_week    INTEGER,
        day_name       TEXT,
        month          INTEGER,
        quarter        INTEGER,
        year           INTEGER,
        is_weekend     INTEGER,
        is_working_day INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scoring_config (
        config_id                       SERIAL PRIMARY KEY,
        effective_date                  TIMESTAMP NOT NULL,
        alpha_num_overdue_6m            DOUBLE PRECISION,
        beta_max_dpd_6m                 DOUBLE PRECISION,
        gamma_dpd_current               DOUBLE PRECISION,
        delta_amount_band               DOUBLE PRECISION,
        epsilon_product_source_mortgage DOUBLE PRECISION,
        applied_by                      TEXT DEFAULT 'system',
        description                     TEXT
    )
    """,
]


def create_tables(conn):
    for stmt in DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()


# ---------------------------------------------------------------------------
# dim_branch
# ---------------------------------------------------------------------------
def load_dim_branch(conn):
    df = pd.read_csv(os.path.join(DATA_DIR, "branch_master.csv"))
    rows = [
        (row["branch_code_clean"], row["branch_name"], row["city"], row["region"])
        for _, row in df.iterrows()
    ]
    psycopg2.extras.execute_values(
        conn.raw.cursor(),
        """INSERT INTO dim_branch (branch_code_clean, branch_name, city, region)
           VALUES %s
           ON CONFLICT (branch_code_clean) DO NOTHING""",
        rows
    )
    conn.commit()
    print(f"  dim_branch: {len(rows)} rows")


# ---------------------------------------------------------------------------
# dim_customer
# ---------------------------------------------------------------------------
def load_dim_customer(conn):
    cb = pd.read_csv(os.path.join(DATA_DIR, "cb_customer.csv"), dtype={"national_id": str})
    cc = pd.read_csv(os.path.join(DATA_DIR, "cc_user.csv"), dtype={"national_id": str})

    cb["national_id"] = cb["national_id"].str.strip()
    cc["national_id"] = cc["national_id"].str.strip()

    cb_dict = {row["national_id"]: row for _, row in cb.iterrows()}
    cc_dict = {row["national_id"]: row for _, row in cc.iterrows()}

    all_ids = set(cb_dict.keys()) | set(cc_dict.keys())
    rows = []
    for nid in all_ids:
        cb_row = cb_dict.get(nid)
        cc_row = cc_dict.get(nid)

        has_mortgage    = 1 if cb_row is not None else 0
        has_credit_card = 1 if cc_row is not None else 0

        full_name = (cb_row["full_name"] if cb_row is not None else cc_row["full_name"])
        phone     = (cb_row["phone"]     if cb_row is not None else
                     cc_row["mobile_number"] if cc_row is not None else None)
        email     = (cb_row["email"]     if cb_row is not None else
                     cc_row["email_address"] if cc_row is not None else None)
        address   = (cb_row["address"]   if cb_row is not None else
                     cc_row["address"]   if cc_row is not None else None)
        source_cif        = cb_row["cif"]         if cb_row is not None else None
        source_cc_user_id = int(cc_row["cc_user_id"]) if cc_row is not None else None

        rows.append((
            nid, str(full_name), str(phone) if phone else None,
            str(email) if email else None, str(address) if address else None,
            has_mortgage, has_credit_card,
            str(source_cif) if source_cif else None, source_cc_user_id
        ))

    psycopg2.extras.execute_values(
        conn.raw.cursor(),
        """INSERT INTO dim_customer
           (national_id, full_name, phone, email, address,
            has_mortgage, has_credit_card, source_cif, source_cc_user_id)
           VALUES %s
           ON CONFLICT (national_id) DO NOTHING""",
        rows
    )
    conn.commit()
    print(f"  dim_customer: {len(rows)} rows")


# ---------------------------------------------------------------------------
# dim_product
# ---------------------------------------------------------------------------
CB_PRODUCT_NAMES = {
    "HOME":     "Vay thế chấp nhà",
    "CAR":      "Vay thế chấp ô tô",
    "BUSINESS": "Vay kinh doanh",
}


def load_dim_product(conn):
    rows = []
    for code, name in CB_PRODUCT_NAMES.items():
        rows.append(("COREBANK", code, name, None))

    cc_acc = pd.read_csv(os.path.join(DATA_DIR, "cc_card_account.csv"))
    combos = cc_acc[["card_type", "product_type"]].drop_duplicates()
    for _, r in combos.iterrows():
        ct, pt = r["card_type"], r["product_type"]
        code = f"{ct}:{pt}"
        name = f"{ct} {pt}"
        rows.append(("CORECARD", code, name, ct))

    psycopg2.extras.execute_values(
        conn.raw.cursor(),
        """INSERT INTO dim_product (product_source, product_code, product_name, card_type)
           VALUES %s
           ON CONFLICT DO NOTHING""",
        rows
    )
    conn.commit()
    print(f"  dim_product: {len(rows)} rows")


# ---------------------------------------------------------------------------
# dim_collector
# ---------------------------------------------------------------------------
def load_dim_collector(conn):
    df = pd.read_csv(os.path.join(DATA_DIR, "collector_staff.csv"))

    cursor = conn.execute("SELECT branch_sk, branch_code_clean FROM dim_branch")
    branch_map = {row["branch_code_clean"]: row["branch_sk"] for row in cursor.fetchall()}

    rows = []
    for _, r in df.iterrows():
        clean = clean_branch(str(r["branch_code_raw"]))
        branch_sk = branch_map.get(clean, 1)
        rows.append((
            str(r["collector_code"]), str(r["collector_name"]),
            str(r["team"]), branch_sk, int(r["max_daily_cases"]),
            str(r["email"]), str(r["phone"]), int(r["is_active"])
        ))

    psycopg2.extras.execute_values(
        conn.raw.cursor(),
        """INSERT INTO dim_collector
           (collector_code, collector_name, team, branch_sk,
            max_daily_cases, email, phone, is_active)
           VALUES %s
           ON CONFLICT (collector_code) DO NOTHING""",
        rows
    )
    conn.commit()
    print(f"  dim_collector: {len(rows)} rows")


# ---------------------------------------------------------------------------
# dim_date
# ---------------------------------------------------------------------------
def load_dim_date(conn):
    start = date(2020, 1, 1)
    end   = date(2034, 12, 31)
    rows  = []
    current = start
    while current <= end:
        dow = current.isoweekday()  # 1=Mon, 7=Sun
        is_weekend = 1 if dow >= 6 else 0
        rows.append((
            int(current.strftime("%Y%m%d")),
            current.isoformat(),
            dow,
            current.strftime("%A"),
            current.month,
            (current.month - 1) // 3 + 1,
            current.year,
            is_weekend,
            1 - is_weekend
        ))
        current += timedelta(days=1)

    psycopg2.extras.execute_values(
        conn.raw.cursor(),
        """INSERT INTO dim_date
           (date_sk, full_date, day_of_week, day_name,
            month, quarter, year, is_weekend, is_working_day)
           VALUES %s
           ON CONFLICT (date_sk) DO NOTHING""",
        rows,
        page_size=2000
    )
    conn.commit()
    print(f"  dim_date: {len(rows)} rows")


# ---------------------------------------------------------------------------
# scoring_config seed
# ---------------------------------------------------------------------------
def seed_scoring_config(conn):
    df = pd.read_csv(os.path.join(DATA_DIR, "scoring_config_initial.csv"))
    existing = conn.execute("SELECT COUNT(*) AS n FROM scoring_config").fetchone()["n"]
    if existing > 0:
        print("  scoring_config: already seeded, skipping")
        return
    for _, r in df.iterrows():
        conn.execute(
            """INSERT INTO scoring_config
               (effective_date, alpha_num_overdue_6m, beta_max_dpd_6m,
                gamma_dpd_current, delta_amount_band,
                epsilon_product_source_mortgage, applied_by, description)
               VALUES (%s,%s,%s,%s,%s,%s,'system',%s)""",
            (str(r["effective_date"]),
             float(r["alpha_num_overdue_6m"]),
             float(r["beta_max_dpd_6m"]),
             float(r["gamma_dpd_current"]),
             float(r["delta_amount_band"]),
             float(r["epsilon_product_source_mortgage"]),
             str(r["description"]))
        )
    conn.commit()
    print("  scoring_config: seeded 1 row")


if __name__ == "__main__":
    from app.db import get_db_conn
    conn = get_db_conn()
    create_tables(conn)
    load_dim_branch(conn)
    load_dim_customer(conn)
    load_dim_product(conn)
    load_dim_collector(conn)
    load_dim_date(conn)
    seed_scoring_config(conn)
    conn.close()
    print("Dimensions loaded successfully.")
