"""Testes de ponta a ponta da identidade — API-07 AC1, AC2 (T19).

Cinco desfechos: sessao valida, sem token, token invalido, token expirado, e as
duas formas de o token sobreviver a conta — desativada e apagada (risco R2).
"""

from datetime import timedelta

from flask_jwt_extended import create_access_token

from app.extensions import bcrypt
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository

LOGIN = "/api/auth/login"
ROTA = "/api/me"
EMAIL = "identidade@exemplo.test"
SENHA = "senha-bem-forte-1"

CAMPOS_DO_USUARIO = {
    "id",
    "nome",
    "email",
    "emailConfirmado",
    "administrador",
    "ativo",
}


def criar_conta() -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=EMAIL,
        senha_hash=bcrypt.generate_password_hash(SENHA).decode("utf-8"),
    )
    usuario.email_confirmado = True
    return usuario


def entrar(cliente) -> str:
    resposta = cliente.post(LOGIN, json={"email": EMAIL, "senha": SENHA})
    return resposta.get_json()["tokenDeAcesso"]


def consultar(cliente, token: str | None = None):
    cabecalhos = {} if token is None else {"Authorization": f"Bearer {token}"}
    return cliente.get(ROTA, headers=cabecalhos)


# AC1 — 200 com o usuario na raiz, nao envolto em `{ user: ... }`.


def test_a_identidade_vem_na_raiz_com_os_seis_campos_do_contrato(cliente, sessao):
    usuario = criar_conta()

    resposta = consultar(cliente, entrar(cliente))

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == CAMPOS_DO_USUARIO
    assert corpo["id"] == str(usuario.id)
    assert corpo["nome"] == "Ada Lovelace"
    assert corpo["email"] == EMAIL
    assert corpo["emailConfirmado"] is True
    assert corpo["administrador"] is False
    assert corpo["ativo"] is True


def test_a_identidade_nao_vem_envolvida_nem_carrega_a_senha(cliente, sessao):
    usuario = criar_conta()

    resposta = consultar(cliente, entrar(cliente))

    corpo = resposta.get_json()
    for envoltorio in ("user", "usuario"):
        assert envoltorio not in corpo
    assert SENHA not in resposta.get_data(as_text=True)
    assert usuario.senha_hash not in resposta.get_data(as_text=True)


# AC2 — 401 `nao_autenticado` sem token, com token invalido e com token expirado.


def test_a_identidade_sem_token_responde_401_nao_autenticado(cliente, sessao):
    resposta = consultar(cliente)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_identidade_com_token_invalido_responde_401_nao_autenticado(
    cliente, sessao
):
    resposta = consultar(cliente, "isto-nao-e-um-jwt")

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_identidade_com_token_expirado_responde_401_nao_autenticado(
    cliente, sessao
):
    usuario = criar_conta()
    expirado = create_access_token(
        identity=str(usuario.id), expires_delta=timedelta(seconds=-1)
    )

    resposta = consultar(cliente, expirado)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


# Edge Case — a conta desativada depois de o token sair perde acesso na hora.


def test_a_identidade_de_conta_desativada_apos_a_emissao_responde_401(
    cliente, sessao
):
    usuario = criar_conta()
    token = entrar(cliente)

    usuario.ativo = False
    sessao.flush()

    resposta = consultar(cliente, token)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


# Risco R2 — token de usuario apagado responde 401, nunca 500.


def test_a_identidade_de_usuario_apagado_responde_401_e_nunca_500(cliente, sessao):
    usuario = criar_conta()
    token = entrar(cliente)

    sessao.delete(usuario)
    sessao.flush()

    resposta = consultar(cliente, token)

    # O codigo antigo chamava `to_dict()` num `None` e devolvia 500 aqui.
    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
