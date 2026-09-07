"""Models do dominio de sessao: renovacao rotacionada e tentativas de login."""

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.modules.colunas import chave_estrangeira, chave_primaria, criado_em, momento


class Sessao(db.Model):
    """Token de renovacao. Do valor cru o banco guarda so o SHA-256 (AD-017)."""

    __tablename__ = "sessoes"

    id = chave_primaria()
    usuario_id = chave_estrangeira(
        "usuarios.id", ondelete="CASCADE", nullable=False
    )
    familia = db.Column(UUID(as_uuid=True), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expira_em = momento(nullable=False)
    rotacionado_em = momento()
    revogada_em = momento()
    criado_em = criado_em()

    __table_args__ = (db.Index("ix_sessoes_familia", "familia"),)


class TentativaLogin(db.Model):
    """Uma linha por tentativa, para a janela de 15 minutos de API-20."""

    __tablename__ = "tentativas_login"

    id = chave_primaria()
    email = db.Column(db.String(255), nullable=False)
    sucesso = db.Column(db.Boolean, nullable=False)
    ocorrido_em = db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )

    __table_args__ = (
        db.Index(
            "ix_tentativas_login_email_ocorrido_em",
            "email",
            db.text("ocorrido_em DESC"),
        ),
    )
