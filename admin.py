from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from extensions import db
from models import User, Role, Faculty, log_action

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _require_admin():
    if current_user.role_name != "admin":
        abort(403)


@bp.route("/dashboard")
@login_required
def dashboard():
    _require_admin()
    users = User.query.order_by(User.user_id.desc()).limit(20).all()
    return render_template("admin_users.html", users=users, roles=Role.query.all(),
                            faculties=Faculty.query.all())


@bp.route("/users", methods=["POST"])
@login_required
def create_user():
    _require_admin()
    full_name = request.form["full_name"].strip()
    email = request.form["email"].strip().lower()
    password = request.form["password"]
    role_id = int(request.form["role_id"])
    faculty_id = request.form.get("faculty_id") or None
    student_group = request.form.get("student_group", "").strip() or None

    if User.query.filter(User.email.ilike(email)).first():
        flash("Пользователь с таким email уже существует.", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User(
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
        role_id=role_id,
        faculty_id=faculty_id,
        student_group=student_group,
        is_active_db=True,
    )
    db.session.add(user)
    db.session.commit()
    log_action(current_user.user_id, "create_user", "user", user.user_id)
    db.session.commit()
    flash(f"Пользователь {email} создан.", "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def toggle_user(user_id):
    _require_admin()
    user = User.query.get_or_404(user_id)
    user.is_active_db = not user.is_active_db
    db.session.commit()
    return redirect(url_for("admin.dashboard"))


@bp.route("/faculties", methods=["POST"])
@login_required
def create_faculty():
    _require_admin()
    name = request.form["faculty_name"].strip()
    code = request.form["faculty_code"].strip()
    if Faculty.query.filter_by(faculty_code=code).first():
        flash("Факультет с таким кодом уже существует.", "danger")
        return redirect(url_for("admin.dashboard"))
    db.session.add(Faculty(faculty_name=name, faculty_code=code))
    db.session.commit()
    flash("Факультет добавлен.", "success")
    return redirect(url_for("admin.dashboard"))
