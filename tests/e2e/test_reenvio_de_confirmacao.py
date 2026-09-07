"""Testes de ponta a ponta do reenvio de confirmacao — API-06 AC5, AC6 (T14)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.modules.contas.models import TokenConfirmacaoEmail
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import agora
from app.modules.emails.models import EmailEnviado

ROTA = "/api/auth/reenviar-confirmacao"
EMAIL = "reenvio@exemplo.test"
EMAIL_SEM_CONTA = "nao.existe.nenhuma.conta@exemplo.test"

CADASTRO = {
    "nome": "Ada Lovelace",
    "email": EMAIL,
    "senha": "senha-bem-forte-1",
    "instituicao": "UFPI",
    "pais": "Brasil",
}


def contar_emails(sessao, destinatario=EMAIL) -> int:
    return sessao.execute(
        select(func.count())
        .select_from(EmailEnviado)
        .where(EmailEnviado.destinatario == destinatario)
    ).scalar()


def contar_tokens(sessao) -> int:
    return sessao.execute(
        select(func.count()).select_from(TokenConfirmacaoEmail)
    ).scalar()


def envelhecer_ultimo_token(sessao, segundos: int) -> None:
    """Recua o instante de emissao para simular a passagem do tempo."""
    ultimo = sessao.scalars(
        select(TokenConfirmacaoEmail).order_by(TokenConfirmacaoEmail.criado_em.desc())
    ).first()
    ultimo.criado_em = agora() - timedelta(seconds=segundos)
    sessao.flush()


# AC5 — a resposta e a mesma exista ou nao a conta.


def test_o_reenvio_responde_o_mesmo_para_email_existente_e_inexistente(
    cliente, sessao
):
    ContaRepository.criar(nome="Ada", email=EMAIL, senha_hash="hash")

    com_conta = cliente.post(ROTA, json={"email": EMAIL})
    sem_conta = cliente.post(ROTA, json={"email": EMAIL_SEM_CONTA})

    assert com_conta.status_code == 200
    assert sem_conta.status_code == 200
    assert com_conta.get_json() == {"esperarSegundos": 60}
    assert sem_conta.get_json() == com_conta.get_json()


# AC6 — dentro da janela devolve o tempo restante e nao envia novo e-mail.


def test_pedido_dentro_da_janela_devolve_o_tempo_restante(cliente, sessao):
    cliente.post("/api/usuarios", json=CADASTRO)
    envelhecer_ultimo_token(sessao, segundos=20)

    resposta = cliente.post(ROTA, json={"email": EMAIL})

    assert resposta.status_code == 200
    assert resposta.get_json() == {"esperarSegundos": 40}


def test_pedido_dentro_da_janela_nao_envia_novo_email(cliente, sessao):
    cliente.post("/api/usuarios", json=CADASTRO)
    assert contar_emails(sessao) == 1
    envelhecer_ultimo_token(sessao, segundos=20)

    cliente.post(ROTA, json={"email": EMAIL})

    assert contar_emails(sessao) == 1
    assert contar_tokens(sessao) == 1


# AC5 — passada a janela, um novo e-mail e enviado.


def test_passada_a_janela_um_novo_email_e_enviado(cliente, sessao):
    cliente.post("/api/usuarios", json=CADASTRO)
    envelhecer_ultimo_token(sessao, segundos=61)

    resposta = cliente.post(ROTA, json={"email": EMAIL})

    assert resposta.status_code == 200
    assert resposta.get_json() == {"esperarSegundos": 60}
    assert contar_emails(sessao) == 2
    assert contar_tokens(sessao) == 2
