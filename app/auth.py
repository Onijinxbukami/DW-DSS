from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

auth_bp = Blueprint("auth", __name__)

# ---------------------------------------------------------------------------
# Hard-coded users for demo (no DB users table needed)
# collector_sk matches the order of collector_staff.csv (1-based ID)
# ---------------------------------------------------------------------------
USERS = {
    "manager":  {"password": "admin123",  "role": "manager",   "collector_sk": None, "name": "Quản Lý"},
    "COL-001":  {"password": "col001",    "role": "collector", "collector_sk": 1,    "name": "Bui Thu Linh"},
    "COL-002":  {"password": "col002",    "role": "collector", "collector_sk": 2,    "name": "Nguyen Thi Trang"},
    "COL-003":  {"password": "col003",    "role": "collector", "collector_sk": 3,    "name": "Dang Quang Chau"},
    "COL-004":  {"password": "col004",    "role": "collector", "collector_sk": 4,    "name": "Vo Thi Huy"},
    "COL-005":  {"password": "col005",    "role": "collector", "collector_sk": 5,    "name": "Pham Quang Thao"},
    "COL-006":  {"password": "col006",    "role": "collector", "collector_sk": 6,    "name": "Tran Thu Trang"},
    "COL-007":  {"password": "col007",    "role": "collector", "collector_sk": 7,    "name": "Huynh Thanh Dung"},
    "COL-008":  {"password": "col008",    "role": "collector", "collector_sk": 8,    "name": "Tran Duc Dung"},
    "COL-009":  {"password": "col009",    "role": "collector", "collector_sk": 9,    "name": "Dang Thanh Chau"},
    "COL-010":  {"password": "col010",    "role": "collector", "collector_sk": 10,   "name": "Bui Van Hieu"},
    "COL-011":  {"password": "col011",    "role": "collector", "collector_sk": 11,   "name": "Dang Van Khanh"},
    "COL-012":  {"password": "col012",    "role": "collector", "collector_sk": 12,   "name": "Phan Minh Hieu"},
    "COL-013":  {"password": "col013",    "role": "collector", "collector_sk": 13,   "name": "Phan Ngoc Khoa"},
    "COL-014":  {"password": "col014",    "role": "collector", "collector_sk": 14,   "name": "Nguyen Thi Binh"},
    "COL-015":  {"password": "col015",    "role": "collector", "collector_sk": 15,   "name": "Bui Hai Trang"},
    "COL-016":  {"password": "col016",    "role": "collector", "collector_sk": 16,   "name": "Vo Duc Tuan"},
    "COL-017":  {"password": "col017",    "role": "collector", "collector_sk": 17,   "name": "Phan Duc Binh"},
    "COL-018":  {"password": "col018",    "role": "collector", "collector_sk": 18,   "name": "Hoang Anh Vy"},
    "COL-019":  {"password": "col019",    "role": "collector", "collector_sk": 19,   "name": "Nguyen Quang Tuan"},
    "COL-020":  {"password": "col020",    "role": "collector", "collector_sk": 20,   "name": "Tran Thu Linh"},
}


def login_required(role=None):
    """Decorator to protect routes. role='collector' or 'manager' or None (any)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                return redirect(url_for("auth.login"))
            if role and session.get("role") != role:
                flash("Bạn không có quyền truy cập trang này.", "danger")
                return redirect(url_for("auth.login"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        user = USERS.get(username)
        if user and user["password"] == password:
            session["username"]     = username
            session["role"]         = user["role"]
            session["collector_sk"] = user["collector_sk"]
            session["name"]         = user["name"]
            if user["role"] == "manager":
                return redirect(url_for("manager.dashboard"))
            return redirect(url_for("collector.tasks"))
        flash("Tên đăng nhập hoặc mật khẩu không đúng.", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
