"""
Алгоритм распределения студентов по элективным курсам.

Логика (раундовое распределение по приоритетам с учётом рейтинга):

1. Обрабатываем приоритеты по очереди: 1, 2, 3, ...
2. На каждом раунде берём все заявки с текущим приоритетом от студентов,
   которые ещё НЕ распределены на предыдущих раундах.
3. Группируем заявки по курсу. В каждом курсе сортируем претендентов
   по GPA (убывание). Свободные места забирают студенты с более высоким
   рейтингом.
4. Кто не попал (мест не хватило) — переходит на следующий приоритет
   в следующем раунде (если такая заявка у него есть).
5. После обработки всех приоритетов:
   - у распределённых студентов все остальные заявки помечаются 'cancelled'
   - у нераспределённых студентов все заявки помечаются 'rejected'
"""

from datetime import datetime
from sqlalchemy import func
from extensions import db
from models import (
    Application,
    Course,
    StudentRating,
    AllocationRun,
    AllocationResult,
    RegistrationPeriod,
    log_action,
)


def _latest_gpa(student_id, semester_code):
    rating = (
        StudentRating.query.filter_by(student_id=student_id, semester_code=semester_code)
        .order_by(StudentRating.fetched_at.desc())
        .first()
    )
    return float(rating.gpa) if rating else 0.0


def run_allocation(period_id: int, initiated_by: int) -> AllocationRun:
    period = RegistrationPeriod.query.get_or_404(period_id)

    run = AllocationRun(period_id=period_id, initiated_by=initiated_by, status="running")
    db.session.add(run)
    db.session.flush()  # получаем run_id

    try:
        allocated_student_ids = set()

        for priority in range(1, period.max_priorities + 1):
            apps = (
                Application.query.filter_by(
                    period_id=period_id, priority=priority, status="submitted"
                )
                .all()
            )
            # исключаем тех, кто уже распределён на более раннем приоритете
            apps = [a for a in apps if a.student_id not in allocated_student_ids]
            if not apps:
                continue

            # группируем по курсу
            by_course = {}
            for a in apps:
                by_course.setdefault(a.course_id, []).append(a)

            for course_id, course_apps in by_course.items():
                course = Course.query.get(course_id)
                free_seats = course.free_seats
                if free_seats <= 0:
                    continue

                # сортируем претендентов по GPA убыв.
                ranked = sorted(
                    course_apps,
                    key=lambda a: _latest_gpa(a.student_id, period.semester_code),
                    reverse=True,
                )

                winners = ranked[:free_seats]

                for app in winners:
                    gpa = _latest_gpa(app.student_id, period.semester_code)
                    app.status = "allocated"
                    course.occupied_seats += 1
                    allocated_student_ids.add(app.student_id)

                    result = AllocationResult(
                        run_id=run.run_id,
                        application_id=app.application_id,
                        student_id=app.student_id,
                        course_id=course_id,
                        is_allocated=True,
                        rating_used=gpa,
                    )
                    db.session.add(result)

        # финальный проход: разбираемся с оставшимися заявками
        remaining = Application.query.filter_by(period_id=period_id, status="submitted").all()
        for app in remaining:
            if app.student_id in allocated_student_ids:
                # у этого студента уже есть место по более высокому приоритету
                app.status = "cancelled"
            else:
                app.status = "rejected"
                result = AllocationResult(
                    run_id=run.run_id,
                    application_id=app.application_id,
                    student_id=app.student_id,
                    course_id=app.course_id,
                    is_allocated=False,
                    rating_used=_latest_gpa(app.student_id, period.semester_code),
                )
                db.session.add(result)

        run.status = "completed"
        run.finished_at = datetime.utcnow()
        period.status = "allocated"

        log_action(initiated_by, "run_allocation", "registration_period", period_id,
                    f"run_id={run.run_id}")

        db.session.commit()
        return run

    except Exception:
        db.session.rollback()
        run.status = "failed"
        run.finished_at = datetime.utcnow()
        db.session.add(run)
        db.session.commit()
        raise


def manual_override(result_or_application, course_id: int, admin_id: int, reason: str,
                     allocate: bool = True):
    """
    Ручная корректировка результата замдеканом:
    зачислить/отчислить студента на конкретный курс вручную.
    """
    app = result_or_application
    old_course_id = app.course_id if app.status == "allocated" else None

    if allocate:
        course = Course.query.get_or_404(course_id)
        if course.free_seats <= 0:
            raise ValueError("На выбранном курсе нет свободных мест")
        course.occupied_seats += 1
        app.status = "allocated"
        app.course_id = course_id
    else:
        if old_course_id:
            old_course = Course.query.get(old_course_id)
            if old_course:
                old_course.occupied_seats = max(0, old_course.occupied_seats - 1)
        app.status = "rejected"

    result = AllocationResult(
        run_id=_latest_run_id(app.period_id),
        application_id=app.application_id,
        student_id=app.student_id,
        course_id=app.course_id,
        is_allocated=allocate,
        manual_override=True,
        override_reason=reason,
    )
    db.session.add(result)
    log_action(admin_id, "manual_override", "application", app.application_id, reason)
    db.session.commit()


def _latest_run_id(period_id):
    run = (
        AllocationRun.query.filter_by(period_id=period_id)
        .order_by(AllocationRun.started_at.desc())
        .first()
    )
    return run.run_id if run else None
