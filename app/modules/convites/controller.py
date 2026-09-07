"""Borda HTTP dos convites por token — consulta e aceite, sem sessao (BASE-08)."""

from flask import Blueprint, jsonify, request

from app.core.unidade_de_trabalho import transacao
from app.modules.contas.schemas import UsuarioDaApi
from app.modules.convites.schemas import AceiteDeConvite
from app.modules.convites.service import ConviteService
from app.modules.sessao.controller import definir_cookie_de_renovacao
from app.modules.sessao.schemas import SessaoAberta
from app.modules.sessao.service import SessaoService

convites_bp = Blueprint("convites", __name__, url_prefix="/api")


@convites_bp.get("/convites/<token>")
def consultar(token: str):
    """200 **sem exigir sessao**; 404, 410 ou 409 com o contato (API-08 AC1..AC4)."""
    convite = ConviteService.consultar(token)

    return jsonify(ConviteService.projetar(convite).para_json()), 200


@convites_bp.post("/convites/<token>/aceitar")
def aceitar(token: str):
    """Aceita o convite e abre sessao — mesmo corpo do login (API-08 AC7..AC9).

    O corpo e opcional: quem ja tem conta nao envia nome nem senha.
    """
    dados = AceiteDeConvite.model_validate(request.get_json(silent=True) or {})

    with transacao():
        usuario = ConviteService.aceitar(token, dados.nome, dados.senha)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = SessaoAberta(
            token_de_acesso=SessaoService.token_de_acesso(usuario),
            usuario=UsuarioDaApi.de(usuario),
        ).para_json()
        renovacao = SessaoService.emitir(usuario)

    resposta = jsonify(corpo)
    definir_cookie_de_renovacao(resposta, renovacao)
    return resposta, 200
