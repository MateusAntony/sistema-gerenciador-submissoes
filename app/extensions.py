from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()
# Emissao e verificacao do JWT de acesso (AD-002, AD-017). A rotacao do token de
# renovacao nao passa por aqui: vive na tabela `sessoes`.
jwt = JWTManager()
