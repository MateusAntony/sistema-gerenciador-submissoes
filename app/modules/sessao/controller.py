"""Borda HTTP do dominio de sessao: login, renovacao e logout."""

from datetime import timedelta

from flask import Blueprint, Response, current_app, jsonify, request

from app.core.unidade_de_trabalho import transacao
from app.modules.contas.schemas import UsuarioDaApi
from app.modules.sessao.schemas import Login, SessaoAberta
from app.modules.sessao.service import (
    VALIDADE_DA_RENOVACAO_EM_DIAS,
    SessaoService,
)

sessao_bp = Blueprint("sessao", __name__, url_prefix="/api")

NOME_DO_COOKIE_DE_RENOVACAO = "renovacao"
# O cookie so viaja para as rotas que o usam; nenhuma outra requisicao o carrega.
CAMINHO_DO_COOKIE_DE_RENOVACAO = "/api/auth"


def _atributos_do_cookie() -> dict:
    return {
        "httponly": True,
        "samesite": "Lax",
        "path": CAMINHO_DO_COOKIE_DE_RENOVACAO,
        # `Secure` sai da configuracao, que o deriva de `APP_ENV` (risco R4).
        "secure": current_app.config["COOKIE_SEGURO"],
    }


def definir_cookie_de_renovacao(resposta: Response, token: str) -> None:
    resposta.set_cookie(
        NOME_DO_COOKIE_DE_RENOVACAO,
        token,
        max_age=int(
            timedelta(days=VALIDADE_DA_RENOVACAO_EM_DIAS).total_seconds()
        ),
        **_atributos_do_cookie(),
    )


def limpar_cookie_de_renovacao(resposta: Response) -> None:
    resposta.delete_cookie(
        NOME_DO_COOKIE_DE_RENOVACAO, **_atributos_do_cookie()
    )


@sessao_bp.post("/auth/login")
def entrar():
    dados = Login.model_validate(request.get_json())

    with transacao():
        usuario, falha = SessaoService.autenticar(dados.email, dados.senha)
        if usuario is not None:
            corpo = SessaoAberta(
                token_de_acesso=SessaoService.token_de_acesso(usuario),
                usuario=UsuarioDaApi.de(usuario),
            ).para_json()
            renovacao = SessaoService.emitir(usuario)

    # A falha e levantada **depois** do commit: o que a autenticacao registrou
    # sobre a tentativa precisa sobreviver a resposta de erro.
    if falha is not None:
        raise falha

    resposta = jsonify(corpo)
    definir_cookie_de_renovacao(resposta, renovacao)
    return resposta, 200
