"""Testes de ponta a ponta da leitura do evento — API-14 AC1, AC2 (T35)."""

import uuid

from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_evento,
    criar_usuario,
)

# AC1 — `GET /api/eventos/{id}`: 200 com o evento completo, ou 404.


def test_a_leitura_por_id_responde_200_com_o_evento_completo(cliente, sessao):
    evento = criar_evento(titulo="Congresso de Computação", identificador="cc-2026")

    resposta = cliente.get(
        f"/api/eventos/{evento.id}", headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["id"] == str(evento.id)
    assert corpo["titulo"] == "Congresso de Computação"
    assert corpo["identificadorPagina"] == "cc-2026"
    assert corpo["situacao"] == "aprovado"
    assert corpo["sigla"] == "SEXT"
    assert corpo["ano"] == 2026
    assert corpo["tipo"] == "conferencia"
    assert corpo["cidade"] == "Feira de Santana"
    assert corpo["estado"] == "Bahia"
    assert corpo["pais"] == "Brasil"
    assert corpo["fuso"] == "America/Bahia"
    assert corpo["dataInicio"] == "2026-05-01"
    assert corpo["dataTermino"] == "2026-05-03"
    assert corpo["modeloDeAvaliacao"] == "aberta"
    assert corpo["avaliadoresPorSubmissao"] == 1
    assert corpo["rebuttalHabilitado"] is False
    assert corpo["maximoDeRodadas"] == 1
    assert corpo["versao"] == 1


def test_a_leitura_de_evento_inexistente_por_id_responde_404(cliente, sessao):
    resposta = cliente.get(
        f"/api/eventos/{uuid.uuid4()}", headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "evento_inexistente"


# AC2 — `GET /api/eventos/por-identificador/{slug}`: resolve sem exigir participacao.


def test_a_leitura_por_identificador_responde_200_com_o_evento(cliente, sessao):
    evento = criar_evento(titulo="Semana Acadêmica", identificador="semana-2026")

    resposta = cliente.get(
        "/api/eventos/por-identificador/semana-2026",
        headers=cabecalhos(criar_usuario()),
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["id"] == str(evento.id)
    assert corpo["titulo"] == "Semana Acadêmica"
    assert corpo["identificadorPagina"] == "semana-2026"


def test_a_leitura_por_identificador_nao_exige_participacao_no_evento(cliente, sessao):
    """AC2 — um usuario sem nenhum papel naquele evento recebe 200, nao 403."""
    criar_evento(identificador="aberto-a-todos")
    sem_papel = criar_usuario()

    resposta = cliente.get(
        "/api/eventos/por-identificador/aberto-a-todos", headers=cabecalhos(sem_papel)
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["identificadorPagina"] == "aberto-a-todos"


def test_a_leitura_por_identificador_inexistente_responde_404(cliente, sessao):
    resposta = cliente.get(
        "/api/eventos/por-identificador/nao-existe", headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "evento_inexistente"
