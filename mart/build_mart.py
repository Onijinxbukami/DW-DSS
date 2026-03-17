"""
Build (or rebuild) dm_daily_collection_tasks for a given snapshot date.
Called by:
  - CLI: python mart/build_mart.py [YYYY-MM-DD]
  - apply_config() in Flask routes when Manager clicks Apply
"""
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import get_db_conn
from models.model1_channel import assign_channel
from models.model2_risk_score import compute_risk_scores, weights_from_config
from models.assign_collectors import assign_collectors


# ---------------------------------------------------------------------------
# 6-month behavior aggregate
# ---------------------------------------------------------------------------
_BEHAVIOR_SQL = """
SELECT
    f.customer_sk,
    f.contract_no,
    COUNT(CASE WHEN f.status IN ('OVERDUE','PARTIAL')
               AND f.due_date_sk >= 20240630 THEN 1 END)  AS num_overdue_6m,
    MAX(CASE WHEN f.due_date_sk >= 20240630
             THEN f.dpd ELSE 0 END)                        AS max_dpd_6m
FROM fact_debt_installment f
GROUP BY f.customer_sk, f.contract_no
"""

# Latest overdue installment per (customer_sk, contract_no)
_CURRENT_TASKS_SQL = """
SELECT
    f.fact_id,
    f.customer_sk,
    f.contract_no,
    f.product_source,
    f.branch_sk,
    f.dpd          AS dpd_current,
    f.amount_due   AS amount_due_current,
    f.total_outstanding,
    p.product_code,
    c.full_name    AS customer_name,
    c.national_id,
    c.phone,
    c.email,
    b.branch_name
FROM fact_debt_installment f
JOIN dim_customer c  ON f.customer_sk = c.customer_sk
JOIN dim_product  p  ON f.product_sk  = p.product_sk
JOIN dim_branch   b  ON f.branch_sk   = b.branch_sk
WHERE f.dpd > 0
  AND f.due_date_sk = (
      SELECT MAX(f2.due_date_sk)
      FROM fact_debt_installment f2
      WHERE f2.customer_sk  = f.customer_sk
        AND f2.contract_no  = f.contract_no
        AND f2.dpd > 0
  )
"""


def build_mart(snapshot_date: str | None = None, conn=None):
    """
    snapshot_date: 'YYYY-MM-DD' string; defaults to today.
    conn: existing sqlite3 connection (reused by Flask); if None, opens a new one.
    """
    close_conn = False
    if conn is None:
        conn = get_db_conn()
        close_conn = True

    if snapshot_date is None:
        snapshot_date = date.today().isoformat()

    print(f"Building data mart for snapshot_date={snapshot_date}...")

    # 1. Load active scoring config
    cfg = conn.execute(
        "SELECT * FROM scoring_config ORDER BY config_id DESC LIMIT 1"
    ).fetchone()
    if cfg is None:
        raise RuntimeError("No scoring_config found. Run ETL first.")
    config_id = cfg["config_id"]
    weights   = weights_from_config(cfg)

    # 2. Load current overdue tasks
    tasks_df = pd.read_sql_query(_CURRENT_TASKS_SQL, conn)
    if tasks_df.empty:
        print("  No overdue tasks found.")
        if close_conn:
            conn.close()
        return 0

    # 3. Load 6-month behavior
    behavior_df = pd.read_sql_query(_BEHAVIOR_SQL, conn)

    # 4. Merge
    tasks_df = tasks_df.merge(
        behavior_df, on=["customer_sk", "contract_no"], how="left"
    )
    tasks_df["num_overdue_6m"] = tasks_df["num_overdue_6m"].fillna(0).astype(int)
    tasks_df["max_dpd_6m"]     = tasks_df["max_dpd_6m"].fillna(0).astype(int)

    # 5. Model 1 – channel assignment
    channels = tasks_df["dpd_current"].apply(assign_channel)
    tasks_df["dpd_bucket"]      = channels.apply(lambda x: x[0])
    tasks_df["assigned_channel"]= channels.apply(lambda x: x[1])

    # Keep only actionable tasks (dpd_bucket != ON_TIME)
    tasks_df = tasks_df[tasks_df["dpd_bucket"] != "ON_TIME"].copy()

    # 6. Model 2 – risk score
    tasks_df = compute_risk_scores(tasks_df, weights)

    # 7. Assign collectors
    collectors_df = pd.read_sql_query(
        "SELECT collector_sk, collector_name, team, branch_sk, max_daily_cases, is_active "
        "FROM dim_collector",
        conn
    )
    tasks_df = assign_collectors(tasks_df, collectors_df)

    # 8. Delete existing rows for this snapshot date
    conn.execute(
        "DELETE FROM dm_daily_collection_tasks WHERE snapshot_date = ?",
        (snapshot_date,)
    )

    # 9. Insert
    insert_rows = []
    for _, r in tasks_df.iterrows():
        insert_rows.append((
            snapshot_date,
            int(r["customer_sk"])     if pd.notna(r["customer_sk"])     else None,
            str(r["customer_name"])   if pd.notna(r["customer_name"])   else None,
            str(r["national_id"])     if pd.notna(r["national_id"])     else None,
            str(r["phone"])           if pd.notna(r["phone"])           else None,
            str(r["email"])           if pd.notna(r["email"])           else None,
            str(r["contract_no"])     if pd.notna(r["contract_no"])     else None,
            str(r["product_source"])  if pd.notna(r["product_source"])  else None,
            str(r["product_code"])    if pd.notna(r["product_code"])    else None,
            int(r["branch_sk"])       if pd.notna(r["branch_sk"])       else None,
            str(r["branch_name"])     if pd.notna(r["branch_name"])     else None,
            int(r["total_outstanding"])     if pd.notna(r["total_outstanding"])     else 0,
            int(r["amount_due_current"])    if pd.notna(r["amount_due_current"])    else 0,
            int(r["dpd_current"])           if pd.notna(r["dpd_current"])           else 0,
            str(r["dpd_bucket"])            if pd.notna(r["dpd_bucket"])            else None,
            str(r["assigned_channel"])      if pd.notna(r["assigned_channel"])      else None,
            int(r["num_overdue_6m"])        if pd.notna(r["num_overdue_6m"])        else 0,
            int(r["max_dpd_6m"])            if pd.notna(r["max_dpd_6m"])            else 0,
            float(r["risk_score"])          if pd.notna(r["risk_score"])            else 0.0,
            int(r["priority_rank"])         if pd.notna(r["priority_rank"])         else 0,
            int(r["collector_sk"])          if pd.notna(r.get("collector_sk"))      else None,
            str(r["collector_name"])        if pd.notna(r.get("collector_name"))    else None,
            "PENDING",
            config_id,
        ))

    conn.executemany(
        """INSERT INTO dm_daily_collection_tasks
           (snapshot_date, customer_sk, customer_name, national_id, phone, email,
            contract_no, product_source, product_code, branch_sk, branch_name,
            total_outstanding, amount_due_current, dpd_current,
            dpd_bucket, assigned_channel, num_overdue_6m, max_dpd_6m,
            risk_score, priority_rank, collector_sk, collector_name,
            task_status, config_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        insert_rows
    )
    conn.commit()

    n = len(insert_rows)
    print(f"  Inserted {n:,} tasks for {snapshot_date} (config_id={config_id})")

    if close_conn:
        conn.close()
    return n


if __name__ == "__main__":
    snapshot = sys.argv[1] if len(sys.argv) > 1 else None
    build_mart(snapshot)
