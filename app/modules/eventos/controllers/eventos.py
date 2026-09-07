"""Borda HTTP do evento — leitura, edicao e hierarquia (API-14)."""

from flask import Blueprint, jsonify

from app.core.permissoes import exige_autenticacao
from app.modules.eventos.services.evento import EventoService
from app.modules.eventos.services.solicitacao import SolicitacaoService

eventos_bp = Blueprint("eventos", __name__, url_prefix="/api")


@eventos_bp.get("/eventos/<uuid:evento_id>")
@exige_autenticacao
def obter(evento_id):
    """200 com o evento completo, ou 404 `evento_inexistente` (API-14 AC1)."""
    evento = EventoService.exigir_existente(evento_id)

    return jsonify(SolicitacaoService.projetar_evento(evento).para_json()), 200


@eventos_bp.get("/eventos/por-identificador/<identificador>")
@exige_autenticacao
def obter_por_identificador(identificador):
    """200 sem exigir participacao no evento, ou 404 (API-14 AC2)."""
    evento = EventoService.exigir_por_identificador(identificador)

    return jsonify(SolicitacaoService.projetar_evento(evento).para_json()), 200
