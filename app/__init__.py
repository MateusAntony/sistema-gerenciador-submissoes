from flask import Flask
from app.config import Config
from app.extensions import db, bcrypt
from app.controllers.auth_controller import auth_bp, public_bp
from app.controllers.evento_controller import eventos_bp
from app.controllers.submissao_controller import submissoes_bp
from app.controllers.notificacao_controller import notificacoes_bp
from app.controllers.formulario_controller import formularios_bp
from app.controllers.etapas_controller import etapas_bp
from app.controllers.avaliacao_controller import avaliacao_bp
from app.controllers.convite_controller import convites_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicialização de Extensões
    db.init_app(app)
    bcrypt.init_app(app)

    # Registro de Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(eventos_bp)
    app.register_blueprint(submissoes_bp)
    app.register_blueprint(notificacoes_bp)
    app.register_blueprint(formularios_bp)
    app.register_blueprint(etapas_bp)
    app.register_blueprint(avaliacao_bp)
    app.register_blueprint(convites_bp)
    return app