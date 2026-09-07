"""Acesso a dados do dominio de eventos.

Nenhum metodo daqui comita: o commit e da unidade de trabalho (AD-019, risco R1).

Os papeis saem como os valores crus da coluna `papel`. Quem precisa deles como
`Papel` da matriz converte na borda — o repositorio nao depende do RBAC, e essa
direcao unica e o que evita o ciclo `core.permissoes` <-> `eventos.repository`.
"""

import uuid
from typing import NamedTuple

from sqlalchemy import delete, select

from app.extensions import db
from app.modules.eventos.models import (
    Evento,
    ParticipacaoEvento,
    SolicitacaoChairInicial,
    SolicitacaoEvento,
)


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


class SolicitacaoRepository:
    @staticmethod
    def por_id(solicitacao_id: uuid.UUID) -> SolicitacaoEvento | None:
        return db.session.get(SolicitacaoEvento, solicitacao_id)

    @staticmethod
    def por_id_bloqueada(solicitacao_id: uuid.UUID) -> SolicitacaoEvento | None:
        """A solicitacao com a **linha travada** ate o fim da transacao.

        E o que serializa duas decisoes simultaneas: a segunda so le a linha
        depois de a primeira comitar, e ai ja a ve decidida (Edge Case da spec).
        """
        return db.session.scalars(
            select(SolicitacaoEvento)
            .where(SolicitacaoEvento.id == solicitacao_id)
            .with_for_update()
        ).first()

    @staticmethod
    def por_identificador(identificador: str) -> SolicitacaoEvento | None:
        return db.session.scalars(
            select(SolicitacaoEvento).where(
                SolicitacaoEvento.identificador_pagina == identificador
            )
        ).first()

    @staticmethod
    def por_solicitante(solicitante_id: uuid.UUID) -> list[SolicitacaoEvento]:
        """As solicitacoes do proprio usuario, da mais antiga para a mais nova."""
        return list(
            db.session.scalars(
                select(SolicitacaoEvento)
                .where(SolicitacaoEvento.solicitante_id == solicitante_id)
                .order_by(SolicitacaoEvento.criado_em)
            )
        )

    @staticmethod
    def listar(situacao: str | None = None) -> list[SolicitacaoEvento]:
        """A fila do administrador, por `criado_em` **crescente** (API-12 AC1).

        Sem `situacao`, devolve todas; com ela, so as daquela situacao (AC2).
        """
        consulta = select(SolicitacaoEvento).order_by(SolicitacaoEvento.criado_em)
        if situacao is not None:
            consulta = consulta.where(SolicitacaoEvento.situacao == situacao)
        return list(db.session.scalars(consulta))

    @staticmethod
    def criar(**campos) -> SolicitacaoEvento:
        solicitacao = SolicitacaoEvento(**campos)
        db.session.add(solicitacao)
        db.session.flush()
        return solicitacao

    @staticmethod
    def chairs_iniciais(solicitacao_id: uuid.UUID) -> list[str]:
        """Os e-mails dos chairs iniciais, em ordem estavel."""
        return list(
            db.session.scalars(
                select(SolicitacaoChairInicial.email)
                .where(SolicitacaoChairInicial.solicitacao_id == solicitacao_id)
                .order_by(SolicitacaoChairInicial.email)
            )
        )

    @staticmethod
    def definir_chairs_iniciais(
        solicitacao_id: uuid.UUID, emails: list[str]
    ) -> None:
        """Substitui a lista de chairs iniciais, sem repetir e-mail (API-13 AC6)."""
        db.session.execute(
            delete(SolicitacaoChairInicial).where(
                SolicitacaoChairInicial.solicitacao_id == solicitacao_id
            )
        )
        for email in dict.fromkeys(emails):
            db.session.add(
                SolicitacaoChairInicial(solicitacao_id=solicitacao_id, email=email)
            )
        db.session.flush()


class EventoRepository:
    @staticmethod
    def por_id(evento_id: uuid.UUID) -> Evento | None:
        return db.session.get(Evento, evento_id)

    @staticmethod
    def por_identificador(identificador: str) -> Evento | None:
        return db.session.scalars(
            select(Evento).where(Evento.identificador_pagina == identificador)
        ).first()

    @staticmethod
    def por_solicitacao(solicitacao_id: uuid.UUID) -> Evento | None:
        return db.session.scalars(
            select(Evento).where(Evento.solicitacao_id == solicitacao_id)
        ).first()

    @staticmethod
    def filhos_de(evento_id: uuid.UUID) -> list[uuid.UUID]:
        """Os ids dos eventos que apontam para este como pai."""
        return list(
            db.session.scalars(
                select(Evento.id).where(Evento.evento_pai_id == evento_id)
            )
        )

    @staticmethod
    def criar(**campos) -> Evento:
        evento = Evento(**campos)
        db.session.add(evento)
        db.session.flush()
        return evento
