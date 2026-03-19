"""
ETL Phase 2: Build fact_debt_installment from CoreBank and CoreCard sources.
Must run AFTER load_dimensions.py.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, SNAPSHOT_DATE
from app.db import get_db_conn
from etl.utils import parse_dirty_date, date_to_sk, clean_branch

# ---------------------------------------------------------------------------
# DDL – individual statements (no executescript in psycopg2)
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
        amount_due        INTEGER NOT NULL DEFAULT 0,
        amount_paid       INTEGER NOT NULL DEFAULT 0,
        amount_remaining  INTEGER NOT NULL DEFAULT 0,
        dpd               INTEGER NOT NULL DEFAULT 0,
        status            TEXT NOT NULL,
        total_outstanding INTEGER NOT NULL DEFAULT 0,
        product_source    TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_fact_customer ON fact_debt_installment(customer_sk)",
    "CREATE INDEX IF NOT EXISTS idx_fact_contract  ON fact_debt_installment(contract_no)",
    "CREATE INDEX IF NOT EXISTS idx_fact_due_date  ON fact_debt_installment(due_date_sk)",
    "CREATE INDEX IF NOT EXISTS idx_fact_dpd       ON fact_debt_installment(dpd)",
]

BATCH_SIZE = 5000


def _build_lookups(conn):
    """Build in-memory lookup dicts for fast SK resolution."""
    rows = conn.execute("SELECT national_id, customer_sk FROM dim_customer").fetchall()
    cust_map = {r["national_id"]: r["customer_sk"] for r in rows}

    rows = conn.execute("SELECT product_source, product_code, product_sk FROM dim_product").fetchall()
    prod_map = {(r["product_source"], r["product_code"]): r["product_sk"] for r in rows}

    rows = conn.execute("SELECT branch_code_clean, branch_sk FROM dim_branch").fetchall()
    branch_map = {r["branch_code_clean"]: r["branch_sk"] for r in rows}

    rows = conn.execute("SELECT date_sk FROM dim_date").fetchall()
    date_set = {r["date_sk"] for r in rows}

    return cust_map, prod_map, branch_map, date_set


def _insert_batch(conn, rows: list):
    conn.executemany(
        """INSERT INTO fact_debt_installment
           (customer_sk, product_sk, branch_sk, due_date_sk, payment_date_sk,
            contract_no, installment_no, amount_due, amount_paid,
            amount_remaining, dpd, status, total_outstanding, product_source)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        rows
    )
    conn.commit()


# ---------------------------------------------------------------------------
# CoreBank
# ---------------------------------------------------------------------------
def load_fact_corebank(conn):
    print("  Loading CoreBank fact rows...")
    cust_map, prod_map, branch_map, date_set = _build_lookups(conn)

    cb_cust = pd.read_csv(
        os.path.join(DATA_DIR, "cb_customer.csv"),
        dtype={"national_id": str, "customer_id": int}
    )
    cb_cust["national_id"] = cb_cust["national_id"].str.strip()
    cid_to_nid = dict(zip(cb_cust["customer_id"], cb_cust["national_id"]))

    cb_loan  = pd.read_csv(os.path.join(DATA_DIR, "cb_mortgage_loan.csv"))
    cb_sched = pd.read_csv(os.path.join(DATA_DIR, "cb_loan_schedule.csv"))
    cb_pay   = pd.read_csv(os.path.join(DATA_DIR, "cb_payment_transaction.csv"))

    cb_pay["payment_date"] = cb_pay["payment_date_raw"].apply(parse_dirty_date)
    pay_agg = cb_pay.groupby(["mortgage_loan_id", "installment_no"]).agg(
        payment_amount=("payment_amount", "sum"),
        payment_date=("payment_date", "max")
    ).reset_index()

    cb_sched["due_date"] = cb_sched["installment_due_date_raw"].apply(parse_dirty_date)

    loan_info = {}
    for _, r in cb_loan.iterrows():
        loan_info[int(r["mortgage_loan_id"])] = {
            "customer_id":      int(r["customer_id"]),
            "product_code":     str(r["product_code"]),
            "branch_code_raw":  str(r["branch_code_raw"]),
            "total_outstanding":int(r["total_outstanding"]),
            "contract_no":      str(r["contract_no"]),
        }

    merged = cb_sched.merge(pay_agg, on=["mortgage_loan_id", "installment_no"], how="left")

    rows = []
    skipped = 0
    for _, r in merged.iterrows():
        loan_id = int(r["mortgage_loan_id"])
        info = loan_info.get(loan_id)
        if info is None:
            skipped += 1
            continue

        nid = cid_to_nid.get(info["customer_id"])
        customer_sk = cust_map.get(nid) if nid else None
        if customer_sk is None:
            skipped += 1
            continue

        prod_sk = prod_map.get(("COREBANK", info["product_code"]))
        if prod_sk is None:
            skipped += 1
            continue

        clean = clean_branch(info["branch_code_raw"])
        branch_sk = branch_map.get(clean, 1)

        due_date = r["due_date"]
        if due_date is None:
            skipped += 1
            continue
        due_sk = date_to_sk(due_date)
        if due_sk not in date_set:
            skipped += 1
            continue

        amount_due  = int(r["installment_amount"]) if pd.notna(r["installment_amount"]) else 0
        amount_paid = int(r["payment_amount"]) if pd.notna(r.get("payment_amount")) else 0
        pay_date    = r.get("payment_date") if pd.notna(r.get("payment_date")) else None

        if pay_date is not None and not pd.isna(pay_date):
            pay_sk = date_to_sk(pay_date)
            dpd = max(0, (pay_date - due_date).days)
            status = "PAID" if amount_paid >= amount_due else "PARTIAL"
        else:
            pay_sk = None
            if due_date < SNAPSHOT_DATE:
                dpd = (SNAPSHOT_DATE - due_date).days
                status = "OVERDUE"
            else:
                dpd = 0
                status = "PENDING"

        amount_remaining = max(0, amount_due - amount_paid)

        rows.append((
            customer_sk, prod_sk, branch_sk,
            due_sk, pay_sk,
            info["contract_no"], int(r["installment_no"]),
            amount_due, amount_paid, amount_remaining,
            dpd, status, info["total_outstanding"], "COREBANK"
        ))

        if len(rows) >= BATCH_SIZE:
            _insert_batch(conn, rows)
            rows = []

    if rows:
        _insert_batch(conn, rows)

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM fact_debt_installment WHERE product_source='COREBANK'"
    ).fetchone()["n"]
    print(f"  CoreBank fact rows: {total} inserted, {skipped} skipped")


# ---------------------------------------------------------------------------
# CoreCard
# ---------------------------------------------------------------------------
def load_fact_corecard(conn):
    print("  Loading CoreCard fact rows...")
    cust_map, prod_map, branch_map, date_set = _build_lookups(conn)

    cc_user = pd.read_csv(
        os.path.join(DATA_DIR, "cc_user.csv"),
        dtype={"national_id": str, "cc_user_id": int}
    )
    cc_user["national_id"] = cc_user["national_id"].str.strip()
    uid_to_nid = dict(zip(cc_user["cc_user_id"], cc_user["national_id"]))

    cc_acc  = pd.read_csv(os.path.join(DATA_DIR, "cc_card_account.csv"))
    cc_stmt = pd.read_csv(os.path.join(DATA_DIR, "cc_card_statement.csv"))
    cc_pay  = pd.read_csv(os.path.join(DATA_DIR, "cc_card_payment.csv"))

    cc_pay["payment_date"] = cc_pay["payment_date_raw"].apply(parse_dirty_date)
    pay_agg = cc_pay.groupby("statement_id").agg(
        payment_amount=("payment_amount", "sum"),
        payment_date=("payment_date", "max")
    ).reset_index()

    cc_stmt["due_date"]       = cc_stmt["payment_due_date_raw"].apply(parse_dirty_date)
    cc_stmt["statement_date"] = cc_stmt["statement_date_raw"].apply(parse_dirty_date)

    cc_stmt = cc_stmt.sort_values(["card_account_id", "statement_date"])
    cc_stmt["installment_no"] = cc_stmt.groupby("card_account_id").cumcount() + 1

    acc_info = {}
    for _, r in cc_acc.iterrows():
        acc_info[int(r["card_account_id"])] = {
            "cc_user_id":      int(r["cc_user_id"]),
            "account_no":      str(r["account_no"]),
            "card_type":       str(r["card_type"]),
            "product_type":    str(r["product_type"]),
            "branch_code_raw": str(r["issuing_branch_code_raw"]),
            "current_balance": int(r["current_balance"]),
        }

    merged = cc_stmt.merge(pay_agg, on="statement_id", how="left")

    rows = []
    skipped = 0
    for _, r in merged.iterrows():
        acc_id = int(r["card_account_id"])
        info = acc_info.get(acc_id)
        if info is None:
            skipped += 1
            continue

        nid = uid_to_nid.get(info["cc_user_id"])
        customer_sk = cust_map.get(nid) if nid else None
        if customer_sk is None:
            skipped += 1
            continue

        product_code = f"{info['card_type']}:{info['product_type']}"
        prod_sk = prod_map.get(("CORECARD", product_code))
        if prod_sk is None:
            skipped += 1
            continue

        clean = clean_branch(info["branch_code_raw"])
        branch_sk = branch_map.get(clean, 1)

        due_date = r["due_date"]
        if due_date is None:
            skipped += 1
            continue
        due_sk = date_to_sk(due_date)
        if due_sk not in date_set:
            skipped += 1
            continue

        amount_due  = int(r["minimum_amount_due"]) if pd.notna(r["minimum_amount_due"]) else 0
        amount_paid = int(r["payment_amount"])      if pd.notna(r.get("payment_amount")) else 0
        pay_date    = r.get("payment_date")         if pd.notna(r.get("payment_date")) else None

        if pay_date is not None and not pd.isna(pay_date):
            pay_sk = date_to_sk(pay_date)
            dpd = max(0, (pay_date - due_date).days)
            status = "PAID" if amount_paid >= amount_due else "PARTIAL"
        else:
            pay_sk = None
            if due_date < SNAPSHOT_DATE:
                dpd = (SNAPSHOT_DATE - due_date).days
                status = "OVERDUE"
            else:
                dpd = 0
                status = "PENDING"

        amount_remaining = max(0, amount_due - amount_paid)

        rows.append((
            customer_sk, prod_sk, branch_sk,
            due_sk, pay_sk,
            info["account_no"], int(r["installment_no"]),
            amount_due, amount_paid, amount_remaining,
            dpd, status, info["current_balance"], "CORECARD"
        ))

        if len(rows) >= BATCH_SIZE:
            _insert_batch(conn, rows)
            rows = []

    if rows:
        _insert_batch(conn, rows)

    total = conn.execute(
        "SELECT COUNT(*) AS n FROM fact_debt_installment WHERE product_source='CORECARD'"
    ).fetchone()["n"]
    print(f"  CoreCard fact rows: {total} inserted, {skipped} skipped")


if __name__ == "__main__":
    conn = get_db_conn()
    for stmt in FACT_DDL_STATEMENTS:
        conn.execute(stmt)
    conn.commit()
    load_fact_corebank(conn)
    load_fact_corecard(conn)
    conn.close()
    print("Fact table loaded.")
