from datetime import datetime

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class Usuario(db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    email_confirmado = db.Column(db.Boolean, default=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    instituicao = db.Column(db.String(200))
    pais = db.Column(db.String(100))
    identificador_orcid = db.Column(db.String(30))
    administrador = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "email": self.email,
            "instituicao": self.instituicao,
            "administrador": self.administrador,
            "ativo": self.ativo
        }
