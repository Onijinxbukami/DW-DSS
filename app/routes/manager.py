import json
from flask import Blueprint, render_template, request, jsonify, session

from app.db import get_db
from app.auth import login_required
from config import SNAPSHOT_DATE_STR as SNAPSHOT_DATE
from models.model2_risk_score import compute_risk_scores, weights_from_config
from models.model1_channel import assign_channel
import pandas as pd

manager_bp = Blueprint("manager", __name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@manager_bp.route("/dashboard")
@login_required(role="manager")
def dashboard():
    conn = get_db()

    # Single round-trip for all KPIs
    row = conn.execute(
        """SELECT
             COUNT(DISTINCT CASE WHEN dpd_current > 0 THEN contract_no END)          AS kpi_overdue,
             COALESCE(SUM(CASE WHEN dpd_current > 0 THEN total_outstanding END), 0)   AS kpi_outstanding,
             COUNT(*)                                                                   AS total_tasks,
             SUM(CASE WHEN task_status = 'DONE' THEN 1 ELSE 0 END)                   AS done_tasks,
             COUNT(DISTINCT CASE WHEN collector_sk IS NOT NULL THEN collector_sk END)  AS kpi_active_collectors
           FROM dm_daily_collection_tasks
           WHERE snapshot_date = %s""",
        (SNAPSHOT_DATE,)
    ).fetchone()

    kpi_overdue           = row["kpi_overdue"] or 0
    kpi_outstanding       = int(row["kpi_outstanding"] or 0)
    total_tasks           = row["total_tasks"] or 1
    done_tasks            = row["done_tasks"] or 0
    kpi_done_pct          = round(100.0 * done_tasks / total_tasks, 1)
    kpi_active_collectors = row["kpi_active_collectors"] or 0

    # DPD bucket distribution
    bucket_rows = conn.execute(
        "SELECT dpd_bucket, COUNT(*) AS cnt FROM dm_daily_collection_tasks "
        "WHERE snapshot_date = %s GROUP BY dpd_bucket ORDER BY dpd_bucket",
        (SNAPSHOT_DATE,)
    ).fetchall()
    bucket_data = {r["dpd_bucket"]: r["cnt"] for r in bucket_rows}

    # Collector performance
    perf_rows = conn.execute(
        """SELECT collector_name,
                  COUNT(*)                                                AS assigned,
                  SUM(CASE WHEN task_status='DONE'        THEN 1 ELSE 0 END) AS done,
                  SUM(CASE WHEN task_status='SKIPPED'     THEN 1 ELSE 0 END) AS skipped,
                  SUM(CASE WHEN task_status='IN_PROGRESS' THEN 1 ELSE 0 END) AS in_progress
           FROM dm_daily_collection_tasks
           WHERE snapshot_date = %s
           GROUP BY collector_sk, collector_name
           ORDER BY done DESC""",
        (SNAPSHOT_DATE,)
    ).fetchall()

    # Channel distribution
    channel_rows = conn.execute(
        "SELECT assigned_channel, COUNT(*) AS cnt FROM dm_daily_collection_tasks "
        "WHERE snapshot_date = %s GROUP BY assigned_channel",
        (SNAPSHOT_DATE,)
    ).fetchall()
    channel_data = {r["assigned_channel"]: r["cnt"] for r in channel_rows}

    # Risk score histogram (10 buckets)
    risk_rows = conn.execute(
        """SELECT
             CASE
               WHEN risk_score < 20  THEN '0–20'
               WHEN risk_score < 40  THEN '20–40'
               WHEN risk_score < 60  THEN '40–60'
               WHEN risk_score < 80  THEN '60–80'
               WHEN risk_score < 100 THEN '80–100'
               ELSE '100+'
             END AS bucket,
             COUNT(*) AS cnt
           FROM dm_daily_collection_tasks
           WHERE snapshot_date = %s
           GROUP BY bucket
           ORDER BY MIN(risk_score)""",
        (SNAPSHOT_DATE,)
    ).fetchall()
    risk_data = {r["bucket"]: r["cnt"] for r in risk_rows}

    # Task status distribution
    status_rows = conn.execute(
        "SELECT task_status, COUNT(*) AS cnt FROM dm_daily_collection_tasks "
        "WHERE snapshot_date = %s GROUP BY task_status",
        (SNAPSHOT_DATE,)
    ).fetchall()
    status_data = {r["task_status"]: r["cnt"] for r in status_rows}

    conn.close()

    return render_template(
        "manager/dashboard.html",
        kpi_overdue=kpi_overdue,
        kpi_outstanding=kpi_outstanding,
        kpi_done_pct=kpi_done_pct,
        kpi_active_collectors=kpi_active_collectors,
        bucket_data=json.dumps(bucket_data),
        channel_data=json.dumps(channel_data),
        risk_data=json.dumps(risk_data),
        status_data=json.dumps(status_data),
        perf_rows=[dict(r) for r in perf_rows],
        snapshot_date=SNAPSHOT_DATE,
    )


# ---------------------------------------------------------------------------
# What-If
# ---------------------------------------------------------------------------
@manager_bp.route("/whatif")
@login_required(role="manager")
def whatif():
    conn = get_db()
    cfg = conn.execute(
        "SELECT * FROM scoring_config ORDER BY config_id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    current_weights = {
        "alpha":        cfg["alpha_num_overdue_6m"],
        "beta":         cfg["beta_max_dpd_6m"],
        "gamma":        cfg["gamma_dpd_current"],
        "delta":        cfg["delta_amount_band"],
        "epsilon":      cfg["epsilon_product_source_mortgage"],
        "config_id":    cfg["config_id"],
        "effective_date": cfg["effective_date"],
        "description":  cfg["description"],
    }
    return render_template("manager/whatif.html", current_weights=current_weights)


@manager_bp.route("/whatif/preview", methods=["POST"])
@login_required(role="manager")
def whatif_preview():
    data = request.get_json()
    new_weights = {
        "alpha":   float(data.get("alpha",   20)),
        "beta":    float(data.get("beta",    25)),
        "gamma":   float(data.get("gamma",   0.5)),
        "delta":   float(data.get("delta",   10)),
        "epsilon": float(data.get("epsilon", 5)),
    }

    conn = get_db()
    tasks = pd.read_sql_query(
        """SELECT task_id, customer_name, contract_no, dpd_current, total_outstanding,
                  product_source, num_overdue_6m, max_dpd_6m,
                  risk_score, priority_rank, assigned_channel
           FROM dm_daily_collection_tasks WHERE snapshot_date = %s""",
        conn.raw,
        params=(SNAPSHOT_DATE,)
    )
    conn.close()

    if tasks.empty:
        return jsonify({"error": "No tasks found"}), 404

    tasks["old_risk_score"]    = tasks["risk_score"]
    tasks["old_priority_rank"] = tasks["priority_rank"]

    tasks = compute_risk_scores(tasks, new_weights)

    tasks["rank_delta"]  = tasks["old_priority_rank"] - tasks["priority_rank"]
    tasks["score_delta"] = (tasks["risk_score"] - tasks["old_risk_score"]).round(2)

    top20 = tasks.nsmallest(20, "priority_rank")[
        ["task_id", "customer_name", "contract_no", "dpd_current",
         "total_outstanding", "old_risk_score", "old_priority_rank",
         "risk_score", "priority_rank", "rank_delta", "score_delta"]
    ].to_dict(orient="records")

    rank_changes = int((tasks["priority_rank"] != tasks["old_priority_rank"]).sum())
    channel_changes = int((tasks.apply(
        lambda r: assign_channel(r["dpd_current"]), axis=1
    ) != tasks["assigned_channel"]).sum()) if "assigned_channel" in tasks.columns else 0

    hist_bins = [0, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 7000, 10000]
    old_hist = pd.cut(tasks["old_risk_score"], bins=hist_bins).value_counts().sort_index()
    new_hist = pd.cut(tasks["risk_score"],     bins=hist_bins).value_counts().sort_index()
    score_distribution = {
        "labels":   [str(i) for i in old_hist.index.astype(str)],
        "old_data": old_hist.tolist(),
        "new_data": new_hist.tolist(),
    }

    return jsonify({
        "top20":              top20,
        "rank_changes":       rank_changes,
        "channel_changes":    channel_changes,
        "score_distribution": score_distribution,
    })


@manager_bp.route("/whatif/apply", methods=["POST"])
@login_required(role="manager")
def whatif_apply():
    from mart.build_mart import update_scores_only

    data    = request.get_json()
    alpha   = float(data.get("alpha",   20))
    beta    = float(data.get("beta",    25))
    gamma   = float(data.get("gamma",   0.5))
    delta   = float(data.get("delta",   10))
    epsilon = float(data.get("epsilon", 5))
    desc    = data.get("description", "Applied via What-If UI")
    weights = {"alpha": alpha, "beta": beta, "gamma": gamma,
               "delta": delta, "epsilon": epsilon}

    conn = get_db()
    conn.execute(
        """INSERT INTO scoring_config
           (effective_date, alpha_num_overdue_6m, beta_max_dpd_6m,
            gamma_dpd_current, delta_amount_band,
            epsilon_product_source_mortgage, applied_by, description)
           VALUES (NOW(), %s,%s,%s,%s,%s,%s,%s)""",
        (alpha, beta, gamma, delta, epsilon, session.get("name", "manager"), desc)
    )
    conn.commit()
    new_config_id = conn.execute(
        "SELECT MAX(config_id) AS n FROM scoring_config"
    ).fetchone()["n"]

    n = update_scores_only(SNAPSHOT_DATE, weights, new_config_id, conn)
    conn.close()

    return jsonify({
        "success":       True,
        "config_id":     new_config_id,
        "tasks_updated": n,
    })
