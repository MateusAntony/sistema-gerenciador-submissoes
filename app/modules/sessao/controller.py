"""Borda HTTP do dominio de sessao: login, renovacao e logout."""

from datetime import timedelta

from flask import Blueprint, Response, current_app, jsonify, request

from app.core.erros import NaoAutenticado, montar_envelope
from app.core.unidade_de_trabalho import transacao
from app.modules.contas.schemas import UsuarioDaApi
from app.modules.sessao.schemas import AcessoRenovado, Login, SessaoAberta
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


def _renovacao_recusada() -> Response:
    """401 `nao_autenticado` com o cookie limpo (API-04 AC2).

    E a unica resposta de erro montada fora do tratador central: o `Set-Cookie`
    que apaga o cookie precisa sair **nesta** resposta, e um tratador de excecao
    nao tem como escrever nela.
    """
    resposta = jsonify(
        montar_envelope(NaoAutenticado.codigo, NaoAutenticado.mensagem)
    )
    resposta.status_code = NaoAutenticado.status
    limpar_cookie_de_renovacao(resposta)
    return resposta


@sessao_bp.post("/auth/refresh")
def renovar():
    apresentado = request.cookies.get(NOME_DO_COOKIE_DE_RENOVACAO)

    # A transacao fecha antes da resposta de erro porque a recusa pode ter
    # revogado a familia inteira por reuso: desfazer isso deixaria o token
    # roubado renovando na proxima tentativa (API-04 AC3).
    with transacao():
        renovado = SessaoService.renovar(apresentado)
        corpo = (
            None
            if renovado is None
            else AcessoRenovado(token_de_acesso=renovado[0]).para_json()
        )

    if renovado is None:
        return _renovacao_recusada()

    resposta = jsonify(corpo)
    definir_cookie_de_renovacao(resposta, renovado[1])
    return resposta, 200


@sessao_bp.post("/auth/logout")
def sair():
    """204 sem corpo, sempre. Sair e idempotente (API-04 AC4, AC5)."""
    with transacao():
        SessaoService.encerrar(request.cookies.get(NOME_DO_COOKIE_DE_RENOVACAO))

    resposta = Response(status=204)
    limpar_cookie_de_renovacao(resposta)
    return resposta
