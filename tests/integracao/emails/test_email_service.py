"""Testes do servico de e-mail — API-10 AC1, AC2, AC3; AD-010 (T10)."""

import logging

import pytest
from sqlalchemy import func, select

from app.core.unidade_de_trabalho import transacao
from app.extensions import db
from app.modules.contas.models import Usuario
from app.modules.emails.backends import CHAVE_DO_BACKEND, BackendDeLog
from app.modules.emails.models import EmailEnviado
from app.modules.emails.service import EmailService

DESTINATARIO = "servico.de.email@exemplo.test"
ASSUNTO = "Confirme seu e-mail"
CORPO = "Corpo da mensagem."
FALHA = "conexao recusada pelo servidor de e-mail"


class BackendQueFalha:
    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        raise OSError(FALHA)


@pytest.fixture()
def backend_de_log(aplicacao, monkeypatch):
    monkeypatch.setitem(aplicacao.extensions, CHAVE_DO_BACKEND, BackendDeLog())


@pytest.fixture()
def backend_que_falha(aplicacao, monkeypatch):
    monkeypatch.setitem(aplicacao.extensions, CHAVE_DO_BACKEND, BackendQueFalha())


def registros(sessao, destinatario=DESTINATARIO) -> list[EmailEnviado]:
    return list(
        sessao.scalars(
            select(EmailEnviado).where(EmailEnviado.destinatario == destinatario)
        )
    )


# API-10 AC1 — o backend de log grava, loga e nao toca a rede.


def test_backend_de_log_grava_a_mensagem_em_emails_enviados(sessao, backend_de_log):
    EmailService.enviar(DESTINATARIO, ASSUNTO, CORPO)

    gravados = registros(sessao)
    assert len(gravados) == 1
    assert gravados[0].destinatario == DESTINATARIO
    assert gravados[0].assunto == ASSUNTO
    assert gravados[0].corpo == CORPO
    assert gravados[0].situacao == "enviado"
    assert gravados[0].erro is None
    assert gravados[0].criado_em is not None


def test_backend_de_log_emite_a_mensagem_no_log(sessao, backend_de_log, caplog):
    with caplog.at_level(logging.INFO, logger="app.modules.emails.backends"):
        EmailService.enviar(DESTINATARIO, ASSUNTO, CORPO)

    assert DESTINATARIO in caplog.text
    assert ASSUNTO in caplog.text
    assert CORPO in caplog.text


def test_backend_de_log_nao_tenta_conexao_de_rede(sessao, backend_de_log, monkeypatch):
    import smtplib

    def recusar(*args, **kwargs):
        raise AssertionError("o backend de log nao pode abrir conexao SMTP")

    monkeypatch.setattr(smtplib, "SMTP", recusar)
    monkeypatch.setattr(smtplib, "SMTP_SSL", recusar)

    registro = EmailService.enviar(DESTINATARIO, ASSUNTO, CORPO)

    assert registro.situacao == "enviado"


# API-10 AC2 — a falha do backend nao propaga e nao desfaz o negocio.


def test_falha_do_backend_fica_registrada_como_falha_sem_propagar(
    sessao, backend_que_falha
):
    registro = EmailService.enviar(DESTINATARIO, ASSUNTO, CORPO)

    assert registro.situacao == "falha"
    assert FALHA in registro.erro
    gravados = registros(sessao)
    assert len(gravados) == 1
    assert gravados[0].situacao == "falha"


def test_falha_do_backend_nao_desfaz_a_escrita_de_negocio(sessao, backend_que_falha):
    email_do_usuario = "cadastro.com.email.falho@exemplo.test"

    with transacao() as unidade:
        unidade.add(
            Usuario(nome="Ada", email=email_do_usuario, senha_hash="hash-bcrypt")
        )
        unidade.flush()
        EmailService.enviar(DESTINATARIO, ASSUNTO, CORPO)

    gravados = sessao.execute(
        select(func.count()).select_from(Usuario).where(Usuario.email == email_do_usuario)
    ).scalar()
    assert gravados == 1
    assert registros(sessao)[0].situacao == "falha"


# API-10 AC3 — o corpo carrega a URL completa montada da origem do front.


def test_o_email_de_confirmacao_carrega_a_url_completa_com_o_token(
    aplicacao, sessao, backend_de_log
):
    token = "token-cru-de-confirmacao"

    registro = EmailService.enviar_confirmacao_de_email(DESTINATARIO, token)

    esperada = f"{aplicacao.config['URL_DO_FRONT']}/confirmar-email?token={token}"
    assert esperada in registro.corpo
    assert registro.destinatario == DESTINATARIO
    assert db.session.get(EmailEnviado, registro.id).corpo == registro.corpo
