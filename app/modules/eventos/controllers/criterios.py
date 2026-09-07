"""Borda HTTP dos criterios de avaliacao (API-17)."""

import uuid

from flask import Blueprint, jsonify, request

from app.core.permissoes import Acao, exige_acao
from app.core.unidade_de_trabalho import transacao
from app.modules.eventos.repository import CriterioRepository
from app.modules.eventos.schemas import CriterioDeEntrada, EdicaoDeCriterio
from app.modules.eventos.services.criterio import CriterioService
from app.modules.eventos.services.evento import EventoService

criterios_bp = Blueprint("criterios", __name__, url_prefix="/api")


def evento_do_criterio(criterio_id: uuid.UUID, **_) -> uuid.UUID | None:
    """O evento dono do criterio, para o RBAC decidir antes de a rota buscar nada.

    Criterio inexistente resolve `None`, que nao concede papel algum: quem nao e
    administrador recebe 403 sem descobrir se aquele criterio existe (API-09 AC5).
    """
    criterio = CriterioRepository.por_id(criterio_id)
    return None if criterio is None else criterio.evento_id


@criterios_bp.get("/eventos/<uuid:evento_id>/criterios")
@exige_acao(Acao.DEFINIR_CRITERIOS_E_ETAPAS, evento_de="evento_id")
def listar(evento_id):
    """200 com os criterios e `temNotas` derivado (API-17 AC1)."""
    EventoService.exigir_existente(evento_id)

    return jsonify(
        [
            CriterioService.projetar(criterio).para_json()
            for criterio in CriterioRepository.do_evento(evento_id)
        ]
    ), 200


@criterios_bp.post("/eventos/<uuid:evento_id>/criterios")
@exige_acao(Acao.DEFINIR_CRITERIOS_E_ETAPAS, evento_de="evento_id")
def criar(evento_id):
    """201 com o criterio ativo e sem notas (API-17 AC2..AC4, AC8)."""
    EventoService.exigir_existente(evento_id)
    dados = CriterioDeEntrada.model_validate(request.get_json(silent=True) or {})

    with transacao():
        criterio = CriterioService.criar(evento_id, dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = CriterioService.projetar(criterio).para_json()

    return jsonify(corpo), 201


@criterios_bp.patch("/criterios/<uuid:criterio_id>")
@exige_acao(Acao.DEFINIR_CRITERIOS_E_ETAPAS, evento_por=evento_do_criterio)
def editar(criterio_id):
    """200 com o criterio alterado (API-17 AC3, AC4, AC7).

    **Estado antes de corpo**: o criterio e buscado antes de o corpo ser
    validado, para um PATCH em criterio inexistente ser 404 ainda que o corpo
    esteja invalido. A leitura fica fora de `transacao()`, para o 422 nao virar
    excecao dentro do bloco e o `rollback()` nao desfazer escritas anteriores.
    """
    criterio = CriterioService.exigir_existente(criterio_id)
    dados = EdicaoDeCriterio.model_validate(request.get_json(silent=True) or {})

    with transacao():
        CriterioService.atualizar(criterio, dados)
        corpo = CriterioService.projetar(criterio).para_json()

    return jsonify(corpo), 200
