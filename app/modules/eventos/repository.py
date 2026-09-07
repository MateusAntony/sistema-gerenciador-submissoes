"""Acesso a dados do dominio de eventos.

Nenhum metodo daqui comita: o commit e da unidade de trabalho (AD-019, risco R1).

Os papeis saem como os valores crus da coluna `papel`. Quem precisa deles como
`Papel` da matriz converte na borda — o repositorio nao depende do RBAC, e essa
direcao unica e o que evita o ciclo `core.permissoes` <-> `eventos.repository`.
"""

import uuid
from typing import NamedTuple

from sqlalchemy import select

from app.extensions import db
from app.modules.eventos.models import Evento, ParticipacaoEvento


class ParticipacaoAgregada(NamedTuple):
    """Um evento e **todos** os papeis ativos do usuario nele (API-07 AC4)."""

    evento_id: uuid.UUID
    evento_titulo: str
    identificador_pagina: str
    papeis: list[str]


class ParticipacaoRepository:
    @staticmethod
    def por_usuario(usuario_id: uuid.UUID) -> list[ParticipacaoAgregada]:
        """As participacoes **ativas** do usuario, uma entrada por evento.

        Quem tem dois papeis no mesmo evento aparece uma vez so, com os dois
        papeis na lista (API-07 AC4); quem nao participa de nada recebe lista
        vazia, nunca ausencia de resposta (AC5).
        """
        linhas = db.session.execute(
            select(
                Evento.id,
                Evento.titulo,
                Evento.identificador_pagina,
                ParticipacaoEvento.papel,
            )
            .join(ParticipacaoEvento, ParticipacaoEvento.evento_id == Evento.id)
            .where(
                ParticipacaoEvento.usuario_id == usuario_id,
                ParticipacaoEvento.ativo.is_(True),
            )
            .order_by(Evento.titulo, ParticipacaoEvento.papel)
        ).all()

        agregadas: dict[uuid.UUID, ParticipacaoAgregada] = {}
        for evento_id, titulo, identificador, papel in linhas:
            entrada = agregadas.get(evento_id)
            if entrada is None:
                agregadas[evento_id] = ParticipacaoAgregada(
                    evento_id=evento_id,
                    evento_titulo=titulo,
                    identificador_pagina=identificador,
                    papeis=[papel],
                )
            else:
                entrada.papeis.append(papel)

        return list(agregadas.values())

    @staticmethod
    def papeis_no_evento(
        usuario_id: uuid.UUID, evento_id: uuid.UUID
    ) -> list[str]:
        """Os papeis ativos do usuario naquele evento; vazia se nenhum."""
        return list(
            db.session.scalars(
                select(ParticipacaoEvento.papel)
                .where(
                    ParticipacaoEvento.usuario_id == usuario_id,
                    ParticipacaoEvento.evento_id == evento_id,
                    ParticipacaoEvento.ativo.is_(True),
                )
                .order_by(ParticipacaoEvento.papel)
            )
        )

    @staticmethod
    def criar(
        evento_id: uuid.UUID, usuario_id: uuid.UUID, papel: str
    ) -> ParticipacaoEvento:
        participacao = ParticipacaoEvento(
            evento_id=evento_id, usuario_id=usuario_id, papel=papel
        )
        db.session.add(participacao)
        db.session.flush()
        return participacao
