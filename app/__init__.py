from flask import Flask

from app.config import Config
from app.core.correlacao import registrar_correlacao
from app.core.erros import registrar_tratadores
from app.extensions import bcrypt, db, jwt, migrate
from app.modules.contas.controller import contas_bp
from app.modules.convites.controller import convites_bp
from app.modules.emails.backends import CHAVE_DO_BACKEND, criar_backend
from app.modules.eventos.controllers.chamadas import chamadas_bp
from app.modules.eventos.controllers.criterios import criterios_bp
from app.modules.eventos.controllers.eventos import eventos_bp
from app.modules.eventos.controllers.participacoes import participacoes_bp
from app.modules.eventos.controllers.solicitacoes import solicitacoes_bp
from app.modules.eventos.controllers.trilhas import trilhas_bp
from app.modules.sessao.controller import sessao_bp


def create_app(configuracao: Config | None = None):
    app = Flask(__name__)
    app.config.from_object(configuracao or Config())

    # Inicialização de Extensões
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)

    # Registra todos os models no metadata antes de o Alembic ler o schema.
    from app import modules  # noqa: F401

    migrate.init_app(app, db)

    # O backend de e-mail e escolhido no boot (AD-010); configuracao incompleta
    # ja derrubou a aplicacao em `Config`.
    app.extensions[CHAVE_DO_BACKEND] = criar_backend(app.config)

    # Toda resposta leva correlacao; toda resposta de erro sai pelo envelope unico.
    registrar_correlacao(app)
    registrar_tratadores(app)

    app.register_blueprint(contas_bp)
    app.register_blueprint(sessao_bp)
    app.register_blueprint(participacoes_bp)
    app.register_blueprint(convites_bp)
    app.register_blueprint(solicitacoes_bp)
    app.register_blueprint(eventos_bp)
    app.register_blueprint(trilhas_bp)
    app.register_blueprint(chamadas_bp)
    app.register_blueprint(criterios_bp)

    return app
