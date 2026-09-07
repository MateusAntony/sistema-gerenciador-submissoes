"""Rotas sinteticas para exercitar `@exige_acao` pelo cliente HTTP (T23).

As rotas reais de gestao chegam da Fase 5 em diante. A guarda, porem, precisa ser
verificada agora e **pela borda HTTP** — o que se afirma dela sao codigos de
status (401, 403, 404), e um teste que chamasse a funcao decorada direto nao
provaria nenhum deles.

Elas ficam sob `/api/_teste` e sao registradas so pela suite.
"""

import uuid

from flask import Blueprint, jsonify

from app.core.erros import NaoEncontrado
from app.core.permissoes import Acao, exige_acao, usuario_autenticado
from app.extensions import db
from app.modules.eventos.models import Evento

guarda_bp = Blueprint("guarda_de_teste", __name__, url_prefix="/api/_teste")


@guarda_bp.get("/eventos/<uuid:evento_id>/gestao")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def gerir_evento(evento_id: uuid.UUID):
    """Rota de gestao de evento: exige `configurar_evento` naquele evento."""
    return jsonify(
        {"eventoId": str(evento_id), "usuario": str(usuario_autenticado().id)}
    ), 200


@guarda_bp.get("/admin/contas")
@exige_acao(Acao.GERENCIAR_CONTAS)
def gerir_contas():
    """Rota `/admin/*`: acao global, so a coluna do administrador a concede."""
    return jsonify({"usuario": str(usuario_autenticado().id)}), 200


@guarda_bp.get("/eventos/<uuid:evento_id>/recurso")
@exige_acao(Acao.CONFIGURAR_EVENTO, evento_de="evento_id")
def obter_recurso(evento_id: uuid.UUID):
    """Rota que **buscaria** o recurso: 404 so para quem passou pela guarda."""
    evento = db.session.get(Evento, evento_id)
    if evento is None:
        raise NaoEncontrado("evento_inexistente")
    return jsonify({"eventoId": str(evento.id)}), 200
