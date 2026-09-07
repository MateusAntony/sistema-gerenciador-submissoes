"""Testes do identificador de correlacao — API-01 AC3."""

import logging
import uuid

import pytest
from flask import Flask

from app.core.correlacao import CABECALHO_DE_CORRELACAO, registrar_correlacao
from app.core.erros import NaoEncontrado, registrar_tratadores


@pytest.fixture()
def cliente_correlacionado():
    app = Flask(__name__)
    registrar_correlacao(app)
    registrar_tratadores(app)

    @app.get("/ok")
    def _ok():
        return {"ok": True}

    @app.get("/dominio")
    def _dominio():
        raise NaoEncontrado("evento_inexistente")

    @app.get("/explode")
    def _explode():
        raise RuntimeError("falha inesperada")

    return app.test_client()


def test_toda_resposta_devolve_a_correlacao_no_header(cliente_correlacionado):
    resposta = cliente_correlacionado.get("/ok")

    correlacao = resposta.headers[CABECALHO_DE_CORRELACAO]

    assert uuid.UUID(correlacao)


def test_o_corpo_do_erro_repete_a_correlacao_do_header_da_mesma_resposta(
    cliente_correlacionado,
):
    resposta = cliente_correlacionado.get("/dominio")

    assert resposta.status_code == 404
    assert resposta.get_json()["correlacao"] == resposta.headers[CABECALHO_DE_CORRELACAO]


def test_o_corpo_do_erro_interno_repete_a_correlacao_do_header(cliente_correlacionado):
    resposta = cliente_correlacionado.get("/explode")

    assert resposta.status_code == 500
    assert resposta.get_json()["correlacao"] == resposta.headers[CABECALHO_DE_CORRELACAO]


def test_duas_requisicoes_consecutivas_recebem_correlacoes_diferentes(
    cliente_correlacionado,
):
    primeira = cliente_correlacionado.get("/ok").headers[CABECALHO_DE_CORRELACAO]
    segunda = cliente_correlacionado.get("/ok").headers[CABECALHO_DE_CORRELACAO]

    assert primeira != segunda


def test_o_log_do_erro_interno_carrega_a_correlacao_da_resposta(
    cliente_correlacionado, caplog
):
    with caplog.at_level(logging.ERROR):
        resposta = cliente_correlacionado.get("/explode")

    assert resposta.headers[CABECALHO_DE_CORRELACAO] in caplog.text
