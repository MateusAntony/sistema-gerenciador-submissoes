"""Acesso a dados dos convites.

Nenhum metodo daqui comita: o commit e da unidade de trabalho (AD-019, risco R1).
"""

import uuid
from datetime import datetime

from sqlalchemy import select

from app.extensions import db
from app.modules.convites.models import Convite


class ConviteRepository:
    @staticmethod
    def por_hash(token_hash: str) -> Convite | None:
        """O convite pelo hash do token — o unico jeito de acha-lo (AD-017)."""
        return db.session.scalars(
            select(Convite).where(Convite.token_hash == token_hash)
        ).first()

    @staticmethod
    def pendente_de_participacao(
        evento_id: uuid.UUID, email: str
    ) -> Convite | None:
        """O convite de participacao ainda pendente daquele e-mail no evento.

        Existe para a aprovacao reprocessada nao emitir um segundo convite
        para quem ja tem um esperando resposta (API-13 AC6).
        """
        return db.session.scalars(
            select(Convite).where(
                Convite.evento_id == evento_id,
                Convite.email == email,
                Convite.tipo == "participacao",
                Convite.situacao == "pendente",
            )
        ).first()

    @staticmethod
    def criar(
        *,
        token_hash: str,
        tipo: str,
        email: str,
        evento_id: uuid.UUID | None = None,
        papel: str | None = None,
        submissao_id: uuid.UUID | None = None,
        prazo: datetime | None = None,
        contato_organizacao: str | None = None,
    ) -> Convite:
        convite = Convite(
            token_hash=token_hash,
            tipo=tipo,
            email=email,
            evento_id=evento_id,
            papel=papel,
            submissao_id=submissao_id,
            prazo=prazo,
            contato_organizacao=contato_organizacao,
        )
        db.session.add(convite)
        db.session.flush()
        return convite
