from flask import Flask

from app.config import Config
from app.core.correlacao import registrar_correlacao
from app.core.erros import registrar_tratadores
from app.extensions import bcrypt, db, migrate
from app.modules.emails.backends import CHAVE_DO_BACKEND, criar_backend


def create_app(configuracao: Config | None = None):
    app = Flask(__name__)
    app.config.from_object(configuracao or Config())

    # Inicialização de Extensões
    db.init_app(app)
    bcrypt.init_app(app)

    # Registra todos os models no metadata antes de o Alembic ler o schema.
    from app import modules  # noqa: F401

    migrate.init_app(app, db)

    # O backend de e-mail e escolhido no boot (AD-010); configuracao incompleta
    # ja derrubou a aplicacao em `Config`.
    app.extensions[CHAVE_DO_BACKEND] = criar_backend(app.config)

    # Toda resposta leva correlacao; toda resposta de erro sai pelo envelope unico.
    registrar_correlacao(app)
    registrar_tratadores(app)

    return app
