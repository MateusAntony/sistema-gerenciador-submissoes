"""Models do dominio de contas."""

from datetime import datetime, timezone

from app.extensions import db
from app.modules.colunas import chave_estrangeira, chave_primaria, criado_em, momento


def _agora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = chave_primaria()
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    email_confirmado = db.Column(db.Boolean, default=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    instituicao = db.Column(db.String(200))
    pais = db.Column(db.String(100))
    identificador_orcid = db.Column(db.String(30))
    administrador = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = momento(default=_agora)
    atualizado_em = momento(default=_agora, onupdate=_agora)


class TokenConfirmacaoEmail(db.Model):
    """Token de confirmacao de e-mail — o banco guarda so o SHA-256 (AD-017)."""

    __tablename__ = "tokens_confirmacao_email"

    id = chave_primaria()
    usuario_id = chave_estrangeira(
        "usuarios.id", ondelete="CASCADE", nullable=False
    )
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expira_em = momento(nullable=False)
    usado_em = momento()
    criado_em = criado_em()

    __table_args__ = (
        db.Index(
            "ix_tokens_confirmacao_email_usuario_criado_em",
            "usuario_id",
            db.text("criado_em DESC"),
        ),
    )
