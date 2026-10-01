import os
from flask import Flask
from extensions import db, login_manager
from config import Config
import models  # noqa: F401 регистрирует модели


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    from auth import bp as auth_bp
    from student import bp as student_bp
    from deputy import bp as deputy_bp
    from admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(deputy_bp)
    app.register_blueprint(admin_bp)

    @app.errorhandler(403)
    def forbidden(e):
        return "У вас нет доступа к этой странице (403).", 403

    return app


app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="127.0.0.1", port=5000)
