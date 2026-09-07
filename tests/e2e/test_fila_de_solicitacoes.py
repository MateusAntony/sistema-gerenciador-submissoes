"""Testes de ponta a ponta de `GET /api/admin/solicitacoes-evento` — API-12 AC1, AC2.

A fila do administrador (T31): a ordem crescente por `criadoEm`, o filtro por
situacao, e as duas recusas que impedem qualquer usuario de ler a fila.
"""

import uuid
from datetime import date, datetime, timezone

from flask_jwt_extended import create_access_token

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.repository import SolicitacaoRepository

ROTA = "/api/admin/solicitacoes-evento"


def criar_usuario(
    email: str = "organizador@exemplo.test", *, administrador: bool = False
) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    usuario.administrador = administrador
    return usuario


def criar_administrador() -> Usuario:
    return criar_usuario(email="admin@exemplo.test", administrador=True)


def cabecalhos(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


def criar_solicitacao(
    solicitante: Usuario,
    *,
    titulo: str,
    situacao: str = "pendente",
    criado_em: datetime | None = None,
):
    return SolicitacaoRepository.criar(
        solicitante_id=solicitante.id,
        situacao=situacao,
        titulo=titulo,
        ano=2026,
        identificador_pagina=f"sol-{uuid.uuid4().hex[:8]}",
        data_inicio=date(2026, 5, 1),
        data_termino=date(2026, 5, 3),
        versao=1,
        **({} if criado_em is None else {"criado_em": criado_em}),
    )


def em(dia: int) -> datetime:
    return datetime(2026, 3, dia, 12, 0, tzinfo=timezone.utc)


def consultar(cliente, usuario: Usuario | None = None, consulta: str = ""):
    return cliente.get(
        ROTA + consulta, headers={} if usuario is None else cabecalhos(usuario)
    )


# AC1 — 200 com todas as solicitacoes ordenadas por `criadoEm` **crescente**.


def test_a_fila_ordena_por_criado_em_crescente(cliente, sessao):
    administrador = criar_administrador()
    solicitante = criar_usuario()
    # Criadas fora de ordem de proposito: a ordem da resposta vem da coluna,
    # nao da ordem de insercao.
    criar_solicitacao(solicitante, titulo="Do meio", criado_em=em(2))
    criar_solicitacao(solicitante, titulo="A última", criado_em=em(3))
    criar_solicitacao(solicitante, titulo="A primeira", criado_em=em(1))

    resposta = consultar(cliente, administrador)

    assert resposta.status_code == 200
    assert [entrada["titulo"] for entrada in resposta.get_json()] == [
        "A primeira",
        "Do meio",
        "A última",
    ]


def test_a_fila_traz_a_solicitacao_com_os_campos_do_contrato(cliente, sessao):
    administrador = criar_administrador()
    solicitante = criar_usuario()
    solicitacao = criar_solicitacao(solicitante, titulo="Simpósio")

    corpo = consultar(cliente, administrador).get_json()

    assert len(corpo) == 1
    assert corpo[0]["id"] == str(solicitacao.id)
    assert corpo[0]["solicitanteId"] == str(solicitante.id)
    assert corpo[0]["situacao"] == "pendente"
    assert corpo[0]["versao"] == 1


# AC2 — `?status=` filtra; sem o parametro, a fila traz todas as situacoes.


def test_a_fila_filtrada_por_status_traz_so_as_daquela_situacao(cliente, sessao):
    administrador = criar_administrador()
    solicitante = criar_usuario()
    criar_solicitacao(solicitante, titulo="Pendente", situacao="pendente")
    criar_solicitacao(solicitante, titulo="Aprovada", situacao="aprovada")
    criar_solicitacao(solicitante, titulo="Recusada", situacao="recusada")

    corpo = consultar(cliente, administrador, "?status=pendente").get_json()

    assert [entrada["titulo"] for entrada in corpo] == ["Pendente"]


def test_a_fila_sem_o_parametro_status_traz_todas_as_situacoes(cliente, sessao):
    administrador = criar_administrador()
    solicitante = criar_usuario()
    criar_solicitacao(solicitante, titulo="Pendente", situacao="pendente", criado_em=em(1))
    criar_solicitacao(solicitante, titulo="Aprovada", situacao="aprovada", criado_em=em(2))
    criar_solicitacao(solicitante, titulo="Recusada", situacao="recusada", criado_em=em(3))

    corpo = consultar(cliente, administrador).get_json()

    assert [entrada["situacao"] for entrada in corpo] == [
        "pendente",
        "aprovada",
        "recusada",
    ]


def test_a_fila_vazia_responde_200_com_lista_vazia(cliente, sessao):
    resposta = consultar(cliente, criar_administrador())

    assert resposta.status_code == 200
    assert resposta.get_json() == []


# AD-008 — a fila e do administrador; qualquer outro usuario recebe 403.


def test_a_fila_para_quem_nao_e_administrador_responde_403(cliente, sessao):
    solicitante = criar_usuario()
    criar_solicitacao(solicitante, titulo="Não deve vazar")

    resposta = consultar(cliente, solicitante)

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_a_fila_sem_token_responde_401_nao_autenticado(cliente, sessao):
    resposta = consultar(cliente)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
