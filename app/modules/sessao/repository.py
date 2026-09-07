"""Acesso a dados do dominio de sessao.

Nenhum metodo daqui comita: o commit e da unidade de trabalho (AD-019).
"""

import uuid

from sqlalchemy import select, update

from app.extensions import db
from app.modules.sessao.models import Sessao


class SessaoRepository:
    @staticmethod
    def por_hash(token_hash: str) -> Sessao | None:
        return db.session.scalars(
            select(Sessao).where(Sessao.token_hash == token_hash)
        ).first()

    @staticmethod
    def criar(
        usuario_id: uuid.UUID,
        familia: uuid.UUID,
        token_hash: str,
        expira_em,
    ) -> Sessao:
        registro = Sessao(
            usuario_id=usuario_id,
            familia=familia,
            token_hash=token_hash,
            expira_em=expira_em,
        )
        db.session.add(registro)
        db.session.flush()
        return registro

    @staticmethod
    def revogar_familia(familia: uuid.UUID, momento) -> None:
        """Derruba toda a familia de uma so vez (API-04 AC3).

        `synchronize_session="fetch"` existe para que os objetos ja carregados na
        sessao enxerguem a revogacao — sem isso o proprio pedido que a disparou
        continuaria lendo `revogada_em is None`.
        """
        db.session.execute(
            update(Sessao)
            .where(Sessao.familia == familia, Sessao.revogada_em.is_(None))
            .values(revogada_em=momento)
            .execution_options(synchronize_session="fetch")
        )
        db.session.flush()
