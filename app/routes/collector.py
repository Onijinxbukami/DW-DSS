from flask import Blueprint, render_template, request, jsonify, session
from app.db import get_db
from app.auth import login_required
from config import SNAPSHOT_DATE_STR as SNAPSHOT_DATE

collector_bp = Blueprint("collector", __name__)


@collector_bp.route("/tasks")
@login_required(role="collector")
def tasks():
    collector_sk = session.get("collector_sk")
    conn = get_db()
    tasks = conn.execute(
        """SELECT * FROM dm_daily_collection_tasks
           WHERE collector_sk = ? AND snapshot_date = ?
           ORDER BY priority_rank ASC""",
        (collector_sk, SNAPSHOT_DATE)
    ).fetchall()
    conn.close()
    return render_template("collector/tasks.html", tasks=tasks)


@collector_bp.route("/update_status", methods=["POST"])
@login_required(role="collector")
def update_status():
    data     = request.get_json()
    task_id  = data.get("task_id")
    new_status = data.get("new_status")
    if new_status not in ("IN_PROGRESS", "DONE", "SKIPPED", "PENDING"):
        return jsonify({"success": False, "error": "Invalid status"}), 400
    conn = get_db()
    conn.execute(
        "UPDATE dm_daily_collection_tasks SET task_status = ? WHERE task_id = ?",
        (new_status, task_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@collector_bp.route("/task_detail/<int:task_id>")
@login_required(role="collector")
def task_detail(task_id):
    conn = get_db()
    task = conn.execute(
        "SELECT * FROM dm_daily_collection_tasks WHERE task_id = ?",
        (task_id,)
    ).fetchone()
    if task is None:
        return jsonify({"error": "Not found"}), 404

    # Last 6 installments for this customer + contract
    # Use pre-computed fact_history_6m if available (Vercel deploy.db),
    # otherwise fall back to the full fact table.
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    if "fact_history_6m" in tables:
        history = conn.execute(
            """SELECT due_date, amount_due, amount_paid, dpd, status
               FROM fact_history_6m
               WHERE customer_sk = ? AND contract_no = ?
               ORDER BY due_date DESC
               LIMIT 6""",
            (task["customer_sk"], task["contract_no"])
        ).fetchall()
    else:
        history = conn.execute(
            """SELECT d.full_date AS due_date, f.amount_due, f.amount_paid,
                      f.dpd, f.status
               FROM fact_debt_installment f
               JOIN dim_date d ON f.due_date_sk = d.date_sk
               WHERE f.customer_sk = ? AND f.contract_no = ?
                 AND f.due_date_sk >= 20240630
               ORDER BY f.due_date_sk DESC
               LIMIT 6""",
            (task["customer_sk"], task["contract_no"])
        ).fetchall()
    conn.close()

    history_list = [dict(h) for h in history]
    return jsonify({
        "task":    dict(task),
        "history": history_list,
    })
