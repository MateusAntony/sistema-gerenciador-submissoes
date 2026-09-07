"""Testes de ponta a ponta do logout — API-04 AC4, AC5 (T18)."""

import hashlib

from sqlalchemy import select

from app.extensions import bcrypt
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.sessao.models import Sessao

LOGIN = "/api/auth/login"
REFRESH = "/api/auth/refresh"
ROTA = "/api/auth/logout"
EMAIL = "logout@exemplo.test"
SENHA = "senha-bem-forte-1"
COOKIE = "renovacao"


def criar_conta() -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=EMAIL,
        senha_hash=bcrypt.generate_password_hash(SENHA).decode("utf-8"),
    )
    usuario.email_confirmado = True
    return usuario


def cabecalho_do_cookie(resposta) -> str | None:
    for cabecalho in resposta.headers.getlist("Set-Cookie"):
        if cabecalho.startswith(f"{COOKIE}="):
            return cabecalho
    return None


def valor_do_cookie(resposta) -> str:
    return cabecalho_do_cookie(resposta).split(";")[0].removeprefix(f"{COOKIE}=")


def entrar(cliente) -> str:
    return valor_do_cookie(cliente.post(LOGIN, json={"email": EMAIL, "senha": SENHA}))


def apresentar(cliente, rota: str, token: str):
    cliente.set_cookie(COOKIE, token, path="/api/auth")
    return cliente.post(rota)


def sessao_do_token(sessao, token: str) -> Sessao | None:
    return sessao.scalars(
        select(Sessao).where(
            Sessao.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
        )
    ).first()


# AC4 — 204 sem corpo, token invalidado e cookie limpo.


def test_o_logout_responde_204_sem_corpo(cliente, sessao):
    criar_conta()
    token = entrar(cliente)

    resposta = apresentar(cliente, ROTA, token)

    assert resposta.status_code == 204
    assert resposta.get_data() == b""


def test_o_logout_invalida_o_token_de_renovacao(cliente, sessao):
    criar_conta()
    token = entrar(cliente)

    apresentar(cliente, ROTA, token)

    assert sessao_do_token(sessao, token).revogada_em is not None


def test_o_logout_limpa_o_cookie_de_renovacao(cliente, sessao):
    criar_conta()
    token = entrar(cliente)

    cabecalho = cabecalho_do_cookie(apresentar(cliente, ROTA, token))

    assert cabecalho is not None
    assert f"{COOKIE}=;" in cabecalho
    assert "Path=/api/auth" in cabecalho
    assert "Expires=Thu, 01 Jan 1970" in cabecalho


# AC5 — sair e idempotente: sem sessao valida tambem responde 204.


def test_o_logout_sem_cookie_tambem_responde_204(cliente, sessao):
    resposta = cliente.post(ROTA)

    assert resposta.status_code == 204
    assert resposta.get_data() == b""


def test_o_logout_repetido_com_o_mesmo_cookie_responde_204_de_novo(cliente, sessao):
    criar_conta()
    token = entrar(cliente)
    apresentar(cliente, ROTA, token)

    resposta = apresentar(cliente, ROTA, token)

    assert resposta.status_code == 204
    assert resposta.get_data() == b""


def test_o_logout_com_cookie_desconhecido_responde_204(cliente, sessao):
    resposta = apresentar(cliente, ROTA, "token-que-nunca-existiu")

    assert resposta.status_code == 204


# Apos o logout, a renovacao com o cookie antigo devolve 401.


def test_a_renovacao_com_o_cookie_antigo_falha_depois_do_logout(cliente, sessao):
    criar_conta()
    token = entrar(cliente)
    apresentar(cliente, ROTA, token)

    resposta = apresentar(cliente, REFRESH, token)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
