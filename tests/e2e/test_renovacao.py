"""Testes de ponta a ponta da renovacao — API-04 AC1, AC2, AC3 (T17)."""

import hashlib
from datetime import timedelta

from flask_jwt_extended import decode_token
from sqlalchemy import select

from app.extensions import bcrypt
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import agora
from app.modules.sessao.models import Sessao

LOGIN = "/api/auth/login"
ROTA = "/api/auth/refresh"
EMAIL = "renovacao@exemplo.test"
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


def apresentar(cliente, token: str):
    """Renova apresentando exatamente este token, sem depender do pote do cliente."""
    cliente.set_cookie(COOKIE, token, path="/api/auth")
    return cliente.post(ROTA)


def entrar(cliente) -> str:
    return valor_do_cookie(cliente.post(LOGIN, json={"email": EMAIL, "senha": SENHA}))


def sessao_do_token(sessao, token: str) -> Sessao | None:
    return sessao.scalars(
        select(Sessao).where(
            Sessao.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
        )
    ).first()


# AC1 — 200 `{ tokenDeAcesso }` e cookie novo, invalidando o anterior.


def test_renovacao_valida_responde_200_com_apenas_o_token_de_acesso(cliente, sessao):
    usuario = criar_conta()
    primeiro = entrar(cliente)

    resposta = apresentar(cliente, primeiro)

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == {"tokenDeAcesso"}
    assert decode_token(corpo["tokenDeAcesso"])["sub"] == str(usuario.id)


def test_a_renovacao_emite_um_cookie_novo_e_diferente_do_anterior(cliente, sessao):
    criar_conta()
    primeiro = entrar(cliente)

    resposta = apresentar(cliente, primeiro)

    segundo = valor_do_cookie(resposta)
    assert segundo != primeiro
    assert "HttpOnly" in cabecalho_do_cookie(resposta)
    assert "Path=/api/auth" in cabecalho_do_cookie(resposta)
    assert sessao_do_token(sessao, segundo) is not None


def test_o_cookie_anterior_deixa_de_renovar_depois_da_rotacao(cliente, sessao):
    criar_conta()
    primeiro = entrar(cliente)
    apresentar(cliente, primeiro)

    assert apresentar(cliente, primeiro).status_code == 401
    # "Invalidando o anterior" e um estado gravado, nao so um 401: a linha do
    # token trocado fica marcada como rotacionada.
    assert sessao_do_token(sessao, primeiro).rotacionado_em is not None


# AC2 — 401 `nao_autenticado` e cookie limpo quando ausente, expirado ou ja
# rotacionado.


def test_renovacao_sem_cookie_responde_401_nao_autenticado(cliente, sessao):
    resposta = cliente.post(ROTA)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_renovacao_com_cookie_expirado_responde_401_nao_autenticado(cliente, sessao):
    criar_conta()
    token = entrar(cliente)
    sessao_do_token(sessao, token).expira_em = agora() - timedelta(seconds=1)
    sessao.flush()

    resposta = apresentar(cliente, token)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_renovacao_com_cookie_ja_rotacionado_responde_401_nao_autenticado(
    cliente, sessao
):
    criar_conta()
    primeiro = entrar(cliente)
    apresentar(cliente, primeiro)

    resposta = apresentar(cliente, primeiro)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_recusa_de_renovacao_limpa_o_cookie(cliente, sessao):
    resposta = cliente.post(ROTA)

    cabecalho = cabecalho_do_cookie(resposta)
    assert cabecalho is not None
    assert f"{COOKIE}=;" in cabecalho
    assert "Path=/api/auth" in cabecalho
    assert "Expires=Thu, 01 Jan 1970" in cabecalho


# AC3 — reapresentar cookie ja rotacionado invalida a familia: a renovacao
# **seguinte** com o token corrente tambem falha.


def test_reapresentar_cookie_rotacionado_derruba_a_familia_inteira(cliente, sessao):
    criar_conta()
    primeiro = entrar(cliente)
    segundo = valor_do_cookie(apresentar(cliente, primeiro))
    terceiro = valor_do_cookie(apresentar(cliente, segundo))
    corrente = valor_do_cookie(apresentar(cliente, terceiro))

    # O token roubado volta depois de o dono legitimo ja ter rotacionado.
    assert apresentar(cliente, primeiro).status_code == 401

    # Invalidar so o token reapresentado nao satisfaz a AC3: quem esta com a
    # copia continuaria dentro pela cadeia corrente.
    assert apresentar(cliente, corrente).status_code == 401
    familia = sessao.scalars(select(Sessao)).all()
    assert len(familia) == 4
    assert [linha.revogada_em is not None for linha in familia] == [True] * 4


def test_a_revogacao_por_reuso_sobrevive_a_resposta_de_erro(cliente, sessao):
    # A recusa e uma resposta de erro; se a transacao que a carrega fosse
    # desfeita, a familia voltaria viva e o reuso nao teria consequencia.
    criar_conta()
    primeiro = entrar(cliente)
    corrente = valor_do_cookie(apresentar(cliente, primeiro))

    apresentar(cliente, primeiro)

    assert sessao_do_token(sessao, corrente).revogada_em is not None
