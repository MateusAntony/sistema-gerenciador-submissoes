"""Testes de ponta a ponta da edicao e da listagem das proprias solicitacoes.

API-11 AC6..AC8 e API-09 AC6 (T30): quem edita, o que acontece depois de
decidida, e a garantia de que a lista do `me` nao vaza solicitacao alheia.
"""

import uuid
from datetime import date, datetime, timezone

from flask_jwt_extended import create_access_token

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.repository import SolicitacaoRepository

ROTA_DA_LISTA = "/api/me/solicitacoes-evento"


def rota_da_edicao(solicitacao_id) -> str:
    return f"/api/solicitacoes-evento/{solicitacao_id}"


def criar_usuario(email: str = "organizador@exemplo.test") -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    return usuario


def cabecalhos(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


def criar_solicitacao(
    solicitante: Usuario,
    *,
    situacao: str = "pendente",
    decidido_por: Usuario | None = None,
    titulo: str = "Simpósio de Extensão",
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
        decidido_por_id=None if decidido_por is None else decidido_por.id,
        decidido_em=(
            None
            if decidido_por is None
            else datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
        ),
    )


# AC6 — PATCH pendente pelo proprio solicitante aplica e incrementa `versao`.


def test_a_edicao_pelo_solicitante_aplica_e_incrementa_a_versao(cliente, sessao):
    dono = criar_usuario()
    solicitacao = criar_solicitacao(dono)

    resposta = cliente.patch(
        rota_da_edicao(solicitacao.id),
        json={"titulo": "Simpósio Renomeado"},
        headers=cabecalhos(dono),
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["titulo"] == "Simpósio Renomeado"
    assert corpo["versao"] == 2
    assert corpo["situacao"] == "pendente"


def test_a_edicao_persiste_a_alteracao_no_banco(cliente, sessao):
    dono = criar_usuario()
    solicitacao = criar_solicitacao(dono)

    cliente.patch(
        rota_da_edicao(solicitacao.id),
        json={"titulo": "Título Persistido"},
        headers=cabecalhos(dono),
    )

    assert SolicitacaoRepository.por_id(solicitacao.id).titulo == "Título Persistido"


def test_a_edicao_deixa_intacto_o_campo_que_nao_foi_enviado(cliente, sessao):
    dono = criar_usuario()
    solicitacao = criar_solicitacao(dono, titulo="Título Original")

    corpo = cliente.patch(
        rota_da_edicao(solicitacao.id),
        json={"cidade": "Feira de Santana"},
        headers=cabecalhos(dono),
    ).get_json()

    assert corpo["cidade"] == "Feira de Santana"
    assert corpo["titulo"] == "Título Original"


# AC7 — PATCH em solicitacao ja decidida e 409 `solicitacao_ja_decidida`.


def test_a_edicao_de_solicitacao_ja_decidida_responde_409(cliente, sessao):
    dono = criar_usuario()
    administrador = criar_usuario(email="admin@exemplo.test")
    solicitacao = criar_solicitacao(
        dono, situacao="aprovada", decidido_por=administrador
    )

    resposta = cliente.patch(
        rota_da_edicao(solicitacao.id),
        json={"titulo": "Tentativa Tardia"},
        headers=cabecalhos(dono),
    )

    assert resposta.status_code == 409
    assert resposta.get_json()["codigo"] == "solicitacao_ja_decidida"


def test_a_edicao_de_solicitacao_ja_decidida_nao_altera_nada(cliente, sessao):
    dono = criar_usuario()
    solicitacao = criar_solicitacao(
        dono, situacao="recusada", titulo="Título Congelado"
    )

    cliente.patch(
        rota_da_edicao(solicitacao.id),
        json={"titulo": "Tentativa Tardia"},
        headers=cabecalhos(dono),
    )

    gravada = SolicitacaoRepository.por_id(solicitacao.id)
    assert gravada.titulo == "Título Congelado"
    assert gravada.versao == 1


# API-09 AC6 — PATCH por quem nao e o solicitante e 403.


def test_a_edicao_por_quem_nao_e_o_solicitante_responde_403(cliente, sessao):
    dono = criar_usuario()
    intruso = criar_usuario(email="intruso@exemplo.test")
    solicitacao = criar_solicitacao(dono, titulo="Título do Dono")

    resposta = cliente.patch(
        rota_da_edicao(solicitacao.id),
        json={"titulo": "Título do Intruso"},
        headers=cabecalhos(intruso),
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert SolicitacaoRepository.por_id(solicitacao.id).titulo == "Título do Dono"


def test_a_edicao_sem_token_responde_401(cliente, sessao):
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.patch(
        rota_da_edicao(solicitacao.id), json={"titulo": "Sem Sessão"}
    )

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_edicao_de_solicitacao_inexistente_responde_404(cliente, sessao):
    resposta = cliente.patch(
        rota_da_edicao(uuid.uuid4()),
        json={"titulo": "Fantasma"},
        headers=cabecalhos(criar_usuario()),
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "solicitacao_inexistente"


# AC8 — `GET /me/solicitacoes-evento` devolve **so** as do proprio usuario.


def test_a_lista_do_me_traz_so_as_solicitacoes_do_proprio_usuario(cliente, sessao):
    dono = criar_usuario()
    outro = criar_usuario(email="outro@exemplo.test")
    minha = criar_solicitacao(dono, titulo="Minha")
    criar_solicitacao(outro, titulo="Alheia")

    corpo = cliente.get(ROTA_DA_LISTA, headers=cabecalhos(dono)).get_json()

    assert [entrada["id"] for entrada in corpo] == [str(minha.id)]
    assert corpo[0]["titulo"] == "Minha"


def test_a_lista_do_me_sem_solicitacao_alguma_devolve_lista_vazia(cliente, sessao):
    resposta = cliente.get(ROTA_DA_LISTA, headers=cabecalhos(criar_usuario()))

    assert resposta.status_code == 200
    assert resposta.get_json() == []


def test_a_lista_do_me_sem_token_responde_401(cliente, sessao):
    resposta = cliente.get(ROTA_DA_LISTA)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
