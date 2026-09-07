"""Testes do repositorio de participacoes — API-07 AC3..AC6 (T22).

As duas consultas que o RBAC e o seletor de evento do front dependem, mais a
constraint que impede a mesma pessoa ter o mesmo papel duas vezes no evento.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento, ParticipacaoEvento
from app.modules.eventos.repository import ParticipacaoRepository


def criar_usuario(email: str = "participante@exemplo.test") -> Usuario:
    return ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )


def criar_evento(sessao, titulo: str = "Simpósio de Extensão") -> Evento:
    evento = Evento(
        situacao="aprovado",
        titulo=titulo,
        ano=2026,
        identificador_pagina=f"evento-{uuid.uuid4().hex[:8]}",
    )
    sessao.add(evento)
    sessao.flush()
    return evento


# --- Consulta por usuario ---------------------------------------------------


def test_a_consulta_por_usuario_traz_o_evento_e_o_papel_ativo(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")

    participacoes = ParticipacaoRepository.por_usuario(usuario.id)

    assert len(participacoes) == 1
    assert participacoes[0].evento_id == evento.id
    assert participacoes[0].evento_titulo == evento.titulo
    assert participacoes[0].identificador_pagina == evento.identificador_pagina
    assert participacoes[0].papeis == ["chair"]


def test_dois_papeis_no_mesmo_evento_viram_uma_entrada_com_dois_papeis(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    ParticipacaoRepository.criar(evento.id, usuario.id, "avaliador")

    participacoes = ParticipacaoRepository.por_usuario(usuario.id)

    assert len(participacoes) == 1
    assert sorted(participacoes[0].papeis) == ["avaliador", "chair"]


def test_papeis_em_eventos_distintos_viram_entradas_distintas(sessao):
    usuario = criar_usuario()
    primeiro = criar_evento(sessao, titulo="Congresso A")
    segundo = criar_evento(sessao, titulo="Congresso B")
    ParticipacaoRepository.criar(primeiro.id, usuario.id, "chair")
    ParticipacaoRepository.criar(segundo.id, usuario.id, "avaliador")

    participacoes = ParticipacaoRepository.por_usuario(usuario.id)

    assert [participacao.evento_id for participacao in participacoes] == [
        primeiro.id,
        segundo.id,
    ]
    assert [participacao.papeis for participacao in participacoes] == [
        ["chair"],
        ["avaliador"],
    ]


def test_usuario_sem_participacao_alguma_recebe_lista_vazia(sessao):
    usuario = criar_usuario()

    assert ParticipacaoRepository.por_usuario(usuario.id) == []


def test_a_consulta_por_usuario_omite_participacao_inativa(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    participacao = ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    participacao.ativo = False
    sessao.flush()

    assert ParticipacaoRepository.por_usuario(usuario.id) == []


def test_a_consulta_por_usuario_ignora_a_participacao_de_outra_pessoa(sessao):
    usuario = criar_usuario()
    outro = criar_usuario(email="outro@exemplo.test")
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, outro.id, "chair")

    assert ParticipacaoRepository.por_usuario(usuario.id) == []


# --- Consulta por (usuario, evento) -----------------------------------------


def test_os_papeis_no_evento_saem_todos_os_ativos(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    ParticipacaoRepository.criar(evento.id, usuario.id, "responsavel_etapa")

    papeis = ParticipacaoRepository.papeis_no_evento(usuario.id, evento.id)

    assert sorted(papeis) == ["chair", "responsavel_etapa"]


def test_os_papeis_no_evento_sao_lista_vazia_quando_nao_ha_participacao(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)

    assert ParticipacaoRepository.papeis_no_evento(usuario.id, evento.id) == []


def test_os_papeis_no_evento_omitem_a_participacao_inativa(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    participacao = ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    ParticipacaoRepository.criar(evento.id, usuario.id, "avaliador")
    participacao.ativo = False
    sessao.flush()

    papeis = ParticipacaoRepository.papeis_no_evento(usuario.id, evento.id)

    assert papeis == ["avaliador"]


def test_os_papeis_no_evento_nao_vazam_de_outro_evento(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao, titulo="Congresso A")
    outro_evento = criar_evento(sessao, titulo="Congresso B")
    ParticipacaoRepository.criar(outro_evento.id, usuario.id, "chair")

    assert ParticipacaoRepository.papeis_no_evento(usuario.id, evento.id) == []


# --- Integridade ------------------------------------------------------------


def test_o_mesmo_papel_duas_vezes_no_mesmo_evento_viola_a_constraint(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")

    with pytest.raises(IntegrityError) as colisao:
        ParticipacaoRepository.criar(evento.id, usuario.id, "chair")

    assert "uq_participacao_evento_papel" in str(colisao.value.orig)
    sessao.rollback()


def test_papeis_diferentes_no_mesmo_evento_convivem(sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)

    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    ParticipacaoRepository.criar(evento.id, usuario.id, "avaliador")

    assert (
        sessao.query(ParticipacaoEvento)
        .filter_by(evento_id=evento.id, usuario_id=usuario.id)
        .count()
        == 2
    )
