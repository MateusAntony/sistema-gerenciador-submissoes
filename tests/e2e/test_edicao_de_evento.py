"""Testes de ponta a ponta de `PATCH /api/eventos/{id}` — API-14 AC3..AC7, AC9, D2 (T36)."""

import uuid

from app.modules.eventos.repository import EventoRepository
from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_chair,
    criar_evento,
    criar_usuario,
)


def rota(evento_id) -> str:
    return f"/api/eventos/{evento_id}"


# AC3 — `versao` igual: aplica, incrementa `versao` em 1, 200.


def test_a_edicao_com_a_versao_atual_aplica_e_responde_200(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "titulo": "Novo Título"},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["titulo"] == "Novo Título"


def test_a_edicao_bem_sucedida_incrementa_a_versao_em_um(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    corpo = cliente.patch(
        rota(evento.id), headers=cabecalhos(chair), json={"versao": 1, "sigla": "NOVA"}
    ).get_json()

    assert corpo["versao"] == 2
    assert corpo["sigla"] == "NOVA"


def test_a_edicao_persiste_a_alteracao_e_a_nova_versao(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "avaliadoresPorSubmissao": 3},
    )

    gravado = EventoRepository.por_id(evento.id)
    assert gravado.avaliadores_por_submissao == 3
    assert gravado.versao == 2


# AC4 / D2 — `versao` divergente: 409 `conflito_de_versao` com o atual em `atual`.


def test_a_edicao_com_versao_divergente_responde_409_conflito_de_versao(
    cliente, sessao
):
    evento = criar_evento(titulo="Título Vigente")
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 7, "titulo": "Título Perdido"},
    )

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "conflito_de_versao"
    assert "correlacao" in corpo
    # D2 — o registro atual vem em `atual`, no envelope, nao cru no corpo.
    assert corpo["atual"]["id"] == str(evento.id)
    assert corpo["atual"]["titulo"] == "Título Vigente"
    assert corpo["atual"]["versao"] == 1


def test_a_edicao_com_versao_divergente_nao_altera_o_evento(cliente, sessao):
    evento = criar_evento(titulo="Título Vigente")
    chair = criar_chair(evento)

    cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 7, "titulo": "Título Perdido"},
    )

    gravado = EventoRepository.por_id(evento.id)
    assert gravado.titulo == "Título Vigente"
    assert gravado.versao == 1


# AC5 — `avaliadoresPorSubmissao` fora de inteiro >= 1.


def test_avaliadores_por_submissao_zero_responde_422_no_campo(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "avaliadoresPorSubmissao": 0},
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "avaliadoresPorSubmissao" in corpo["campos"]


# AC6 — rebuttal ligado sem prazo.


def test_rebuttal_habilitado_sem_prazo_responde_422_no_prazo(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "rebuttalHabilitado": True},
    )

    assert resposta.status_code == 422
    assert "prazoRebuttalDias" in resposta.get_json()["campos"]


def test_rebuttal_habilitado_com_prazo_e_aceito(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "rebuttalHabilitado": True, "prazoRebuttalDias": 7},
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["rebuttalHabilitado"] is True
    assert corpo["prazoRebuttalDias"] == 7


# AC7 — `maximoDeRodadas` fora de inteiro >= 1.


def test_maximo_de_rodadas_zero_responde_422_no_campo(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "maximoDeRodadas": 0},
    )

    assert resposta.status_code == 422
    assert "maximoDeRodadas" in resposta.get_json()["campos"]


# Edge Case — `identificadorPagina` em evento **ja publicado**.


def test_alterar_o_identificador_de_evento_publicado_responde_422(cliente, sessao):
    evento = criar_evento(situacao="publicado", identificador="ja-divulgado")
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "identificadorPagina": "outro-endereco"},
    )

    assert resposta.status_code == 422
    assert "identificadorPagina" in resposta.get_json()["campos"]
    assert EventoRepository.por_id(evento.id).identificador_pagina == "ja-divulgado"


def test_alterar_o_identificador_de_evento_aprovado_e_permitido(cliente, sessao):
    """Evento **aprovado** (nao publicado) ainda pode trocar o identificador."""
    evento = criar_evento(situacao="aprovado", identificador="ainda-privado")
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "identificadorPagina": "novo-endereco"},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["identificadorPagina"] == "novo-endereco"


# AC9 — `eventoPaiId` que e descendente do proprio evento editado.


def test_apontar_o_pai_para_um_descendente_do_proprio_evento_responde_422(
    cliente, sessao
):
    """Hierarquia evento -> filho -> neto; apontar o pai do evento para o neto."""
    evento = criar_evento(titulo="Evento Raiz")
    filho = criar_evento(titulo="Filho", evento_pai_id=evento.id)
    neto = criar_evento(titulo="Neto", evento_pai_id=filho.id)
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "eventoPaiId": str(neto.id)},
    )

    assert resposta.status_code == 422
    assert "eventoPaiId" in resposta.get_json()["campos"]
    assert EventoRepository.por_id(evento.id).evento_pai_id is None


def test_apontar_o_pai_para_um_evento_fora_da_propria_arvore_e_permitido(
    cliente, sessao
):
    evento = criar_evento(titulo="Evento Raiz")
    outro = criar_evento(titulo="Evento Irmão")
    chair = criar_chair(evento)

    resposta = cliente.patch(
        rota(evento.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "eventoPaiId": str(outro.id)},
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["eventoPaiId"] == str(outro.id)


# RBAC (AD-008) — 403 para quem nao e chair; 403 antes de 404.


def test_a_edicao_por_quem_nao_e_chair_do_evento_responde_403(cliente, sessao):
    evento = criar_evento(titulo="Título Vigente")
    intruso = criar_usuario()

    resposta = cliente.patch(
        rota(evento.id), headers=cabecalhos(intruso), json={"versao": 1, "titulo": "X"}
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert EventoRepository.por_id(evento.id).titulo == "Título Vigente"


def test_a_edicao_de_evento_inexistente_por_quem_nao_pode_responde_403(cliente, sessao):
    """403 antes de 404: a resposta nao revela quais eventos existem (API-09 AC5)."""
    resposta = cliente.patch(
        rota(uuid.uuid4()),
        headers=cabecalhos(criar_usuario()),
        json={"versao": 1, "titulo": "X"},
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_a_edicao_de_evento_inexistente_pelo_administrador_responde_404(
    cliente, sessao
):
    resposta = cliente.patch(
        rota(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"versao": 1, "titulo": "X"},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "evento_inexistente"


# Precedencia — estado antes do corpo: 404 mesmo com corpo invalido.


def test_a_edicao_de_evento_inexistente_com_corpo_invalido_responde_404(
    cliente, sessao
):
    resposta = cliente.patch(
        rota(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"campoQueNaoExiste": 1},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "evento_inexistente"


def test_a_edicao_sem_token_responde_401(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.patch(rota(evento.id), json={"versao": 1, "titulo": "X"})

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
