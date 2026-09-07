"""Regras do evento ja criado — leitura, edicao e hierarquia (API-14).

Nada aqui comita: o commit e da unidade de trabalho (AD-019).
"""

import uuid

from app.core.erros import ConflitoDeVersao, ErroDeValidacao, NaoEncontrado
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import EventoRepository
from app.modules.eventos.services.solicitacao import SolicitacaoService

MENSAGEM_DE_EVENTO_INEXISTENTE = "Evento não encontrado."
MENSAGEM_DE_REBUTTAL_SEM_PRAZO = (
    "Informe o prazo de rebuttal quando o rebuttal está habilitado."
)
MENSAGEM_DE_IDENTIFICADOR_DE_PUBLICADO = (
    "O identificador de página não pode ser alterado depois da publicação."
)
MENSAGEM_DE_IDENTIFICADOR_EM_USO = "Este identificador já está em uso."

SITUACAO_PUBLICADO = "publicado"

# Os campos do corpo que nao tem o mesmo nome da coluna. O resto e identico.
COLUNA_POR_CAMPO = {
    "modelo_de_avaliacao": "modelo_avaliacao",
    "maximo_de_rodadas": "maximo_rodadas",
    "nota_de_corte": "nota_corte",
}


class EventoService:
    @staticmethod
    def exigir_existente(evento_id: uuid.UUID) -> Evento:
        """404 `evento_inexistente` (API-14 AC1)."""
        evento = EventoRepository.por_id(evento_id)
        if evento is None:
            raise NaoEncontrado("evento_inexistente", MENSAGEM_DE_EVENTO_INEXISTENTE)
        return evento

    @staticmethod
    def exigir_por_identificador(identificador: str) -> Evento:
        """404 `evento_inexistente`; resolve **sem exigir participacao** (AC2)."""
        evento = EventoRepository.por_identificador(identificador)
        if evento is None:
            raise NaoEncontrado("evento_inexistente", MENSAGEM_DE_EVENTO_INEXISTENTE)
        return evento

    @staticmethod
    def descendentes(evento_id: uuid.UUID) -> list[uuid.UUID]:
        """Toda a arvore abaixo do evento — filhos, netos e alem (AC8).

        A descida e iterativa e guarda os visitados. Um ciclo ja gravado em
        dados legados faria a travessia recursiva ingenua nunca terminar (Edge
        Case da spec): com o conjunto, cada evento e visitado uma vez so, e o
        proprio evento de partida nunca entra no resultado.
        """
        visitados: set[uuid.UUID] = {evento_id}
        encontrados: list[uuid.UUID] = []
        fila = [evento_id]

        while fila:
            for filho_id in EventoRepository.filhos_de(fila.pop(0)):
                if filho_id in visitados:
                    continue
                visitados.add(filho_id)
                encontrados.append(filho_id)
                fila.append(filho_id)

        return encontrados

    @staticmethod
    def exigir_versao(evento: Evento, versao: int) -> None:
        """409 `conflito_de_versao` com o evento atual em `atual` (AC4, D2).

        Fica separada de `atualizar` para o controller poder conferir a versao
        **antes** de abrir a transacao de escrita: o conflito e um estado, e
        estado tem precedencia sobre corpo.
        """
        if evento.versao != versao:
            raise ConflitoDeVersao(
                SolicitacaoService.projetar_evento(evento).para_json()
            )

    @staticmethod
    def atualizar(evento: Evento, dados) -> Evento:
        """Aplica a alteracao parcial e incrementa `versao` em 1 (AC3).

        As tres validacoes que dependem do estado gravado rodam aqui, antes de
        qualquer escrita: o schema sozinho nao as decide porque cada uma compara
        o corpo com o que o evento ja e.
        """
        alteracoes = dados.model_dump(exclude_unset=True)
        alteracoes.pop("versao", None)

        EventoService._validar_rebuttal(evento, alteracoes)
        EventoService._validar_identificador(evento, alteracoes)

        if "evento_pai_id" in alteracoes:
            # AC9 — o pai nao pode ser o proprio evento nem um descendente dele.
            SolicitacaoService.validar_evento_pai(
                alteracoes["evento_pai_id"], evento_proprio=evento.id
            )

        for campo, valor in alteracoes.items():
            setattr(evento, COLUNA_POR_CAMPO.get(campo, campo), valor)

        evento.versao += 1
        return evento

    @staticmethod
    def _validar_rebuttal(evento: Evento, alteracoes: dict) -> None:
        """AC6 — rebuttal ligado sem prazo e 422 em `prazoRebuttalDias`.

        O prazo pode ja estar gravado de uma edicao anterior: o que a AC exige e
        que o resultado da edicao tenha os dois, nao que o corpo os traga juntos.
        """
        habilitado = alteracoes.get(
            "rebuttal_habilitado", evento.rebuttal_habilitado
        )
        prazo = alteracoes.get("prazo_rebuttal_dias", evento.prazo_rebuttal_dias)
        if habilitado and prazo is None:
            raise ErroDeValidacao({"prazoRebuttalDias": MENSAGEM_DE_REBUTTAL_SEM_PRAZO})

    @staticmethod
    def _validar_identificador(evento: Evento, alteracoes: dict) -> None:
        """Edge Case — evento **publicado** nao troca de identificador.

        Links publicos ja divulgados nao podem quebrar. Evento `aprovado`, que
        ainda nao foi divulgado, troca a vontade.
        """
        novo = alteracoes.get("identificador_pagina")
        if novo is None or novo == evento.identificador_pagina:
            return

        if evento.situacao == SITUACAO_PUBLICADO:
            raise ErroDeValidacao(
                {"identificadorPagina": MENSAGEM_DE_IDENTIFICADOR_DE_PUBLICADO}
            )

        if EventoRepository.por_identificador(novo) is not None:
            raise ErroDeValidacao(
                {"identificadorPagina": MENSAGEM_DE_IDENTIFICADOR_EM_USO}
            )
