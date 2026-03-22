"""
ETL Phase 2: Build fact_debt_installment from CoreBank and CoreCard sources.
Must run AFTER load_dimensions.py.
"""
import os
import sys

import numpy as np
import pandas as pd
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, SNAPSHOT_DATE
from app.db import get_db_conn
from etl.utils import parse_dirty_date, date_to_sk, clean_branch

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------
FACT_DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS fact_debt_installment (
        fact_id           SERIAL PRIMARY KEY,
        customer_sk       INTEGER NOT NULL,
        product_sk        INTEGER NOT NULL,
        branch_sk         INTEGER NOT NULL,
        due_date_sk       INTEGER NOT NULL,
        payment_date_sk   INTEGER,
        contract_no       TEXT NOT NULL,
        installment_no    INTEGER NOT NULL,
        amount_due        BIGINT NOT NULL DEFAULT 0,
        amount_paid       BIGINT NOT NULL DEFAULT 0,
        amount_remaining  BIGINT NOT NULL DEFAULT 0,
        dpd               INTEGER NOT NULL DEFAULT 0,
        status            TEXT NOT NULL,
        total_outstanding BIGINT NOT NULL DEFAULT 0,
        product_source    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_debt_installment(customer_sk)",
    "CREATE INDEX IF NOT EXISTS idx_fact_contract  ON fact_debt_installment(contract_no)",
    "CREATE INDEX IF NOT EXISTS idx_fact_due_date  ON fact_debt_installment(due_date_sk)",
    "CREATE INDEX IF NOT EXISTS idx_fact_dpd       ON fact_debt_installment(dpd)",
]

SNAPSHOT_DATE_PD = pd.Timestamp(SNAPSHOT_DATE)


def _build_lookups(conn):
    rows = conn.execute("SELECT national_id, customer_sk FROM dim_customer").fetchall()
    cust_map = {r["national_id"]: r["customer_sk"] for r in rows}

    rows = conn.execute("SELECT product_source, product_code, product_sk FROM dim_product").fetchall()
    prod_map = {(r["product_source"], r["product_code"]): r["product_sk"] for r in rows}

    rows = conn.execute("SELECT branch_code_clean, branch_sk FROM dim_branch").fetchall()
    branch_map = {r["branch_code_clean"]: r["branch_sk"] for r in rows}

    rows = conn.execute("SELECT date_sk FROM dim_date").fetchall()
    date_set = {r["date_sk"] for r in rows}

    return cust_map, prod_map, branch_map, date_set


def _bulk_insert(conn, df: pd.DataFrame, source: str):
    """Convert DataFrame to list of tuples and bulk-insert in one round-trip."""
    cols = [
        "customer_sk", "product_sk", "branch_sk", "due_date_sk", "payment_date_sk",
        "contract_no", "installment_no", "amount_due", "amount_paid",
        "amount_remaining", "dpd", "status", "total_outstanding",
    ]
    records = []
    for row in df[cols].itertuples(index=False):
        records.append((
            int(row.customer_sk), int(row.product_sk), int(row.branch_sk),
            int(row.due_date_sk),
            int(row.payment_date_sk) if pd.notna(row.payment_date_sk) else None,
            row.contract_no, int(row.installment_no),
            int(row.amount_due), int(row.amount_paid), int(row.amount_remaining),
            int(row.dpd), row.status, int(row.total_outstanding), source,
        ))
    psycopg2.extras.execute_values(
        conn.raw.cursor(),
        """INSERT INTO fact_debt_installment
           (customer_sk, product_sk, branch_sk, due_date_sk, payment_date_sk,
            contract_no, installment_no, amount_due, amount_paid,
            amount_remaining, dpd, status, total_outstanding, product_source)
           VALUES %s""",
        records,
        page_size=5000,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# CoreBank — fully vectorized
# ---------------------------------------------------------------------------
def load_fact_corebank(conn):
    print("  Loading CoreBank fact rows...")
    cust_map, prod_map, branch_map, date_set = _build_lookups(conn)

    cb_cust = pd.read_csv(os.path.join(DATA_DIR, "cb_customer.csv"),
                          dtype={"national_id": str, "customer_id": int})
    cb_cust["national_id"] = cb_cust["national_id"].str.strip()

    cb_loan  = pd.read_csv(os.path.join(DATA_DIR, "cb_mortgage_loan.csv"))
    cb_sched = pd.read_csv(os.path.join(DATA_DIR, "cb_loan_schedule.csv"))
    cb_pay   = pd.read_csv(os.path.join(DATA_DIR, "cb_payment_transaction.csv"))

    # --- parse dates vectorized ---
    cb_sched["due_date"]    = pd.to_datetime(cb_sched["installment_due_date_raw"].map(parse_dirty_date), errors="coerce")
    cb_pay["payment_date"]  = pd.to_datetime(cb_pay["payment_date_raw"].map(parse_dirty_date), errors="coerce")

    pay_agg = cb_pay.groupby(["mortgage_loan_id", "installment_no"]).agg(
        payment_amount=("payment_amount", "sum"),
        payment_date=("payment_date", "max")
    ).reset_index()

    # --- merge all together ---
    df = cb_sched.merge(pay_agg, on=["mortgage_loan_id", "installment_no"], how="left")
    df = df.merge(cb_loan[["mortgage_loan_id", "customer_id", "product_code",
                            "branch_code_raw", "total_outstanding", "contract_no"]],
                  on="mortgage_loan_id", how="left")
    df = df.merge(cb_cust[["customer_id", "national_id"]], on="customer_id", how="left")

    # --- SK lookups via map ---
    df["customer_sk"] = df["national_id"].map(cust_map)
    df["product_key"] = list(zip(["COREBANK"] * len(df), df["product_code"]))
    df["product_sk"]  = df["product_key"].map(prod_map)
    df["branch_clean"]= df["branch_code_raw"].map(lambda x: clean_branch(str(x)) if pd.notna(x) else "BR-HCM01")
    df["branch_sk"]   = df["branch_clean"].map(branch_map).fillna(1).astype(int)
    df["due_date_sk"] = df["due_date"].map(lambda d: date_to_sk(d.date()) if pd.notna(d) else None)

    # --- filter invalid rows ---
    df = df.dropna(subset=["customer_sk", "product_sk", "due_date_sk"])
    df = df[df["due_date_sk"].isin(date_set)]

    # --- amounts ---
    df["amount_due"]  = df["installment_amount"].fillna(0).astype(int)
    df["amount_paid"] = df["payment_amount"].fillna(0).astype(int)
    df["amount_remaining"] = (df["amount_due"] - df["amount_paid"]).clip(lower=0)

    # --- payment date sk ---
    df["payment_date_sk"] = df["payment_date"].map(
        lambda d: date_to_sk(d.date()) if pd.notna(d) else None
    )

    # --- DPD & status ---
    has_payment = df["payment_date"].notna()
    df["dpd"] = 0
    df.loc[has_payment, "dpd"] = (
        (df.loc[has_payment, "payment_date"] - df.loc[has_payment, "due_date"])
        .dt.days.clip(lower=0)
    )
    overdue_mask = ~has_payment & (df["due_date"] < SNAPSHOT_DATE_PD)
    df.loc[overdue_mask, "dpd"] = (
        (SNAPSHOT_DATE_PD - df.loc[overdue_mask, "due_date"]).dt.days
    )

    df["status"] = "PENDING"
    df.loc[has_payment & (df["amount_paid"] >= df["amount_due"]), "status"] = "PAID"
    df.loc[has_payment & (df["amount_paid"] < df["amount_due"]),  "status"] = "PARTIAL"
    df.loc[overdue_mask, "status"] = "OVERDUE"

    df["total_outstanding"] = df["total_outstanding"].fillna(0).astype(int)

    _bulk_insert(conn, df, "COREBANK")
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM fact_debt_installment WHERE product_source='COREBANK'"
    ).fetchone()["n"]
    print(f"  CoreBank fact rows: {total:,}")


# ---------------------------------------------------------------------------
# CoreCard — fully vectorized
# ---------------------------------------------------------------------------
def load_fact_corecard(conn):
    print("  Loading CoreCard fact rows...")
    cust_map, prod_map, branch_map, date_set = _build_lookups(conn)

    cc_user = pd.read_csv(os.path.join(DATA_DIR, "cc_user.csv"),
                          dtype={"national_id": str, "cc_user_id": int})
    cc_user["national_id"] = cc_user["national_id"].str.strip()

    cc_acc  = pd.read_csv(os.path.join(DATA_DIR, "cc_card_account.csv"))
    cc_stmt = pd.read_csv(os.path.join(DATA_DIR, "cc_card_statement.csv"))
    cc_pay  = pd.read_csv(os.path.join(DATA_DIR, "cc_card_payment.csv"))

    # --- parse dates vectorized ---
    cc_pay["payment_date"]  = pd.to_datetime(cc_pay["payment_date_raw"].map(parse_dirty_date), errors="coerce")
    cc_stmt["due_date"]     = pd.to_datetime(cc_stmt["payment_due_date_raw"].map(parse_dirty_date), errors="coerce")
    cc_stmt["statement_date"] = pd.to_datetime(cc_stmt["statement_date_raw"].map(parse_dirty_date), errors="coerce")

    pay_agg = cc_pay.groupby("statement_id").agg(
        payment_amount=("payment_amount", "sum"),
        payment_date=("payment_date", "max")
    ).reset_index()

    cc_stmt = cc_stmt.sort_values(["card_account_id", "statement_date"])
    cc_stmt["installment_no"] = cc_stmt.groupby("card_account_id").cumcount() + 1

    # --- merge all ---
    df = cc_stmt.merge(pay_agg, on="statement_id", how="left")
    df = df.merge(cc_acc[["card_account_id", "cc_user_id", "account_no",
                           "card_type", "product_type", "issuing_branch_code_raw", "current_balance"]],
                  on="card_account_id", how="left")
    df = df.merge(cc_user[["cc_user_id", "national_id"]], on="cc_user_id", how="left")

    # --- SK lookups ---
    df["customer_sk"]   = df["national_id"].map(cust_map)
    df["product_code"]  = df["card_type"] + ":" + df["product_type"]
    df["product_key"]   = list(zip(["CORECARD"] * len(df), df["product_code"]))
    df["product_sk"]    = df["product_key"].map(prod_map)
    df["branch_clean"]  = df["issuing_branch_code_raw"].map(lambda x: clean_branch(str(x)) if pd.notna(x) else "BR-HCM01")
    df["branch_sk"]     = df["branch_clean"].map(branch_map).fillna(1).astype(int)
    df["due_date_sk"]   = df["due_date"].map(lambda d: date_to_sk(d.date()) if pd.notna(d) else None)

    # --- filter ---
    df = df.dropna(subset=["customer_sk", "product_sk", "due_date_sk"])
    df = df[df["due_date_sk"].isin(date_set)]

    # --- amounts ---
    df["amount_due"]  = df["minimum_amount_due"].fillna(0).astype(int)
    df["amount_paid"] = df["payment_amount"].fillna(0).astype(int)
    df["amount_remaining"] = (df["amount_due"] - df["amount_paid"]).clip(lower=0)
    df["contract_no"] = df["account_no"]
    df["total_outstanding"] = df["current_balance"].fillna(0).astype(int)

    # --- payment date sk ---
    df["payment_date_sk"] = df["payment_date"].map(
        lambda d: date_to_sk(d.date()) if pd.notna(d) else None
    )

    # --- DPD & status ---
    has_payment = df["payment_date"].notna()
    df["dpd"] = 0
    df.loc[has_payment, "dpd"] = (
        (df.loc[has_payment, "payment_date"] - df.loc[has_payment, "due_date"])
        .dt.days.clip(lower=0)
    )
    overdue_mask = ~has_payment & (df["due_date"] < SNAPSHOT_DATE_PD)
    df.loc[overdue_mask, "dpd"] = (
        (SNAPSHOT_DATE_PD - df.loc[overdue_mask, "due_date"]).dt.days
    )

    df["status"] = "PENDING"
    df.loc[has_payment & (df["amount_paid"] >= df["amount_due"]), "status"] = "PAID"
    df.loc[has_payment & (df["amount_paid"] < df["amount_due"]),  "status"] = "PARTIAL"
    df.loc[overdue_mask, "status"] = "OVERDUE"

    _bulk_insert(conn, df, "CORECARD")
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM fact_debt_installment WHERE product_source='CORECARD'"
    ).fetchone()["n"]
    print(f"  CoreCard fact rows: {total:,}")


if __name__ == "__main__":
    conn = get_db_conn()
    for stmt in FACT_DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    load_fact_corebank(conn)
    load_fact_corecard(conn)
    conn.close()
    print("Fact table loaded.")
