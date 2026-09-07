"""Borda HTTP das solicitacoes de evento (API-11, API-12)."""

from flask import Blueprint, jsonify, request

from app.core.permissoes import exige_autenticacao, usuario_autenticado
from app.core.unidade_de_trabalho import transacao
from app.modules.eventos.schemas import SolicitacaoDeEntrada
from app.modules.eventos.services.solicitacao import SolicitacaoService

solicitacoes_bp = Blueprint("solicitacoes", __name__, url_prefix="/api")


@solicitacoes_bp.post("/solicitacoes-evento")
@exige_autenticacao
def criar():
    """201 com a solicitacao completa, `pendente` e `versao: 1` (API-11 AC1)."""
    dados = SolicitacaoDeEntrada.model_validate(request.get_json(silent=True) or {})

    with transacao():
        solicitacao = SolicitacaoService.criar(usuario_autenticado().id, dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = SolicitacaoService.projetar(solicitacao).para_json()

    return jsonify(corpo), 201
