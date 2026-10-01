from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import User, log_action
from extensions import db

bp = Blueprint("auth", __name__)


def _redirect_by_role(user):
    if user.role_name == "student":
        return redirect(url_for("student.dashboard"))
    if user.role_name == "deputy_dean":
        return redirect(url_for("deputy.dashboard"))
    if user.role_name == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("auth.login"))


@bp.route("/", methods=["GET"])
def index():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)
    return redirect(url_for("auth.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter(User.email.ilike(email)).first()

        if user and user.is_active and check_password_hash(user.password_hash, password):
            login_user(user)
            log_action(user.user_id, "login", "user", user.user_id)
            db.session.commit()
            return _redirect_by_role(user)

        flash("Неверный email или пароль, либо аккаунт отключён.", "danger")

    return render_template("login.html")


@bp.route("/logout")
@login_required
def logout():
    log_action(current_user.user_id, "logout", "user", current_user.user_id)
    db.session.commit()
    logout_user()
    flash("Вы вышли из системы.", "info")
    return redirect(url_for("auth.login"))
