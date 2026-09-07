"""Model de convite por token, com `tipo` (D3) e hash do token (AD-017)."""

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db
from app.modules.colunas import chave_estrangeira, chave_primaria, criado_em, momento
from app.modules.enums import convite_situacao_enum, convite_tipo_enum, papel_enum


class Convite(db.Model):
    __tablename__ = "convites"

    id = chave_primaria()
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    tipo = db.Column(convite_tipo_enum, nullable=False)
    email = db.Column(db.String(255), nullable=False)
    evento_id = chave_estrangeira("eventos.id", ondelete="CASCADE")
    papel = db.Column(papel_enum)
    # A submissao pertence a area SUB (AD-018): sem chave estrangeira ainda.
    submissao_id = db.Column(UUID(as_uuid=True))
    prazo = momento()
    contato_organizacao = db.Column(db.String(255))
    situacao = db.Column(
        convite_situacao_enum, nullable=False, server_default="pendente"
    )
    criado_em = criado_em()
    aceito_em = momento()

    __table_args__ = (
        db.CheckConstraint(
            "tipo <> 'avaliacao' OR submissao_id IS NOT NULL",
            name="ck_convites_avaliacao_com_submissao",
        ),
    )
