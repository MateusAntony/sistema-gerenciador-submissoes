"""Testes de ponta a ponta de `GET /api/convites/{token}` — API-08 AC1..AC6 (T26).

Seis desfechos: o 200 sem sessao, as duas formas de `tipo` (D3), os tres erros
com o contato no corpo (D4) e o `precisaCriarConta`.
"""

import uuid
from datetime import timedelta

from app.extensions import bcrypt, db
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import agora, hash_do_token
from app.modules.convites.repository import ConviteRepository
from app.modules.convites.service import (
    MENSAGEM_DE_CONVITE_EXPIRADO,
    MENSAGEM_DE_CONVITE_INVALIDO,
    MENSAGEM_DE_CONVITE_JA_USADO,
    VALIDADE_DO_CONVITE_EM_DIAS,
    ConviteService,
)
from app.modules.eventos.models import Evento

ROTA = "/api/convites/{token}"
EMAIL = "convidada@exemplo.test"
CONTATO = "organizacao@exemplo.br"

CAMPOS_DE_PARTICIPACAO = {
    "tipo",
    "email",
    "eventoTitulo",
    "prazo",
    "fuso",
    "contatoDaOrganizacao",
    "precisaCriarConta",
}


def criar_evento(
    sessao, titulo: str = "Congresso de Computação", fuso: str = "America/Bahia"
) -> Evento:
    evento = Evento(
        situacao="aprovado",
        titulo=titulo,
        ano=2026,
        identificador_pagina=f"evento-{uuid.uuid4().hex[:8]}",
        fuso=fuso,
    )
    sessao.add(evento)
    sessao.flush()
    return evento


def criar_convite_de_participacao(sessao, email: str = EMAIL):
    evento = criar_evento(sessao)
    convite, token = ConviteService.criar_para_participacao(evento, email, "chair")
    convite.contato_organizacao = CONTATO
    sessao.flush()
    return convite, token


def criar_convite_de_avaliacao(
    sessao, *, submissao_titulo: str = "Um estudo sobre grafos"
):
    evento = criar_evento(sessao)
    token = "token-de-avaliacao"
    convite = ConviteRepository.criar(
        token_hash=hash_do_token(token),
        tipo="avaliacao",
        email=EMAIL,
        evento_id=evento.id,
        papel="avaliador",
        submissao_id=uuid.uuid4(),
        prazo=agora() + timedelta(days=VALIDADE_DO_CONVITE_EM_DIAS),
        contato_organizacao=CONTATO,
    )
    convite.submissao_titulo = submissao_titulo
    sessao.flush()
    return convite, token


def criar_conta(email: str = EMAIL) -> None:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=email,
        senha_hash=bcrypt.generate_password_hash("senha-bem-forte-1").decode("utf-8"),
    )
    usuario.email_confirmado = True
    db.session.flush()


def consultar(cliente, token: str):
    return cliente.get(ROTA.format(token=token))


# AC1 — 200 **sem sessao**, com `tipo` e os demais campos do contrato.


def test_o_convite_e_consultado_sem_qualquer_sessao(cliente, sessao):
    convite, token = criar_convite_de_participacao(sessao)

    resposta = consultar(cliente, token)

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["tipo"] == "participacao"
    assert corpo["email"] == EMAIL
    assert corpo["eventoTitulo"] == "Congresso de Computação"
    assert corpo["fuso"] == "America/Bahia"
    assert corpo["contatoDaOrganizacao"] == CONTATO
    assert corpo["prazo"].endswith("Z")
    assert convite.token_hash not in resposta.get_data(as_text=True)


def test_o_convite_de_participacao_traz_exatamente_os_campos_do_contrato(
    cliente, sessao
):
    _, token = criar_convite_de_participacao(sessao)

    corpo = consultar(cliente, token).get_json()

    assert set(corpo) == CAMPOS_DE_PARTICIPACAO


# AC6 e D3 — `submissaoTitulo` ausente em `participacao`, presente em `avaliacao`.


def test_convite_de_participacao_nao_traz_submissao_titulo(cliente, sessao):
    _, token = criar_convite_de_participacao(sessao)

    corpo = consultar(cliente, token).get_json()

    # Ausente, nao nulo: o front distingue os dois.
    assert "submissaoTitulo" not in corpo


def test_convite_de_avaliacao_traz_submissao_titulo_nao_vazio(cliente, sessao):
    _, token = criar_convite_de_avaliacao(sessao)

    corpo = consultar(cliente, token).get_json()

    assert corpo["tipo"] == "avaliacao"
    assert corpo["submissaoTitulo"] == "Um estudo sobre grafos"


# AC5 — `precisaCriarConta` verdadeiro so quando o e-mail nao tem conta.


def test_precisa_criar_conta_e_verdadeiro_quando_o_email_nao_tem_conta(
    cliente, sessao
):
    _, token = criar_convite_de_participacao(sessao)

    assert consultar(cliente, token).get_json()["precisaCriarConta"] is True


def test_precisa_criar_conta_e_falso_quando_o_email_ja_tem_conta(cliente, sessao):
    _, token = criar_convite_de_participacao(sessao)
    criar_conta()

    assert consultar(cliente, token).get_json()["precisaCriarConta"] is False


def test_a_conta_de_outro_email_nao_afeta_precisa_criar_conta(cliente, sessao):
    _, token = criar_convite_de_participacao(sessao)
    criar_conta(email="outra@exemplo.test")

    assert consultar(cliente, token).get_json()["precisaCriarConta"] is True


# AC2 — token inexistente: 404 `convite_invalido` com o contato no corpo (D4).


def test_token_inexistente_responde_404_convite_invalido(cliente, sessao):
    resposta = consultar(cliente, "token-que-nunca-existiu")

    assert resposta.status_code == 404
    corpo = resposta.get_json()
    assert corpo["codigo"] == "convite_invalido"
    assert corpo["mensagem"] == MENSAGEM_DE_CONVITE_INVALIDO
    assert corpo["contatoDaOrganizacao"] == "contato@sgs.local"
    assert "campos" not in corpo
    assert "correlacao" in corpo


# AC3 — convite expirado: 410 `convite_expirado` com o contato no corpo (D4).


def test_convite_com_prazo_vencido_responde_410_convite_expirado(cliente, sessao):
    convite, token = criar_convite_de_participacao(sessao)
    convite.prazo = agora() - timedelta(seconds=1)
    db.session.flush()

    resposta = consultar(cliente, token)

    assert resposta.status_code == 410
    corpo = resposta.get_json()
    assert corpo["codigo"] == "convite_expirado"
    assert corpo["mensagem"] == MENSAGEM_DE_CONVITE_EXPIRADO
    assert corpo["contatoDaOrganizacao"] == CONTATO
    assert "campos" not in corpo


def test_convite_marcado_expirado_responde_410_convite_expirado(cliente, sessao):
    convite, token = criar_convite_de_participacao(sessao)
    convite.situacao = "expirado"
    db.session.flush()

    resposta = consultar(cliente, token)

    assert resposta.status_code == 410
    assert resposta.get_json()["codigo"] == "convite_expirado"


# AC4 — convite ja aceito: 409 `convite_ja_usado` com o contato no corpo (D4).


def test_convite_ja_aceito_responde_409_convite_ja_usado(cliente, sessao):
    convite, token = criar_convite_de_participacao(sessao)
    convite.situacao = "aceito"
    db.session.flush()

    resposta = consultar(cliente, token)

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "convite_ja_usado"
    assert corpo["mensagem"] == MENSAGEM_DE_CONVITE_JA_USADO
    assert corpo["contatoDaOrganizacao"] == CONTATO
    assert "campos" not in corpo


def test_convite_aceito_e_vencido_continua_respondendo_409_ja_usado(cliente, sessao):
    convite, token = criar_convite_de_participacao(sessao)
    convite.situacao = "aceito"
    convite.prazo = agora() - timedelta(days=1)
    db.session.flush()

    resposta = consultar(cliente, token)

    assert resposta.status_code == 409
    assert resposta.get_json()["codigo"] == "convite_ja_usado"
