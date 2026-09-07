"""Testes de ponta a ponta de `GET /api/me/participacoes` — API-07 AC3..AC6 (T24).

E a rota que monta o seletor de evento e o menu do front: a forma da lista, a
agregacao por evento, a lista vazia, a omissao da inativa e o 401 sem token.
"""

import uuid

from flask_jwt_extended import create_access_token

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import ParticipacaoRepository

ROTA = "/api/me/participacoes"

CAMPOS_DA_PARTICIPACAO = {
    "eventoId",
    "eventoTitulo",
    "identificadorPagina",
    "papeis",
}


def criar_usuario(email: str = "participacoes@exemplo.test") -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    return usuario


def criar_evento(
    sessao, titulo: str = "Simpósio de Extensão", identificador: str | None = None
) -> Evento:
    evento = Evento(
        situacao="aprovado",
        titulo=titulo,
        ano=2026,
        identificador_pagina=identificador or f"evento-{uuid.uuid4().hex[:8]}",
    )
    sessao.add(evento)
    sessao.flush()
    return evento


def consultar(cliente, usuario: Usuario | None = None):
    cabecalhos = (
        {}
        if usuario is None
        else {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}
    )
    return cliente.get(ROTA, headers=cabecalhos)


# AC3 — 200 com `{ eventoId, eventoTitulo, identificadorPagina, papeis }`.


def test_a_lista_traz_os_quatro_campos_do_contrato(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(
        sessao, titulo="Congresso de Computação", identificador="congresso-2026"
    )
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")

    resposta = consultar(cliente, usuario)

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert len(corpo) == 1
    assert set(corpo[0]) == CAMPOS_DA_PARTICIPACAO
    assert corpo[0]["eventoId"] == str(evento.id)
    assert corpo[0]["eventoTitulo"] == "Congresso de Computação"
    assert corpo[0]["identificadorPagina"] == "congresso-2026"
    assert corpo[0]["papeis"] == ["chair"]


def test_a_lista_traz_uma_entrada_por_evento_em_que_o_usuario_atua(cliente, sessao):
    usuario = criar_usuario()
    primeiro = criar_evento(sessao, titulo="Congresso A")
    segundo = criar_evento(sessao, titulo="Congresso B")
    ParticipacaoRepository.criar(primeiro.id, usuario.id, "chair")
    ParticipacaoRepository.criar(segundo.id, usuario.id, "avaliador")

    corpo = consultar(cliente, usuario).get_json()

    assert [entrada["eventoTitulo"] for entrada in corpo] == [
        "Congresso A",
        "Congresso B",
    ]
    assert [entrada["papeis"] for entrada in corpo] == [["chair"], ["avaliador"]]


# AC4 — dois papeis no mesmo evento produzem **uma** entrada com dois papeis.


def test_dois_papeis_no_mesmo_evento_viram_uma_entrada_com_dois_papeis(
    cliente, sessao
):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    ParticipacaoRepository.criar(evento.id, usuario.id, "responsavel_etapa")

    corpo = consultar(cliente, usuario).get_json()

    assert len(corpo) == 1
    assert corpo[0]["eventoId"] == str(evento.id)
    assert sorted(corpo[0]["papeis"]) == ["chair", "responsavel_etapa"]


# AC5 — sem participacao alguma, lista vazia; nunca 404.


def test_usuario_sem_participacao_recebe_200_com_lista_vazia(cliente, sessao):
    usuario = criar_usuario()

    resposta = consultar(cliente, usuario)

    assert resposta.status_code == 200
    assert resposta.get_json() == []


def test_a_lista_nao_traz_a_participacao_de_outra_pessoa(cliente, sessao):
    usuario = criar_usuario()
    outro = criar_usuario(email="outro@exemplo.test")
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, outro.id, "chair")

    assert consultar(cliente, usuario).get_json() == []


# AC6 — participacao inativa e omitida.


def test_a_participacao_inativa_e_omitida_da_lista(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    inativa = ParticipacaoRepository.criar(evento.id, usuario.id, "avaliador")
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    inativa.ativo = False
    sessao.flush()

    corpo = consultar(cliente, usuario).get_json()

    assert len(corpo) == 1
    assert corpo[0]["papeis"] == ["chair"]


def test_a_unica_participacao_inativa_deixa_a_lista_vazia(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    participacao = ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    participacao.ativo = False
    sessao.flush()

    resposta = consultar(cliente, usuario)

    assert resposta.status_code == 200
    assert resposta.get_json() == []


# API-09 AC3 — sem token e 401.


def test_a_lista_sem_token_responde_401_nao_autenticado(cliente, sessao):
    resposta = consultar(cliente)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
