"""Testes de ponta a ponta do reenvio de confirmacao — API-06 AC5, AC6 (T14)."""

from datetime import timedelta

from sqlalchemy import func, select

from app.modules.contas.models import PedidoDeReenvio, TokenConfirmacaoEmail
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


def envelhecer_ultimo_pedido(sessao, segundos: int) -> None:
    """Recua o instante do ultimo pedido para simular a passagem do tempo.

    A janela passou a ser governada por `pedidos_de_reenvio`, e nao pela emissao
    do token: e o que torna a contagem identica para e-mail com e sem conta
    (API-06 AC7).
    """
    ultimo = sessao.scalars(
        select(PedidoDeReenvio).order_by(PedidoDeReenvio.criado_em.desc())
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
    cliente.post(ROTA, json={"email": EMAIL})  # abre a janela
    envelhecer_ultimo_pedido(sessao, segundos=20)

    resposta = cliente.post(ROTA, json={"email": EMAIL})

    assert resposta.status_code == 200
    assert resposta.get_json() == {"esperarSegundos": 40}


def test_pedido_dentro_da_janela_nao_envia_novo_email(cliente, sessao):
    cliente.post("/api/usuarios", json=CADASTRO)
    assert contar_emails(sessao) == 1
    cliente.post(ROTA, json={"email": EMAIL})  # abre a janela e envia o 2o
    assert contar_emails(sessao) == 2
    envelhecer_ultimo_pedido(sessao, segundos=20)

    cliente.post(ROTA, json={"email": EMAIL})

    assert contar_emails(sessao) == 2
    assert contar_tokens(sessao) == 2


# AC5 — passada a janela, um novo e-mail e enviado.


def test_passada_a_janela_um_novo_email_e_enviado(cliente, sessao):
    cliente.post("/api/usuarios", json=CADASTRO)
    cliente.post(ROTA, json={"email": EMAIL})  # abre a janela e envia o 2o
    envelhecer_ultimo_pedido(sessao, segundos=61)

    resposta = cliente.post(ROTA, json={"email": EMAIL})

    assert resposta.status_code == 200
    assert resposta.get_json() == {"esperarSegundos": 60}
    assert contar_emails(sessao) == 3
    assert contar_tokens(sessao) == 3


# AC7 — as duas sequencias sao identicas par a par. Este e o teste que faltava:
# sem ele, o oraculo de enumeracao passou pelo gate com todos os testes verdes.


def test_sequencias_identicas_para_email_com_e_sem_conta(cliente, sessao):
    """Dois pedidos com o mesmo intervalo, um para cada tipo de e-mail.

    O defeito que este teste mata: quando a janela era registrada so para contas
    existentes, o segundo pedido devolvia 40 para e-mail cadastrado e 60 para
    nao cadastrado — duas chamadas revelavam quem tem conta no sistema.
    """
    ContaRepository.criar(nome="Ada", email=EMAIL, senha_hash="hash")

    respostas = {}
    for rotulo, email in (("com_conta", EMAIL), ("sem_conta", EMAIL_SEM_CONTA)):
        primeira = cliente.post(ROTA, json={"email": email})
        envelhecer_ultimo_pedido(sessao, segundos=20)
        segunda = cliente.post(ROTA, json={"email": email})
        respostas[rotulo] = [
            (primeira.status_code, primeira.get_json()),
            (segunda.status_code, segunda.get_json()),
        ]

    assert respostas["com_conta"] == [(200, {"esperarSegundos": 60}),
                                      (200, {"esperarSegundos": 40})]
    assert respostas["sem_conta"] == respostas["com_conta"]


# AC8 — a tabela guarda so o hash, e registros vencidos somem.


def test_o_email_cru_nao_e_gravado_em_pedidos_de_reenvio(cliente, sessao):
    cliente.post(ROTA, json={"email": EMAIL_SEM_CONTA})

    pedidos = sessao.scalars(select(PedidoDeReenvio)).all()

    assert len(pedidos) == 1
    assert pedidos[0].email_hash != EMAIL_SEM_CONTA
    assert EMAIL_SEM_CONTA not in pedidos[0].email_hash
    assert len(pedidos[0].email_hash) == 64


def test_o_mesmo_email_em_caixa_diferente_compartilha_a_janela(cliente, sessao):
    cliente.post(ROTA, json={"email": "Pessoa@UEFS.br"})
    envelhecer_ultimo_pedido(sessao, segundos=20)

    resposta = cliente.post(ROTA, json={"email": "pessoa@uefs.br"})

    assert resposta.get_json() == {"esperarSegundos": 40}


def test_pedidos_vencidos_sao_removidos(cliente, sessao):
    cliente.post(ROTA, json={"email": EMAIL_SEM_CONTA})
    envelhecer_ultimo_pedido(sessao, segundos=61)

    cliente.post(ROTA, json={"email": "outro@exemplo.test"})

    restantes = sessao.scalars(select(PedidoDeReenvio)).all()
    assert len(restantes) == 1
