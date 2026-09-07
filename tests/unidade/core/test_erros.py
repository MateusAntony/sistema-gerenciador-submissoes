"""Testes do envelope de erro e dos tratadores centrais — API-01 AC1, AC2, AC5, AC6."""

import logging

import pytest
from flask import Flask, request
from pydantic import BaseModel, ConfigDict, field_validator

from app.core.erros import (
    Conflito,
    ConflitoDeVersao,
    ErroDaApi,
    ErroDeValidacao,
    NaoAutenticado,
    NaoEncontrado,
    SemPermissao,
    registrar_tratadores,
)

CHAVES_DO_ENVELOPE = {"codigo", "mensagem", "correlacao"}


class CorpoDeEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identificador_pagina: str
    ano: int = 2026

    @field_validator("identificador_pagina")
    @classmethod
    def _validar(cls, valor: str) -> str:
        if valor == "reservado":
            raise ValueError("Este identificador não está disponível.")
        return valor


@pytest.fixture()
def aplicacao_de_erro():
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100
    registrar_tratadores(app)

    @app.post("/dominio")
    def _dominio():
        raise NaoEncontrado("evento_inexistente", "Evento não encontrado.")

    @app.post("/validacao-de-dominio")
    def _validacao_de_dominio():
        raise ErroDeValidacao({"instituicao": "Campo obrigatório."})

    @app.post("/conflito-de-versao")
    def _conflito_de_versao():
        raise ConflitoDeVersao({"id": "evt-1", "versao": 7})

    @app.post("/schema")
    def _schema():
        CorpoDeEntrada(**request.get_json())
        return {"ok": True}

    @app.post("/corpo")
    def _corpo():
        return {"recebido": request.get_json()}

    @app.get("/explode")
    def _explode():
        raise RuntimeError("segredo interno que nao pode vazar")

    @app.get("/existe")
    def _existe():
        return {"ok": True}

    return app


@pytest.fixture()
def cliente_de_erro(aplicacao_de_erro):
    return aplicacao_de_erro.test_client()


def test_erro_de_dominio_sai_com_o_status_e_o_codigo_da_propria_excecao(cliente_de_erro):
    resposta = cliente_de_erro.post("/dominio")
    corpo = resposta.get_json()

    assert resposta.status_code == 404
    assert corpo["codigo"] == "evento_inexistente"
    assert corpo["mensagem"] == "Evento não encontrado."
    assert CHAVES_DO_ENVELOPE <= set(corpo)
    assert isinstance(corpo["correlacao"], str)
    assert corpo["correlacao"] != ""


def test_as_subclasses_carregam_codigo_status_mensagem_e_extras():
    assert (NaoAutenticado().status, NaoAutenticado().codigo) == (401, "nao_autenticado")
    assert (SemPermissao().status, SemPermissao().codigo) == (403, "sem_permissao")
    assert NaoEncontrado("evento_inexistente").status == 404
    assert Conflito("email_existente").status == 409
    assert ErroDeValidacao({"senha": "Valor muito curto."}).status == 422
    assert ErroDeValidacao({"senha": "Valor muito curto."}).extras == {
        "campos": {"senha": "Valor muito curto."}
    }
    assert ErroDaApi().status == 500

    conflito = Conflito("solicitacao_ja_decidida", "Já decidida.", decididoPorId="u-1")

    assert conflito.extras == {"decididoPorId": "u-1"}


def test_erro_de_validacao_de_dominio_sai_como_422_com_campos(cliente_de_erro):
    resposta = cliente_de_erro.post("/validacao-de-dominio")
    corpo = resposta.get_json()

    assert resposta.status_code == 422
    assert corpo["codigo"] == "dados_invalidos"
    assert corpo["campos"] == {"instituicao": "Campo obrigatório."}


def test_conflito_de_versao_leva_o_registro_atual_no_campo_atual(cliente_de_erro):
    resposta = cliente_de_erro.post("/conflito-de-versao")
    corpo = resposta.get_json()

    assert resposta.status_code == 409
    assert corpo["codigo"] == "conflito_de_versao"
    assert corpo["atual"] == {"id": "evt-1", "versao": 7}


def test_campo_ausente_no_schema_vira_422_com_o_nome_em_camelcase(cliente_de_erro):
    resposta = cliente_de_erro.post("/schema", json={})
    corpo = resposta.get_json()

    assert resposta.status_code == 422
    assert corpo["codigo"] == "dados_invalidos"
    assert corpo["campos"] == {"identificadorPagina": "Campo obrigatório."}


def test_campo_desconhecido_no_schema_vira_422_nomeando_o_campo(cliente_de_erro):
    resposta = cliente_de_erro.post(
        "/schema", json={"identificador_pagina": "sbc-2026", "sobrando": 1}
    )
    corpo = resposta.get_json()

    assert resposta.status_code == 422
    assert corpo["campos"] == {"sobrando": "Campo não reconhecido."}


def test_mensagem_do_validador_de_dominio_chega_em_pt_br_no_campo(cliente_de_erro):
    resposta = cliente_de_erro.post("/schema", json={"identificador_pagina": "reservado"})
    corpo = resposta.get_json()

    assert resposta.status_code == 422
    assert corpo["campos"] == {
        "identificadorPagina": "Este identificador não está disponível."
    }


def test_rota_inexistente_devolve_envelope_json_e_nunca_html(cliente_de_erro):
    resposta = cliente_de_erro.get("/nao-existe")
    corpo = resposta.get_json()

    assert resposta.status_code == 404
    assert resposta.mimetype == "application/json"
    assert corpo["codigo"] == "nao_encontrado"
    assert CHAVES_DO_ENVELOPE <= set(corpo)
    assert "<html" not in resposta.get_data(as_text=True).lower()


def test_metodo_errado_devolve_envelope_json_e_nunca_html(cliente_de_erro):
    resposta = cliente_de_erro.post("/existe")
    corpo = resposta.get_json()

    assert resposta.status_code == 405
    assert resposta.mimetype == "application/json"
    assert corpo["codigo"] == "metodo_nao_permitido"
    assert "<html" not in resposta.get_data(as_text=True).lower()


def test_corpo_que_nao_e_json_vira_400_corpo_invalido(cliente_de_erro):
    resposta = cliente_de_erro.post(
        "/corpo", data="isto nao e json", content_type="application/json"
    )
    corpo = resposta.get_json()

    assert resposta.status_code == 400
    assert corpo["codigo"] == "corpo_invalido"
    assert CHAVES_DO_ENVELOPE <= set(corpo)


def test_corpo_acima_do_limite_vira_413(cliente_de_erro):
    resposta = cliente_de_erro.post(
        "/corpo", data="x" * 5000, content_type="application/json"
    )
    corpo = resposta.get_json()

    assert resposta.status_code == 413
    assert corpo["codigo"] == "corpo_muito_grande"
    assert CHAVES_DO_ENVELOPE <= set(corpo)


def test_excecao_nao_prevista_vira_500_sem_stack_no_corpo_e_com_stack_no_log(
    cliente_de_erro, caplog
):
    with caplog.at_level(logging.ERROR):
        resposta = cliente_de_erro.get("/explode")
    corpo = resposta.get_json()
    texto = resposta.get_data(as_text=True)

    assert resposta.status_code == 500
    assert corpo["codigo"] == "erro_interno"
    assert set(corpo) == CHAVES_DO_ENVELOPE
    assert "Traceback" not in texto
    assert "segredo interno que nao pode vazar" not in texto
    assert "Traceback" in caplog.text
    assert "segredo interno que nao pode vazar" in caplog.text
