from datetime import datetime
from flask_login import UserMixin
from extensions import db


class Role(db.Model):
    __tablename__ = "roles"
    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)


class Faculty(db.Model):
    __tablename__ = "faculties"
    faculty_id = db.Column(db.Integer, primary_key=True)
    faculty_name = db.Column(db.String(200), nullable=False)
    faculty_code = db.Column(db.String(20), unique=True, nullable=False)


class User(db.Model, UserMixin):
    __tablename__ = "users"
    user_id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.role_id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculties.faculty_id"), nullable=True)

    student_group = db.Column(db.String(30))
    is_active_db = db.Column("is_active", db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    role = db.relationship("Role")
    faculty = db.relationship("Faculty")

    # Flask-Login требует get_id -> строка
    def get_id(self):
        return str(self.user_id)

    @property
    def is_active(self):
        return bool(self.is_active_db)

    @property
    def role_name(self):
        return self.role.role_name if self.role else None


class StudentRating(db.Model):
    __tablename__ = "student_ratings"
    rating_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    semester_code = db.Column(db.String(20), nullable=False)
    gpa = db.Column(db.Numeric(4, 2), nullable=False)
    source_system = db.Column(db.String(50), default="ИСУ")
    fetched_at = db.Column(db.DateTime, default=datetime.utcnow)


class RegistrationPeriod(db.Model):
    __tablename__ = "registration_periods"
    period_id = db.Column(db.Integer, primary_key=True)
    semester_code = db.Column(db.String(20), unique=True, nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="planned")  # planned, open, closed, allocated
    max_priorities = db.Column(db.SmallInteger, default=5)

    courses = db.relationship("Course", backref="period")


class Course(db.Model):
    __tablename__ = "courses"
    course_id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey("registration_periods.period_id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("faculties.faculty_id"), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    teacher_name = db.Column(db.String(200))
    total_seats = db.Column(db.Integer, nullable=False)
    occupied_seats = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="active")  # active, archived

    faculty = db.relationship("Faculty")

    @property
    def free_seats(self):
        return self.total_seats - self.occupied_seats


class Application(db.Model):
    __tablename__ = "applications"
    application_id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    period_id = db.Column(db.Integer, db.ForeignKey("registration_periods.period_id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.course_id"), nullable=False)
    priority = db.Column(db.SmallInteger, nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="submitted")
    # submitted, allocated, rejected, cancelled

    student = db.relationship("User")
    course = db.relationship("Course")
    period = db.relationship("RegistrationPeriod")


class AllocationRun(db.Model):
    __tablename__ = "allocation_runs"
    run_id = db.Column(db.Integer, primary_key=True)
    period_id = db.Column(db.Integer, db.ForeignKey("registration_periods.period_id"), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    initiated_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    status = db.Column(db.String(20), default="running")  # running, completed, failed


class AllocationResult(db.Model):
    __tablename__ = "allocation_results"
    result_id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("allocation_runs.run_id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.application_id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.course_id"), nullable=False)
    is_allocated = db.Column(db.Boolean, nullable=False)
    rating_used = db.Column(db.Numeric(4, 2), nullable=True)
    decided_at = db.Column(db.DateTime, default=datetime.utcnow)
    manual_override = db.Column(db.Boolean, default=False)
    override_reason = db.Column(db.Text, nullable=True)

    student = db.relationship("User")
    course = db.relationship("Course")
    application = db.relationship("Application")


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    log_id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def log_action(user_id, action, entity_type, entity_id=None, details=None):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.session.add(entry)
