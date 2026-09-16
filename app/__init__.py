from flask import Flask
from app.config import Config
from app.extensions import db, bcrypt
from app.controllers.auth_controller import auth_bp
from app.controllers.evento_controller import eventos_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicialização de Extensões
    db.init_app(app)
    bcrypt.init_app(app)

    # Registro de Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(eventos_bp)
    return app
