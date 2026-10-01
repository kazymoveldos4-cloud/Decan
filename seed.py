"""
Одноразовый скрипт: создаёт первого администратора,
чтобы можно было войти и дальше заводить пользователей через веб-интерфейс.

Запуск:
    python seed.py
"""
from werkzeug.security import generate_password_hash
from app import create_app
from extensions import db
from models import User, Role

app = create_app()

with app.app_context():
    admin_role = Role.query.filter_by(role_name="admin").first()
    if not admin_role:
        raise SystemExit(
            "Роль 'admin' не найдена в таблице roles. "
            "Убедись, что базовый SQL-скрипт с ролями уже выполнен."
        )

    email = "admin@university.local"
    if User.query.filter_by(email=email).first():
        print("Администратор уже существует:", email)
    else:
        admin = User(
            full_name="Администратор системы",
            email=email,
            password_hash=generate_password_hash("admin123"),
            role_id=admin_role.role_id,
            is_active_db=True,
        )
        db.session.add(admin)
        db.session.commit()
        print("Создан администратор:")
        print("  email:", email)
        print("  пароль: admin123")
        print("Обязательно смени пароль после первого входа!")
