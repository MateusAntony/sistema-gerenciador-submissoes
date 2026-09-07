"""Testes e2e de `DELETE /api/criterios/{id}` — API-17 AC5, AC6, AC7 (T42)."""

import uuid

from app.extensions import db
from app.modules.eventos.models import CriterioAvaliacao
from tests.e2e.apoio_de_criterios import (
    criar_criterio,
    registrar_nota,
    rota_do_criterio,
)
from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_chair,
    criar_evento,
    criar_usuario,
)

# AC5 — criterio **sem** notas: 204 sem corpo, linha removida.


def test_a_exclusao_de_criterio_sem_notas_responde_204_sem_corpo(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)

    resposta = cliente.delete(
        rota_do_criterio(criterio.id), headers=cabecalhos(chair)
    )

    assert resposta.status_code == 204
    assert resposta.get_data() == b""


def test_a_exclusao_de_criterio_sem_notas_remove_a_linha(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)

    cliente.delete(rota_do_criterio(criterio.id), headers=cabecalhos(chair))

    assert db.session.get(CriterioAvaliacao, criterio.id) is None


# AC6 — criterio **com** nota: 409 `criterio_com_notas` com `acaoSugerida`.


def test_a_exclusao_de_criterio_com_notas_responde_409_com_acao_sugerida(
    cliente, sessao
):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)
    registrar_nota(criterio)

    resposta = cliente.delete(
        rota_do_criterio(criterio.id), headers=cabecalhos(chair)
    )

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "criterio_com_notas"
    assert corpo["acaoSugerida"] == "desativar"
    assert "mensagem" in corpo
    assert "correlacao" in corpo


def test_a_exclusao_de_criterio_com_notas_nao_remove_a_linha(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)
    registrar_nota(criterio)

    cliente.delete(rota_do_criterio(criterio.id), headers=cabecalhos(chair))

    assert db.session.get(CriterioAvaliacao, criterio.id) is not None


# AC7 — criterio inexistente e 404 `criterio_inexistente`.


def test_a_exclusao_de_criterio_inexistente_responde_404(cliente, sessao):
    resposta = cliente.delete(
        rota_do_criterio(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "criterio_inexistente"


# RBAC (AD-008) — 403 para quem nao e chair do evento.


def test_a_exclusao_por_quem_nao_e_chair_responde_403(cliente, sessao):
    evento = criar_evento()
    criterio = criar_criterio(evento, ordem=1)

    resposta = cliente.delete(
        rota_do_criterio(criterio.id), headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert db.session.get(CriterioAvaliacao, criterio.id) is not None


def test_a_exclusao_de_criterio_inexistente_por_quem_nao_pode_responde_403(
    cliente, sessao
):
    """403 antes de 404: a resposta nao revela quais criterios existem."""
    resposta = cliente.delete(
        rota_do_criterio(uuid.uuid4()), headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_a_exclusao_sem_token_responde_401(cliente, sessao):
    evento = criar_evento()
    criterio = criar_criterio(evento, ordem=1)

    resposta = cliente.delete(rota_do_criterio(criterio.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
