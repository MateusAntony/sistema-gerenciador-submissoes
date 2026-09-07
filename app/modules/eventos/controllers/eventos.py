"""Borda HTTP do evento — leitura, edicao e hierarquia (API-14)."""

from flask import Blueprint, jsonify, request

from app.core.permissoes import Acao, exige_acao, exige_autenticacao
from app.core.unidade_de_trabalho import transacao
from app.modules.eventos.schemas import EdicaoDeEvento
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


@eventos_bp.get("/eventos/<uuid:evento_id>/descendentes")
@exige_autenticacao
def descendentes(evento_id):
    """200 `{ descendentes: [...] }` com toda a arvore abaixo (API-14 AC8)."""
    EventoService.exigir_existente(evento_id)

    return jsonify(
        {
            "descendentes": [
                str(filho_id) for filho_id in EventoService.descendentes(evento_id)
            ]
        }
    ), 200


@eventos_bp.patch("/eventos/<uuid:evento_id>")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def editar(evento_id):
    """200 com o evento na versao seguinte; 409 se a versao divergir (AC3, AC4).

    A ordem das recusas e deliberada: 403 vem do decorador, antes de qualquer
    busca (API-09 AC5); depois 404; depois o 409 de versao; so entao o corpo e
    validado. **Estado antes de corpo** — um PATCH em evento inexistente e 404
    ainda que o corpo esteja invalido.

    Nenhuma dessas checagens roda dentro de `transacao()`: abortar la dentro
    dispararia o `rollback()`, que desfaria escritas anteriores da mesma
    requisicao. Sao leituras, e leituras decidem fora da transacao de escrita.
    """
    evento = EventoService.exigir_existente(evento_id)
    dados = EdicaoDeEvento.model_validate(request.get_json(silent=True) or {})
    EventoService.exigir_versao(evento, dados.versao)

    with transacao():
        EventoService.atualizar(evento, dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = SolicitacaoService.projetar_evento(evento).para_json()

    return jsonify(corpo), 200
