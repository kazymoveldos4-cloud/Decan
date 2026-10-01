from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import RegistrationPeriod, Course, Application, log_action

bp = Blueprint("student", __name__, url_prefix="/student")


def _require_student():
    if current_user.role_name != "student":
        abort(403)


@bp.route("/dashboard")
@login_required
def dashboard():
    _require_student()
    now = datetime.utcnow()
    open_periods = RegistrationPeriod.query.filter(
        RegistrationPeriod.status == "open",
        RegistrationPeriod.start_date <= now,
        RegistrationPeriod.end_date >= now,
    ).all()
    return render_template("student_dashboard.html", periods=open_periods)


@bp.route("/courses/<int:period_id>")
@login_required
def course_list(period_id):
    _require_student()
    period = RegistrationPeriod.query.get_or_404(period_id)
    courses = Course.query.filter_by(period_id=period_id, status="active").all()

    my_apps = {
        a.course_id: a
        for a in Application.query.filter_by(student_id=current_user.user_id, period_id=period_id).all()
    }
    return render_template("course_list.html", period=period, courses=courses, my_apps=my_apps)


@bp.route("/apply/<int:period_id>", methods=["GET", "POST"])
@login_required
def apply(period_id):
    _require_student()
    period = RegistrationPeriod.query.get_or_404(period_id)

    if period.status != "open":
        flash("Период записи закрыт.", "warning")
        return redirect(url_for("student.dashboard"))

    courses = Course.query.filter_by(period_id=period_id, status="active").all()

    if request.method == "POST":
        # form: priority_<course_id> = число приоритета (пусто = не выбран)
        chosen = []
        for course in courses:
            raw = request.form.get(f"priority_{course.course_id}", "").strip()
            if raw:
                try:
                    p = int(raw)
                except ValueError:
                    continue
                if p > 0:
                    chosen.append((course.course_id, p))

        priorities_used = [p for _, p in chosen]
        if not chosen:
            flash("Нужно выбрать хотя бы один курс с приоритетом.", "warning")
            return redirect(url_for("student.apply", period_id=period_id))

        if len(priorities_used) != len(set(priorities_used)):
            flash("Каждый приоритет можно использовать только один раз.", "danger")
            return redirect(url_for("student.apply", period_id=period_id))

        if max(priorities_used) > period.max_priorities:
            flash(f"Максимально допустимый приоритет: {period.max_priorities}.", "danger")
            return redirect(url_for("student.apply", period_id=period_id))

        # удаляем старые заявки студента на этот период (пересдача формы)
        Application.query.filter_by(student_id=current_user.user_id, period_id=period_id).delete()

        for course_id, p in chosen:
            db.session.add(Application(
                student_id=current_user.user_id,
                period_id=period_id,
                course_id=course_id,
                priority=p,
                status="submitted",
            ))

        log_action(current_user.user_id, "submit_application", "registration_period", period_id)
        db.session.commit()
        flash("Заявка успешно подана.", "success")
        return redirect(url_for("student.my_applications", period_id=period_id))

    my_apps = {
        a.course_id: a
        for a in Application.query.filter_by(student_id=current_user.user_id, period_id=period_id).all()
    }
    return render_template("apply.html", period=period, courses=courses, my_apps=my_apps)


@bp.route("/applications/<int:period_id>")
@login_required
def my_applications(period_id):
    _require_student()
    period = RegistrationPeriod.query.get_or_404(period_id)
    apps = (
        Application.query.filter_by(student_id=current_user.user_id, period_id=period_id)
        .order_by(Application.priority)
        .all()
    )
    return render_template("my_applications.html", period=period, apps=apps)
