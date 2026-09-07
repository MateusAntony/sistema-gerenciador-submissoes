"""Testes da base Pydantic — API-01 AC4, AD-006."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from flask import Flask, request

from app.core.erros import registrar_tratadores
from app.core.schemas import SchemaDaApi, SchemaDeEntrada

IDENTIFICADOR = UUID("11111111-2222-3333-4444-555555555555")


class Evento(SchemaDaApi):
    id: UUID
    identificador_pagina: str
    criado_em: datetime
    sigla: str | None = None


class CriacaoDeEvento(SchemaDeEntrada):
    identificador_pagina: str


@pytest.fixture()
def cliente_de_entrada():
    app = Flask(__name__)
    registrar_tratadores(app)

    @app.post("/eventos")
    def _criar():
        return CriacaoDeEvento(**request.get_json()).para_json()

    return app.test_client()


def evento(**alteracoes) -> Evento:
    padrao = {
        "id": IDENTIFICADOR,
        "identificador_pagina": "sbc-2026",
        "criado_em": datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    }
    return Evento(**{**padrao, **alteracoes})


def test_campo_snake_case_sai_em_camelcase():
    corpo = evento().para_json()

    assert corpo["identificadorPagina"] == "sbc-2026"
    assert "identificador_pagina" not in corpo


def test_a_entrada_aceita_o_nome_em_camelcase_e_o_do_proprio_campo():
    pelo_alias = Evento(
        id=IDENTIFICADOR,
        identificadorPagina="sbc-2026",
        criadoEm=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
    )

    assert pelo_alias.identificador_pagina == "sbc-2026"
    assert evento().identificador_pagina == "sbc-2026"


def test_identificador_sai_como_string():
    corpo = evento().para_json()

    assert corpo["id"] == "11111111-2222-3333-4444-555555555555"
    assert isinstance(corpo["id"], str)


def test_data_e_hora_saem_em_iso_utc_terminando_em_z():
    assert evento().para_json()["criadoEm"] == "2026-01-02T03:04:05Z"


def test_data_e_hora_de_outro_fuso_e_convertida_para_utc():
    em_brasilia = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone(timedelta(hours=-3)))

    assert evento(criado_em=em_brasilia).para_json()["criadoEm"] == "2026-01-02T06:04:05Z"


def test_data_e_hora_sem_fuso_e_lida_como_utc():
    # O ponto do teste e justamente o momento sem fuso.
    sem_fuso = datetime(2026, 1, 2, 3, 4, 5)  # noqa: DTZ001

    assert evento(criado_em=sem_fuso).para_json()["criadoEm"] == "2026-01-02T03:04:05Z"


def test_campo_opcional_ausente_e_omitido_em_vez_de_virar_nulo():
    corpo = evento().para_json()

    assert "sigla" not in corpo
    assert None not in corpo.values()


def test_campo_opcional_presente_continua_na_saida():
    assert evento(sigla="SBC").para_json()["sigla"] == "SBC"


def test_campo_desconhecido_na_entrada_vira_422_nomeando_o_campo(cliente_de_entrada):
    resposta = cliente_de_entrada.post(
        "/eventos", json={"identificadorPagina": "sbc-2026", "sobrando": 1}
    )

    assert resposta.status_code == 422
    assert resposta.get_json()["codigo"] == "dados_invalidos"
    assert resposta.get_json()["campos"] == {"sobrando": "Campo não reconhecido."}


def test_entrada_valida_passa_pelo_schema_de_entrada(cliente_de_entrada):
    resposta = cliente_de_entrada.post("/eventos", json={"identificadorPagina": "sbc-2026"})

    assert resposta.status_code == 200
    assert resposta.get_json() == {"identificadorPagina": "sbc-2026"}
