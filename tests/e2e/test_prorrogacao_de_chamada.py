"""Testes e2e de prorrogar e encerrar chamada — API-16 AC6, AC7, AC8, AC10 (T40)."""

import uuid
from datetime import datetime, timezone

from app.extensions import db
from app.modules.eventos.models import Chamada
from tests.e2e.apoio_de_chamadas import criar_chamada
from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_chair,
    criar_evento,
    criar_usuario,
)

VIGENTE = datetime(2026, 2, 1, tzinfo=timezone.utc)
POSTERIOR = "2026-03-01T00:00:00Z"
ANTERIOR = "2026-01-15T00:00:00Z"
IGUAL = "2026-02-01T00:00:00Z"


def rota_de_prorrogacao(chamada_id) -> str:
    return f"/api/chamadas/{chamada_id}/prorrogar"


def rota_de_encerramento(chamada_id) -> str:
    return f"/api/chamadas/{chamada_id}/encerrar"


# AC6 — prorrogar para data posterior atualiza o prazo, incrementa `versao`, 200.


def test_a_prorrogacao_para_data_posterior_atualiza_o_prazo(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento, data_limite=VIGENTE)

    resposta = cliente.post(
        rota_de_prorrogacao(chamada.id),
        headers=cabecalhos(chair),
        json={"dataLimite": POSTERIOR},
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["dataLimite"] == POSTERIOR
    assert corpo["versao"] == 2
    gravada = db.session.get(Chamada, chamada.id)
    assert gravada.data_limite == datetime(2026, 3, 1, tzinfo=timezone.utc)
    assert gravada.versao == 2


# AC7 — prorrogar **nunca encurta prazo**: anterior, igual ou ausente e 422.


def test_a_prorrogacao_para_data_anterior_responde_422_na_data_limite(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento, data_limite=VIGENTE)

    resposta = cliente.post(
        rota_de_prorrogacao(chamada.id),
        headers=cabecalhos(chair),
        json={"dataLimite": ANTERIOR},
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "dataLimite" in corpo["campos"]
    gravada = db.session.get(Chamada, chamada.id)
    assert gravada.data_limite == VIGENTE
    assert gravada.versao == 1


def test_a_prorrogacao_para_a_mesma_data_responde_422_na_data_limite(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento, data_limite=VIGENTE)

    resposta = cliente.post(
        rota_de_prorrogacao(chamada.id),
        headers=cabecalhos(chair),
        json={"dataLimite": IGUAL},
    )

    assert resposta.status_code == 422
    assert "dataLimite" in resposta.get_json()["campos"]
    assert db.session.get(Chamada, chamada.id).versao == 1


def test_a_prorrogacao_sem_data_limite_responde_422_na_data_limite(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento, data_limite=VIGENTE)

    resposta = cliente.post(
        rota_de_prorrogacao(chamada.id), headers=cabecalhos(chair), json={}
    )

    assert resposta.status_code == 422
    assert "dataLimite" in resposta.get_json()["campos"]
    assert db.session.get(Chamada, chamada.id).versao == 1


# AC8 — encerrar marca `encerradaManualmente`, incrementa `versao`, 200.


def test_o_encerramento_marca_a_chamada_e_incrementa_a_versao(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento)

    resposta = cliente.post(
        rota_de_encerramento(chamada.id), headers=cabecalhos(chair)
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["encerradaManualmente"] is True
    assert corpo["versao"] == 2
    gravada = db.session.get(Chamada, chamada.id)
    assert gravada.encerrada_manualmente is True
    assert gravada.versao == 2


# AC10 — 404 em ambas as rotas.


def test_a_prorrogacao_de_chamada_inexistente_responde_404(cliente, sessao):
    resposta = cliente.post(
        rota_de_prorrogacao(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"dataLimite": POSTERIOR},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "chamada_inexistente"


def test_a_prorrogacao_de_chamada_inexistente_sem_corpo_responde_404(cliente, sessao):
    """Estado antes de corpo: o 404 tem precedencia sobre o 422 de `dataLimite`."""
    resposta = cliente.post(
        rota_de_prorrogacao(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "chamada_inexistente"


def test_o_encerramento_de_chamada_inexistente_responde_404(cliente, sessao):
    resposta = cliente.post(
        rota_de_encerramento(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "chamada_inexistente"


# RBAC (AD-008) — 403 para quem nao e chair do evento.


def test_a_prorrogacao_por_quem_nao_e_chair_responde_403(cliente, sessao):
    evento = criar_evento()
    chamada = criar_chamada(evento, data_limite=VIGENTE)

    resposta = cliente.post(
        rota_de_prorrogacao(chamada.id),
        headers=cabecalhos(criar_usuario()),
        json={"dataLimite": POSTERIOR},
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert db.session.get(Chamada, chamada.id).data_limite == VIGENTE


def test_o_encerramento_por_quem_nao_e_chair_responde_403(cliente, sessao):
    evento = criar_evento()
    chamada = criar_chamada(evento)

    resposta = cliente.post(
        rota_de_encerramento(chamada.id), headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert db.session.get(Chamada, chamada.id).encerrada_manualmente is False


def test_o_encerramento_sem_token_responde_401(cliente, sessao):
    evento = criar_evento()
    chamada = criar_chamada(evento)

    resposta = cliente.post(rota_de_encerramento(chamada.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
