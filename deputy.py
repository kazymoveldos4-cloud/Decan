from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import (
    RegistrationPeriod, Course, Application, Faculty,
    AllocationRun, AllocationResult, log_action,
)
from allocation import run_allocation, manual_override

bp = Blueprint("deputy", __name__, url_prefix="/deputy")


def _require_deputy():
    if current_user.role_name not in ("deputy_dean", "admin"):
        abort(403)


@bp.route("/dashboard")
@login_required
def dashboard():
    _require_deputy()
    periods = RegistrationPeriod.query.order_by(RegistrationPeriod.start_date.desc()).all()
    return render_template("deputy_dashboard.html", periods=periods)


# ---------- Периоды ----------

@bp.route("/periods", methods=["GET", "POST"])
@login_required
def periods():
    _require_deputy()
    if request.method == "POST":
        semester_code = request.form["semester_code"].strip()
        start_date = datetime.fromisoformat(request.form["start_date"])
        end_date = datetime.fromisoformat(request.form["end_date"])
        max_priorities = int(request.form.get("max_priorities", 5))

        db.session.add(RegistrationPeriod(
            semester_code=semester_code,
            start_date=start_date,
            end_date=end_date,
            max_priorities=max_priorities,
            status="planned",
        ))
        db.session.commit()
        flash("Период создан.", "success")
        return redirect(url_for("deputy.periods"))

    all_periods = RegistrationPeriod.query.order_by(RegistrationPeriod.start_date.desc()).all()
    return render_template("periods.html", periods=all_periods)


@bp.route("/periods/<int:period_id>/status", methods=["POST"])
@login_required
def change_period_status(period_id):
    _require_deputy()
    period = RegistrationPeriod.query.get_or_404(period_id)
    new_status = request.form.get("status")
    if new_status in ("planned", "open", "closed", "allocated"):
        period.status = new_status
        log_action(current_user.user_id, "change_status", "registration_period", period_id, new_status)
        db.session.commit()
        flash("Статус периода обновлён.", "success")
    return redirect(url_for("deputy.periods"))


# ---------- Курсы ----------

@bp.route("/courses/<int:period_id>", methods=["GET", "POST"])
@login_required
def courses(period_id):
    _require_deputy()
    period = RegistrationPeriod.query.get_or_404(period_id)

    if request.method == "POST":
        title = request.form["title"].strip()
        teacher_name = request.form.get("teacher_name", "").strip()
        description = request.form.get("description", "").strip()
        total_seats = int(request.form["total_seats"])
        faculty_id = request.form.get("faculty_id") or None

        db.session.add(Course(
            period_id=period_id,
            faculty_id=faculty_id,
            title=title,
            description=description,
            teacher_name=teacher_name,
            total_seats=total_seats,
            occupied_seats=0,
            status="active",
        ))
        db.session.commit()
        flash("Курс добавлен.", "success")
        return redirect(url_for("deputy.courses", period_id=period_id))

    course_list = Course.query.filter_by(period_id=period_id).all()
    faculties = Faculty.query.all()
    return render_template("courses.html", period=period, courses=course_list, faculties=faculties)


@bp.route("/courses/<int:course_id>/archive", methods=["POST"])
@login_required
def archive_course(course_id):
    _require_deputy()
    course = Course.query.get_or_404(course_id)
    course.status = "archived" if course.status == "active" else "active"
    db.session.commit()
    return redirect(url_for("deputy.courses", period_id=course.period_id))


# ---------- Заявки ----------

@bp.route("/applications/<int:period_id>")
@login_required
def applications(period_id):
    _require_deputy()
    period = RegistrationPeriod.query.get_or_404(period_id)
    apps = (
        Application.query.filter_by(period_id=period_id)
        .order_by(Application.course_id, Application.priority)
        .all()
    )
    return render_template("applications_review.html", period=period, apps=apps)


# ---------- Распределение ----------

@bp.route("/allocate/<int:period_id>", methods=["POST"])
@login_required
def allocate(period_id):
    _require_deputy()
    period = RegistrationPeriod.query.get_or_404(period_id)

    if period.status not in ("open", "closed"):
        flash("Распределение можно запускать только для открытого или закрытого периода.", "warning")
        return redirect(url_for("deputy.dashboard"))

    try:
        run = run_allocation(period_id, current_user.user_id)
        flash(f"Распределение выполнено (run #{run.run_id}).", "success")
    except Exception as e:
        flash(f"Ошибка при распределении: {e}", "danger")

    return redirect(url_for("deputy.results", period_id=period_id))


@bp.route("/results/<int:period_id>")
@login_required
def results(period_id):
    _require_deputy()
    period = RegistrationPeriod.query.get_or_404(period_id)
    runs = AllocationRun.query.filter_by(period_id=period_id).order_by(AllocationRun.started_at.desc()).all()

    latest_run = runs[0] if runs else None
    results_list = []
    if latest_run:
        results_list = AllocationResult.query.filter_by(run_id=latest_run.run_id).all()

    courses = Course.query.filter_by(period_id=period_id).all()
    return render_template(
        "results.html", period=period, runs=runs, latest_run=latest_run,
        results=results_list, courses=courses,
    )


@bp.route("/override/<int:application_id>", methods=["POST"])
@login_required
def override(application_id):
    _require_deputy()
    app = Application.query.get_or_404(application_id)
    action = request.form.get("action")  # 'allocate' или 'reject'
    course_id = request.form.get("course_id", type=int) or app.course_id
    reason = request.form.get("reason", "").strip() or "Ручная корректировка замдеканом"

    try:
        manual_override(
            app, course_id, current_user.user_id, reason,
            allocate=(action == "allocate"),
        )
        flash("Результат обновлён вручную.", "success")
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("deputy.results", period_id=app.period_id))
