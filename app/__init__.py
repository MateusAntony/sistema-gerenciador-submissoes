from flask import Flask

from app.config import Config
from app.controllers.auth_controller import auth_bp
from app.extensions import bcrypt, db, migrate


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicialização de Extensões
    db.init_app(app)
    bcrypt.init_app(app)

    # Registra todos os models no metadata antes de o Alembic ler o schema.
    from app import modules  # noqa: F401

    migrate.init_app(app, db)

    # Registro de Blueprints
    app.register_blueprint(auth_bp)

    return app
