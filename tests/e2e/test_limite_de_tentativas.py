"""Testes de ponta a ponta do limite de tentativas — API-20 AC1..AC3 (T20)."""

from datetime import timedelta

from sqlalchemy import select

from app.extensions import bcrypt
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.sessao.models import TentativaLogin

ROTA = "/api/auth/login"
EMAIL = "tentativas@exemplo.test"
SENHA = "senha-bem-forte-1"
SENHA_ERRADA = "senha-que-nao-e-1"
JANELA_EM_SEGUNDOS = 15 * 60


def criar_conta() -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=EMAIL,
        senha_hash=bcrypt.generate_password_hash(SENHA).decode("utf-8"),
    )
    usuario.email_confirmado = True
    return usuario


def entrar(cliente, senha=SENHA, email=EMAIL):
    return cliente.post(ROTA, json={"email": email, "senha": senha})


def errar(cliente, vezes: int) -> list[int]:
    return [entrar(cliente, senha=SENHA_ERRADA).status_code for _ in range(vezes)]


def envelhecer_tentativas(sessao, segundos: int) -> None:
    """Recua as tentativas gravadas para simular a passagem da janela."""
    for tentativa in sessao.scalars(select(TentativaLogin)):
        tentativa.ocorrido_em = tentativa.ocorrido_em - timedelta(seconds=segundos)
    sessao.flush()


# AC1 — a 11a falha em 15 minutos responde 429 `muitas_tentativas`.


def test_as_dez_primeiras_falhas_ainda_respondem_401(cliente, sessao):
    criar_conta()

    assert errar(cliente, 10) == [401] * 10


def test_a_decima_primeira_falha_responde_429_muitas_tentativas(cliente, sessao):
    criar_conta()
    errar(cliente, 10)

    resposta = entrar(cliente, senha=SENHA_ERRADA)

    assert resposta.status_code == 429
    assert resposta.get_json()["codigo"] == "muitas_tentativas"


def test_o_429_traz_retry_after_em_segundos(cliente, sessao):
    criar_conta()
    errar(cliente, 10)

    resposta = entrar(cliente, senha=SENHA_ERRADA)

    espera = int(resposta.headers["Retry-After"])
    assert 0 < espera <= JANELA_EM_SEGUNDOS


def test_o_bloqueio_tambem_alcanca_a_senha_correta(cliente, sessao):
    # O limite protege a conta; liberar quem acerta na 11a tentativa devolveria
    # ao ataque exatamente o que a janela existe para negar.
    criar_conta()
    errar(cliente, 10)

    assert entrar(cliente).status_code == 429


def test_o_limite_vale_para_email_sem_conta(cliente, sessao):
    # Se a contagem so valesse para contas existentes, o 429 diria quais
    # enderecos estao cadastrados.
    for _ in range(10):
        entrar(cliente, email="ninguem@exemplo.test", senha=SENHA_ERRADA)

    resposta = entrar(cliente, email="ninguem@exemplo.test", senha=SENHA_ERRADA)

    assert resposta.status_code == 429


# AC2 — login com sucesso zera o contador.


def test_login_com_sucesso_zera_o_contador(cliente, sessao):
    criar_conta()
    errar(cliente, 9)

    assert entrar(cliente).status_code == 200

    # Sem o zeramento, a segunda falha depois do sucesso seria a 11a e daria 429.
    assert errar(cliente, 10) == [401] * 10


def test_depois_do_sucesso_a_contagem_recomeca_do_zero(cliente, sessao):
    criar_conta()
    errar(cliente, 9)
    entrar(cliente)
    errar(cliente, 10)

    assert entrar(cliente, senha=SENHA_ERRADA).status_code == 429


# AC3 — passada a janela de 15 minutos, o contador zera.


def test_passada_a_janela_de_15_minutos_o_contador_zera(cliente, sessao):
    criar_conta()
    errar(cliente, 10)
    assert entrar(cliente, senha=SENHA_ERRADA).status_code == 429

    envelhecer_tentativas(sessao, JANELA_EM_SEGUNDOS + 60)

    assert entrar(cliente, senha=SENHA_ERRADA).status_code == 401


def test_passada_a_janela_o_login_correto_volta_a_funcionar(cliente, sessao):
    criar_conta()
    errar(cliente, 10)
    envelhecer_tentativas(sessao, JANELA_EM_SEGUNDOS + 60)

    assert entrar(cliente).status_code == 200


def test_falhas_ainda_dentro_da_janela_continuam_contando(cliente, sessao):
    criar_conta()
    errar(cliente, 10)

    # Recuo menor que a janela: as dez falhas seguem valendo.
    envelhecer_tentativas(sessao, JANELA_EM_SEGUNDOS - 60)

    assert entrar(cliente, senha=SENHA_ERRADA).status_code == 429
