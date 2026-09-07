"""Models do dominio de contas.

O modelo `Usuario` continua em `app/models/user.py` ate a T9, que o move para ca.
"""

from app.extensions import db
from app.modules.colunas import chave_estrangeira, chave_primaria, criado_em, momento


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
