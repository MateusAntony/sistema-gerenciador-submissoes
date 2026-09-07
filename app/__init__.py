from flask import Flask

from app.config import Config
from app.controllers.auth_controller import auth_bp
from app.core.erros import registrar_tratadores
from app.extensions import bcrypt, db, migrate


def create_app(configuracao: Config | None = None):
    app = Flask(__name__)
    app.config.from_object(configuracao or Config())

    # Inicialização de Extensões
    db.init_app(app)
    bcrypt.init_app(app)

    # Registra todos os models no metadata antes de o Alembic ler o schema.
    from app import modules  # noqa: F401

    migrate.init_app(app, db)

    # Toda resposta de erro sai pelo envelope unico (API-01 AC1).
    registrar_tratadores(app)

    # Registro de Blueprints
    app.register_blueprint(auth_bp)

    return app
