"""Testes de ponta a ponta da confirmacao de e-mail — API-06 AC1..AC4 (T13)."""

from datetime import timedelta

from sqlalchemy import select

from app.modules.contas.models import TokenConfirmacaoEmail, Usuario
from app.modules.contas.service import agora
from app.modules.emails.models import EmailEnviado

ROTA = "/api/auth/confirmar-email"
EMAIL = "confirmacao@exemplo.test"

CADASTRO = {
    "nome": "Ada Lovelace",
    "email": EMAIL,
    "senha": "senha-bem-forte-1",
    "instituicao": "UFPI",
    "pais": "Brasil",
}


def cadastrar_e_obter_token(cliente, sessao, aplicacao) -> str:
    """Cadastra e recolhe o token cru do jeito que a pessoa o receberia: do e-mail."""
    cliente.post("/api/usuarios", json=CADASTRO)
    corpo = sessao.scalars(
        select(EmailEnviado.corpo).where(EmailEnviado.destinatario == EMAIL)
    ).one()
    prefixo = f"{aplicacao.config['URL_DO_FRONT']}/confirmar-email?token="
    return corpo.split(prefixo, 1)[1].split()[0]


def usuario(sessao) -> Usuario:
    return sessao.scalars(select(Usuario).where(Usuario.email == EMAIL)).one()


def token_gravado(sessao) -> TokenConfirmacaoEmail:
    return sessao.scalars(select(TokenConfirmacaoEmail)).one()


# AC1 — token pendente e nao expirado confirma a conta.


def test_token_valido_responde_200_com_o_email(cliente, sessao, aplicacao):
    token = cadastrar_e_obter_token(cliente, sessao, aplicacao)

    resposta = cliente.post(ROTA, json={"token": token})

    assert resposta.status_code == 200
    assert resposta.get_json() == {"email": EMAIL}


def test_token_valido_marca_a_conta_como_confirmada(cliente, sessao, aplicacao):
    token = cadastrar_e_obter_token(cliente, sessao, aplicacao)

    cliente.post(ROTA, json={"token": token})

    assert usuario(sessao).email_confirmado is True


def test_token_valido_marca_o_token_como_usado(cliente, sessao, aplicacao):
    token = cadastrar_e_obter_token(cliente, sessao, aplicacao)

    cliente.post(ROTA, json={"token": token})

    assert token_gravado(sessao).usado_em is not None


# AC2 — token inexistente responde 404 `token_invalido`.


def test_token_inexistente_responde_404_token_invalido(cliente, sessao):
    resposta = cliente.post(ROTA, json={"token": "token-que-nunca-foi-emitido"})

    assert resposta.status_code == 404
    corpo = resposta.get_json()
    assert corpo["codigo"] == "token_invalido"
    assert corpo["correlacao"]


# AC3 — token expirado responde 410 `token_expirado`.


def test_token_expirado_responde_410_token_expirado(cliente, sessao, aplicacao):
    token = cadastrar_e_obter_token(cliente, sessao, aplicacao)
    token_gravado(sessao).expira_em = agora() - timedelta(minutes=1)
    sessao.flush()

    resposta = cliente.post(ROTA, json={"token": token})

    assert resposta.status_code == 410
    assert resposta.get_json()["codigo"] == "token_expirado"
    assert usuario(sessao).email_confirmado is False


# AC4 — token ja usado responde 409 `token_ja_usado`.


def test_confirmar_duas_vezes_o_mesmo_token_responde_409_na_segunda(
    cliente, sessao, aplicacao
):
    token = cadastrar_e_obter_token(cliente, sessao, aplicacao)

    primeira = cliente.post(ROTA, json={"token": token})
    segunda = cliente.post(ROTA, json={"token": token})

    assert primeira.status_code == 200
    assert segunda.status_code == 409
    assert segunda.get_json()["codigo"] == "token_ja_usado"
