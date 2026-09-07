"""Testes do repositorio de solicitacoes e eventos — T28, API-11 e API-12 AC1/AC2.

As quatro consultas que a Fase 5 depende: por id, por `identificador_pagina`,
por solicitante e a listagem administrativa ordenada por `criado_em` crescente.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento, SolicitacaoChairInicial
from app.modules.eventos.repository import EventoRepository, SolicitacaoRepository


def criar_usuario(email: str = "solicitante@exemplo.test") -> Usuario:
    return ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )


def criar_solicitacao(
    solicitante: Usuario,
    *,
    identificador: str | None = None,
    situacao: str = "pendente",
    criado_em=None,
):
    campos = {
        "solicitante_id": solicitante.id,
        "situacao": situacao,
        "titulo": "Simpósio de Extensão",
        "ano": 2026,
        "identificador_pagina": identificador or f"sol-{uuid.uuid4().hex[:8]}",
        "data_inicio": date(2026, 5, 1),
        "data_termino": date(2026, 5, 3),
    }
    if criado_em is not None:
        campos["criado_em"] = criado_em
    return SolicitacaoRepository.criar(**campos)


# --- Busca por id -----------------------------------------------------------


def test_a_busca_por_id_devolve_a_solicitacao_gravada(sessao):
    solicitacao = criar_solicitacao(criar_usuario())

    assert SolicitacaoRepository.por_id(solicitacao.id).id == solicitacao.id


def test_a_busca_por_id_inexistente_devolve_none(sessao):
    assert SolicitacaoRepository.por_id(uuid.uuid4()) is None


# --- Busca por identificador de pagina --------------------------------------


def test_a_busca_por_identificador_encontra_a_solicitacao(sessao):
    criar_solicitacao(criar_usuario(), identificador="simposio-2026")

    encontrada = SolicitacaoRepository.por_identificador("simposio-2026")

    assert encontrada.identificador_pagina == "simposio-2026"


def test_a_busca_por_identificador_de_evento_encontra_o_evento(sessao):
    evento = EventoRepository.criar(
        situacao="aprovado",
        titulo="Congresso",
        ano=2026,
        identificador_pagina="congresso-2026",
    )

    assert EventoRepository.por_identificador("congresso-2026").id == evento.id


def test_o_identificador_de_pagina_e_unico_entre_solicitacoes(sessao):
    solicitante = criar_usuario()
    criar_solicitacao(solicitante, identificador="repetido-2026")

    with pytest.raises(IntegrityError):
        criar_solicitacao(solicitante, identificador="repetido-2026")


# --- Listagem por solicitante -----------------------------------------------


def test_a_listagem_por_solicitante_traz_so_as_do_proprio_usuario(sessao):
    dono = criar_usuario()
    outro = criar_usuario(email="outro@exemplo.test")
    minha = criar_solicitacao(dono)
    criar_solicitacao(outro)

    minhas = SolicitacaoRepository.por_solicitante(dono.id)

    assert [solicitacao.id for solicitacao in minhas] == [minha.id]


def test_a_listagem_por_solicitante_sem_nenhuma_devolve_lista_vazia(sessao):
    assert SolicitacaoRepository.por_solicitante(criar_usuario().id) == []


# --- Listagem administrativa, ordenada por criado_em crescente --------------


def test_a_listagem_administrativa_ordena_por_criado_em_crescente(sessao):
    solicitante = criar_usuario()
    base = date(2026, 1, 1)
    meio = criar_solicitacao(
        solicitante, identificador="meio", criado_em=base + timedelta(days=1)
    )
    ultima = criar_solicitacao(
        solicitante, identificador="ultima", criado_em=base + timedelta(days=2)
    )
    primeira = criar_solicitacao(
        solicitante, identificador="primeira", criado_em=base
    )

    listadas = SolicitacaoRepository.listar()

    assert [solicitacao.id for solicitacao in listadas] == [
        primeira.id,
        meio.id,
        ultima.id,
    ]


def test_a_listagem_administrativa_filtra_por_situacao(sessao):
    solicitante = criar_usuario()
    pendente = criar_solicitacao(solicitante, situacao="pendente")
    criar_solicitacao(solicitante, situacao="recusada")

    pendentes = SolicitacaoRepository.listar(situacao="pendente")

    assert [solicitacao.id for solicitacao in pendentes] == [pendente.id]


def test_a_listagem_administrativa_sem_filtro_traz_todas_as_situacoes(sessao):
    solicitante = criar_usuario()
    criar_solicitacao(solicitante, situacao="pendente")
    criar_solicitacao(solicitante, situacao="recusada")

    assert len(SolicitacaoRepository.listar()) == 2


# --- Chairs iniciais: UNIQUE (solicitacao_id, email) ------------------------


def test_o_mesmo_email_nao_pode_repetir_na_mesma_solicitacao(sessao):
    solicitacao = criar_solicitacao(criar_usuario())
    sessao.add(
        SolicitacaoChairInicial(solicitacao_id=solicitacao.id, email="ana@exemplo.test")
    )
    sessao.flush()

    sessao.add(
        SolicitacaoChairInicial(solicitacao_id=solicitacao.id, email="ana@exemplo.test")
    )
    with pytest.raises(IntegrityError):
        sessao.flush()


def test_definir_chairs_iniciais_grava_cada_email_uma_vez_so(sessao):
    solicitacao = criar_solicitacao(criar_usuario())

    SolicitacaoRepository.definir_chairs_iniciais(
        solicitacao.id, ["ana@exemplo.test", "ana@exemplo.test", "bia@exemplo.test"]
    )

    assert SolicitacaoRepository.chairs_iniciais(solicitacao.id) == [
        "ana@exemplo.test",
        "bia@exemplo.test",
    ]


# --- Auto-referencia de eventos.evento_pai_id -------------------------------


def test_o_evento_filho_aponta_para_o_pai_e_o_pai_lista_o_filho(sessao):
    pai = EventoRepository.criar(
        situacao="aprovado", titulo="Pai", ano=2026, identificador_pagina="pai-2026"
    )
    filho = EventoRepository.criar(
        situacao="aprovado",
        titulo="Filho",
        ano=2026,
        identificador_pagina="filho-2026",
        evento_pai_id=pai.id,
    )

    assert sessao.get(Evento, filho.id).evento_pai_id == pai.id
    assert EventoRepository.filhos_de(pai.id) == [filho.id]
