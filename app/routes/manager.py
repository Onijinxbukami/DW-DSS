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

    kpi_overdue = conn.execute(
        "SELECT COUNT(DISTINCT contract_no) AS n FROM dm_daily_collection_tasks "
        "WHERE dpd_current > 0 AND snapshot_date = %s", (SNAPSHOT_DATE,)
    ).fetchone()["n"] or 0

    kpi_outstanding = conn.execute(
        "SELECT COALESCE(SUM(total_outstanding),0) AS n FROM dm_daily_collection_tasks "
        "WHERE dpd_current > 0 AND snapshot_date = %s", (SNAPSHOT_DATE,)
    ).fetchone()["n"] or 0

    total_tasks = conn.execute(
        "SELECT COUNT(*) AS n FROM dm_daily_collection_tasks WHERE snapshot_date = %s",
        (SNAPSHOT_DATE,)
    ).fetchone()["n"] or 1

    done_tasks = conn.execute(
        "SELECT COUNT(*) AS n FROM dm_daily_collection_tasks "
        "WHERE task_status='DONE' AND snapshot_date = %s", (SNAPSHOT_DATE,)
    ).fetchone()["n"] or 0

    kpi_done_pct = round(100.0 * done_tasks / total_tasks, 1) if total_tasks else 0

    kpi_active_collectors = conn.execute(
        "SELECT COUNT(DISTINCT collector_sk) AS n FROM dm_daily_collection_tasks "
        "WHERE snapshot_date = %s AND collector_sk IS NOT NULL", (SNAPSHOT_DATE,)
    ).fetchone()["n"] or 0

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

    conn.close()

    return render_template(
        "manager/dashboard.html",
        kpi_overdue=kpi_overdue,
        kpi_outstanding=kpi_outstanding,
        kpi_done_pct=kpi_done_pct,
        kpi_active_collectors=kpi_active_collectors,
        bucket_data=json.dumps(bucket_data),
        channel_data=json.dumps(channel_data),
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
        "SELECT * FROM dm_daily_collection_tasks WHERE snapshot_date = %s",
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
         "old_risk_score", "old_priority_rank",
         "risk_score", "priority_rank", "rank_delta", "score_delta"]
    ].to_dict(orient="records")

    rank_changes = int((tasks["priority_rank"] != tasks["old_priority_rank"]).sum())

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
        "score_distribution": score_distribution,
    })


@manager_bp.route("/whatif/apply", methods=["POST"])
@login_required(role="manager")
def whatif_apply():
    from mart.build_mart import build_mart

    data    = request.get_json()
    alpha   = float(data.get("alpha",   20))
    beta    = float(data.get("beta",    25))
    gamma   = float(data.get("gamma",   0.5))
    delta   = float(data.get("delta",   10))
    epsilon = float(data.get("epsilon", 5))
    desc    = data.get("description", "Applied via What-If UI")

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

    n = build_mart(SNAPSHOT_DATE, conn)
    conn.close()

    return jsonify({
        "success":       True,
        "config_id":     new_config_id,
        "tasks_updated": n,
    })
