"""Borda HTTP das trilhas do evento (API-15)."""

import uuid

from flask import Blueprint, jsonify, request

from app.core.permissoes import Acao, exige_acao
from app.core.unidade_de_trabalho import transacao
from app.modules.eventos.repository import TrilhaRepository
from app.modules.eventos.schemas import EdicaoDeTrilha, TrilhaDeEntrada
from app.modules.eventos.services.evento import EventoService
from app.modules.eventos.services.trilha import TrilhaService

trilhas_bp = Blueprint("trilhas", __name__, url_prefix="/api")


def evento_da_trilha(trilha_id: uuid.UUID, **_) -> uuid.UUID | None:
    """O evento dono da trilha, para o RBAC decidir antes de a rota buscar nada.

    Trilha inexistente resolve `None`, que nao concede papel algum: quem nao e
    administrador recebe 403 sem descobrir se aquela trilha existe (API-09 AC5).
    """
    trilha = TrilhaRepository.por_id(trilha_id)
    return None if trilha is None else trilha.evento_id


@trilhas_bp.get("/eventos/<uuid:evento_id>/trilhas")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def listar(evento_id):
    """200 com as trilhas do evento e a contagem derivada (API-15 AC1)."""
    EventoService.exigir_existente(evento_id)

    return jsonify(
        [
            TrilhaService.projetar(trilha).para_json()
            for trilha in TrilhaRepository.do_evento(evento_id)
        ]
    ), 200


@trilhas_bp.post("/eventos/<uuid:evento_id>/trilhas")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def criar(evento_id):
    """201 com a trilha criada, `ativa` e sem submissoes (API-15 AC2, AC3, AC7)."""
    EventoService.exigir_existente(evento_id)
    dados = TrilhaDeEntrada.model_validate(request.get_json(silent=True) or {})

    with transacao():
        trilha = TrilhaService.criar(evento_id, dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = TrilhaService.projetar(trilha).para_json()

    return jsonify(corpo), 201


@trilhas_bp.patch("/trilhas/<uuid:trilha_id>")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_por=evento_da_trilha)
def editar(trilha_id):
    """200 com a trilha e a contagem atualizada (API-15 AC4, AC5, AC6).

    **Estado antes de corpo**: a trilha e buscada antes de o corpo ser validado,
    para um PATCH em trilha inexistente ser 404 ainda que o corpo esteja
    invalido. A leitura acontece fora de `transacao()`, para o 422 nao virar
    excecao dentro do bloco e o `rollback()` nao desfazer escritas anteriores.
    """
    trilha = TrilhaService.exigir_existente(trilha_id)
    dados = EdicaoDeTrilha.model_validate(request.get_json(silent=True) or {})

    with transacao():
        TrilhaService.atualizar(trilha, dados)
        corpo = TrilhaService.projetar(trilha).para_json()

    return jsonify(corpo), 200
