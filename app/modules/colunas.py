"""Colunas comuns a todos os models (AD-004: toda PK e UUID gerado pelo banco)."""

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


def chave_primaria() -> db.Column:
    return db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=db.text("uuid_generate_v4()"),
    )


def chave_estrangeira(alvo: str, *, nullable: bool = True, **kwargs) -> db.Column:
    return db.Column(
        UUID(as_uuid=True), db.ForeignKey(alvo, **kwargs), nullable=nullable
    )


def momento(**kwargs) -> db.Column:
    return db.Column(db.DateTime(timezone=True), **kwargs)


def criado_em() -> db.Column:
    return db.Column(
        db.DateTime(timezone=True), nullable=False, server_default=db.func.now()
    )
