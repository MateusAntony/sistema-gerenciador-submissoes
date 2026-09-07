"""Testes da configuracao por ambiente — API-21 AC4, AC5; risco R4."""

import os

import pytest

from app.config import VARIAVEIS_DE_SMTP, VARIAVEIS_OBRIGATORIAS, Config

AMBIENTE_COMPLETO = {
    "APP_ENV": "development",
    "SECRET_KEY": "chave-de-teste",
    "DATABASE_URL": "postgresql://sgs:sgs@localhost:5432/sgs",
    "URL_DO_FRONT": "http://localhost:5173",
}


def ambiente(**alteracoes):
    return {**AMBIENTE_COMPLETO, **alteracoes}


def test_desenvolvimento_liga_o_debug_e_deixa_o_cookie_sem_secure():
    config = Config(ambiente(APP_ENV="development"))

    assert config.DEBUG is True
    assert config.TESTING is False
    assert config.COOKIE_SEGURO is False
    assert config.SESSION_COOKIE_SECURE is False


def test_teste_liga_o_modo_de_teste_e_desliga_o_debug():
    config = Config(ambiente(APP_ENV="test"))

    assert config.TESTING is True
    assert config.DEBUG is False


def test_producao_desliga_o_debug_e_liga_o_secure_do_cookie():
    config = Config(ambiente(APP_ENV="production", URL_DO_FRONT="https://sgs.exemplo.br"))

    assert config.DEBUG is False
    assert config.TESTING is False
    assert config.COOKIE_SEGURO is True
    assert config.SESSION_COOKIE_SECURE is True


def test_ambiente_desconhecido_derruba_o_boot_nomeando_a_variavel():
    with pytest.raises(ValueError, match="APP_ENV"):
        Config(ambiente(APP_ENV="homologacao"))


def test_producao_sem_https_declarado_derruba_o_boot():
    with pytest.raises(ValueError, match="URL_DO_FRONT"):
        Config(ambiente(APP_ENV="production", URL_DO_FRONT="http://sgs.exemplo.br"))


@pytest.mark.parametrize("variavel", VARIAVEIS_OBRIGATORIAS)
def test_variavel_obrigatoria_ausente_derruba_o_boot_nomeando_a_variavel(variavel):
    incompleto = {
        nome: valor for nome, valor in AMBIENTE_COMPLETO.items() if nome != variavel
    }

    with pytest.raises(ValueError, match=variavel):
        Config(incompleto)


def test_o_limite_de_tamanho_do_corpo_vem_configurado():
    config = Config(ambiente(TAMANHO_MAXIMO_DE_CORPO_MB="3"))

    assert config.MAX_CONTENT_LENGTH == 3 * 1024 * 1024


def test_o_limite_de_tamanho_do_corpo_tem_padrao_sem_a_variavel():
    config = Config(ambiente())

    assert config.MAX_CONTENT_LENGTH == 10 * 1024 * 1024


def test_o_env_example_lista_todas_as_variaveis_exigidas(raiz_do_projeto):
    exemplo = (raiz_do_projeto / ".env.example").read_text(encoding="utf-8")

    for variavel in VARIAVEIS_OBRIGATORIAS:
        assert f"{variavel}=" in exemplo


def test_o_env_example_nao_carrega_segredo_real(raiz_do_projeto):
    exemplo = (raiz_do_projeto / ".env.example").read_text(encoding="utf-8")
    linhas = dict(
        linha.split("=", 1)
        for linha in exemplo.splitlines()
        if "=" in linha and not linha.startswith("#")
    )

    assert linhas["SECRET_KEY"] == "troque-me"
    assert linhas["SECRET_KEY"] != os.environ["SECRET_KEY"]
    assert "sgs_dev" not in exemplo


# API-10 AC4 — SMTP sem configuracao completa derruba o boot nomeando a variavel.

SMTP_COMPLETO = {
    "SMTP_HOST": "smtp.exemplo.br",
    "SMTP_PORTA": "587",
    "SMTP_USUARIO": "sgs",
    "SMTP_SENHA": "segredo",
    "SMTP_REMETENTE": "nao-responda@exemplo.br",
}


def test_sem_a_variavel_o_backend_de_email_padrao_e_o_de_log():
    assert Config(ambiente()).EMAIL_BACKEND == "log"


def test_backend_de_email_desconhecido_derruba_o_boot_nomeando_a_variavel():
    with pytest.raises(ValueError, match="EMAIL_BACKEND"):
        Config(ambiente(EMAIL_BACKEND="sendgrid"))


def test_backend_smtp_completo_permanece_smtp_com_a_configuracao_carregada():
    config = Config(ambiente(EMAIL_BACKEND="smtp", **SMTP_COMPLETO))

    assert config.EMAIL_BACKEND == "smtp"
    assert config.SMTP["SMTP_HOST"] == "smtp.exemplo.br"
    assert config.SMTP["SMTP_PORTA"] == "587"
    assert config.SMTP["SMTP_REMETENTE"] == "nao-responda@exemplo.br"


@pytest.mark.parametrize("variavel", VARIAVEIS_DE_SMTP)
def test_backend_smtp_sem_uma_variavel_derruba_o_boot_nomeando_a_variavel(variavel):
    incompleto = {
        nome: valor for nome, valor in SMTP_COMPLETO.items() if nome != variavel
    }

    with pytest.raises(ValueError, match=variavel):
        Config(ambiente(EMAIL_BACKEND="smtp", **incompleto))


def test_backend_smtp_incompleto_nunca_cai_silenciosamente_no_backend_de_log():
    # AC4: o boot precisa parar. Cair no log escondido faria o e-mail de
    # producao virar linha de log sem ninguem perceber.
    with pytest.raises(ValueError):
        Config(ambiente(EMAIL_BACKEND="smtp"))
