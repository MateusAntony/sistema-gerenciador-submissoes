"""Borda HTTP das participacoes do usuario autenticado."""

from flask import Blueprint, jsonify

from app.core.permissoes import exige_autenticacao, usuario_autenticado
from app.modules.eventos.repository import ParticipacaoRepository
from app.modules.eventos.schemas import ParticipacaoDaApi

participacoes_bp = Blueprint("participacoes", __name__, url_prefix="/api")


@participacoes_bp.get("/me/participacoes")
@exige_autenticacao
def minhas_participacoes():
    """Lista as participacoes ativas; sem nenhuma, lista vazia (API-07 AC5)."""
    participacoes = ParticipacaoRepository.por_usuario(usuario_autenticado().id)

    return jsonify(
        [
            ParticipacaoDaApi(
                evento_id=participacao.evento_id,
                evento_titulo=participacao.evento_titulo,
                identificador_pagina=participacao.identificador_pagina,
                papeis=participacao.papeis,
            ).para_json()
            for participacao in participacoes
        ]
    ), 200
