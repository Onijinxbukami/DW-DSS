from flask import Flask, redirect, url_for, session
from config import SECRET_KEY


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = SECRET_KEY

    from app.auth import auth_bp
    from app.routes.collector import collector_bp
    from app.routes.manager import manager_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(collector_bp, url_prefix="/collector")
    app.register_blueprint(manager_bp,   url_prefix="/manager")

    @app.route("/")
    def index():
        if "role" not in session:
            return redirect(url_for("auth.login"))
        if session["role"] == "manager":
            return redirect(url_for("manager.dashboard"))
        return redirect(url_for("collector.tasks"))

    return app
