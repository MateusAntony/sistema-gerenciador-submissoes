"""Borda HTTP das chamadas do evento (API-16)."""

import uuid

from flask import Blueprint, jsonify, request

from app.core.permissoes import Acao, exige_acao
from app.core.unidade_de_trabalho import transacao
from app.modules.eventos.repository import ChamadaRepository
from app.modules.eventos.schemas import (
    ChamadaDeEntrada,
    EdicaoDeChamada,
    ProrrogacaoDeChamada,
)
from app.modules.eventos.services.chamada import ChamadaService
from app.modules.eventos.services.evento import EventoService

chamadas_bp = Blueprint("chamadas", __name__, url_prefix="/api")


def evento_da_chamada(chamada_id: uuid.UUID, **_) -> uuid.UUID | None:
    """O evento dono da chamada, para o RBAC decidir antes de a rota buscar nada.

    Chamada inexistente resolve `None`, que nao concede papel algum: quem nao e
    administrador recebe 403 sem descobrir se aquela chamada existe (API-09 AC5).
    """
    chamada = ChamadaRepository.por_id(chamada_id)
    return None if chamada is None else chamada.evento_id


@chamadas_bp.get("/eventos/<uuid:evento_id>/chamadas")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def listar(evento_id):
    """200 com as chamadas do evento (API-16 AC1)."""
    EventoService.exigir_existente(evento_id)

    return jsonify(
        [
            ChamadaService.projetar(chamada).para_json()
            for chamada in ChamadaRepository.do_evento(evento_id)
        ]
    ), 200


@chamadas_bp.post("/eventos/<uuid:evento_id>/chamadas")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def criar(evento_id):
    """201 com a chamada aberta na versao 1 (API-16 AC2, AC3, AC9)."""
    EventoService.exigir_existente(evento_id)
    dados = ChamadaDeEntrada.model_validate(request.get_json(silent=True) or {})

    with transacao():
        chamada = ChamadaService.criar(evento_id, dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = ChamadaService.projetar(chamada).para_json()

    return jsonify(corpo), 201


@chamadas_bp.patch("/chamadas/<uuid:chamada_id>")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_por=evento_da_chamada)
def editar(chamada_id):
    """200 com a chamada na versao seguinte; 409 se a versao divergir (AC4, AC5).

    A ordem das recusas repete a de `PATCH /eventos/{id}`: 403 no decorador,
    depois 404, depois o corpo, depois o 409 de versao. **Estado antes de
    corpo** — PATCH em chamada inexistente e 404 ainda que o corpo esteja
    invalido. Nada disso roda dentro de `transacao()`: sao leituras, e abortar
    la dentro dispararia o `rollback()` sobre escritas anteriores.
    """
    chamada = ChamadaService.exigir_existente(chamada_id)
    dados = EdicaoDeChamada.model_validate(request.get_json(silent=True) or {})
    ChamadaService.exigir_versao(chamada, dados.versao)

    with transacao():
        ChamadaService.atualizar(chamada, dados)
        corpo = ChamadaService.projetar(chamada).para_json()

    return jsonify(corpo), 200


@chamadas_bp.post("/chamadas/<uuid:chamada_id>/prorrogar")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_por=evento_da_chamada)
def prorrogar(chamada_id):
    """200 com o prazo estendido e a versao seguinte (API-16 AC6, AC7).

    A chamada e buscada antes de o corpo ser validado: prorrogar uma chamada
    inexistente e 404 ainda que `dataLimite` esteja ausente (estado antes de
    corpo).
    """
    chamada = ChamadaService.exigir_existente(chamada_id)
    dados = ProrrogacaoDeChamada.model_validate(request.get_json(silent=True) or {})

    with transacao():
        ChamadaService.prorrogar(chamada, dados.data_limite)
        corpo = ChamadaService.projetar(chamada).para_json()

    return jsonify(corpo), 200


@chamadas_bp.post("/chamadas/<uuid:chamada_id>/encerrar")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_por=evento_da_chamada)
def encerrar(chamada_id):
    """200 com `encerradaManualmente: true` e a versao seguinte (API-16 AC8)."""
    chamada = ChamadaService.exigir_existente(chamada_id)

    with transacao():
        ChamadaService.encerrar(chamada)
        corpo = ChamadaService.projetar(chamada).para_json()

    return jsonify(corpo), 200
