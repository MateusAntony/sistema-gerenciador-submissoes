"""Testes da criacao de convites — API-08, D3, AD-017 (T25).

O que se afirma aqui: o convite de participacao nasce sem submissao, o banco
guarda so o hash do token, o e-mail sai com a URL completa contendo o token cru,
e o CHECK do banco recusa convite de avaliacao sem submissao.
"""

import uuid

import pytest
from flask import current_app
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.modules.contas.service import hash_do_token
from app.modules.convites.models import Convite
from app.modules.convites.repository import ConviteRepository
from app.modules.convites.service import ConviteService
from app.modules.emails.models import EmailEnviado
from app.modules.emails.service import ASSUNTO_DE_CONVITE
from app.modules.eventos.models import Evento

EMAIL = "convidada@exemplo.test"


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


def emails_enviados(sessao) -> list[EmailEnviado]:
    return list(sessao.scalars(select(EmailEnviado)))


# --- `criar_para_participacao` ----------------------------------------------


def test_o_convite_de_participacao_nasce_sem_submissao(sessao):
    evento = criar_evento(sessao)

    convite, _ = ConviteService.criar_para_participacao(evento, EMAIL, "chair")

    assert convite.tipo == "participacao"
    assert convite.submissao_id is None
    assert convite.evento_id == evento.id
    assert convite.papel == "chair"
    assert convite.email == EMAIL
    assert convite.situacao == "pendente"


def test_o_convite_de_participacao_nasce_com_prazo_e_contato(sessao):
    evento = criar_evento(sessao)

    convite, _ = ConviteService.criar_para_participacao(evento, EMAIL, "chair")

    assert convite.prazo is not None
    assert convite.contato_organizacao == "contato@sgs.local"


# --- Apenas o hash do token e gravado (AD-017) ------------------------------


def test_a_coluna_guarda_o_sha256_do_token_e_nao_o_token(sessao):
    evento = criar_evento(sessao)

    convite, token = ConviteService.criar_para_participacao(evento, EMAIL, "chair")

    assert convite.token_hash == hash_do_token(token)
    assert len(convite.token_hash) == 64
    assert convite.token_hash != token


def test_o_token_cru_nao_aparece_em_nenhuma_coluna_do_convite(sessao):
    evento = criar_evento(sessao)
    convite, token = ConviteService.criar_para_participacao(evento, EMAIL, "chair")

    colunas = [coluna.name for coluna in inspect(Convite).columns]
    linha = sessao.execute(
        text(
            f"SELECT {', '.join(f'{coluna}::text' for coluna in colunas)} "
            "FROM convites WHERE id = :id"
        ).bindparams(id=convite.id)
    ).one()

    assert all(token not in str(valor) for valor in linha)


def test_o_convite_e_encontrado_pelo_hash_do_token_apresentado(sessao):
    evento = criar_evento(sessao)
    convite, token = ConviteService.criar_para_participacao(evento, EMAIL, "chair")

    assert ConviteRepository.por_hash(hash_do_token(token)) is convite
    assert ConviteRepository.por_hash(hash_do_token("outro-token")) is None


# --- E-mail com a URL completa contendo o token cru --------------------------


def test_o_email_de_convite_sai_com_a_url_completa_e_o_token_cru(sessao):
    evento = criar_evento(sessao, titulo="Congresso de Computação")

    _, token = ConviteService.criar_para_participacao(evento, EMAIL, "chair")

    enviados = emails_enviados(sessao)
    assert len(enviados) == 1
    assert enviados[0].destinatario == EMAIL
    assert enviados[0].assunto == ASSUNTO_DE_CONVITE
    origem = current_app.config["URL_DO_FRONT"].rstrip("/")
    assert f"{origem}/convites/{token}" in enviados[0].corpo
    assert "Congresso de Computação" in enviados[0].corpo
    assert enviados[0].situacao == "enviado"


# --- CHECK do banco: convite de avaliacao exige submissao (D3) --------------


def test_convite_de_avaliacao_sem_submissao_viola_o_check(sessao):
    with pytest.raises(IntegrityError) as recusa:
        ConviteRepository.criar(
            token_hash=hash_do_token("token-de-avaliacao"),
            tipo="avaliacao",
            email=EMAIL,
        )

    assert "ck_convites_avaliacao_com_submissao" in str(recusa.value.orig)
    sessao.rollback()


def test_convite_de_avaliacao_com_submissao_e_aceito(sessao):
    convite = ConviteRepository.criar(
        token_hash=hash_do_token("token-de-avaliacao"),
        tipo="avaliacao",
        email=EMAIL,
        submissao_id=uuid.uuid4(),
    )

    assert convite.tipo == "avaliacao"
    assert convite.submissao_id is not None
