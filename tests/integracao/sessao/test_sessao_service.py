"""Emissao, rotacao e invalidacao de familia — API-04 AC1, AC3, AD-017 (T15)."""

import hashlib
from datetime import timedelta

from flask_jwt_extended import decode_token
from sqlalchemy import select

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import agora
from app.modules.sessao.models import Sessao
from app.modules.sessao.service import SessaoService

TOLERANCIA = timedelta(seconds=30)


def criar_usuario(email="sessao@exemplo.test") -> Usuario:
    return ContaRepository.criar(nome="Ada", email=email, senha_hash="hash")


def sessoes(sessao) -> list[Sessao]:
    return list(sessao.scalars(select(Sessao).order_by(Sessao.criado_em)))


def sessao_do_token(sessao, token: str) -> Sessao | None:
    esperado = hashlib.sha256(token.encode("utf-8")).hexdigest()
    return sessao.scalars(
        select(Sessao).where(Sessao.token_hash == esperado)
    ).first()


# Criterio 1 — emitir cria linha com familia, token_hash SHA-256 e expira_em de 14 dias.


def test_emitir_grava_a_sessao_com_familia_e_sha256_do_token(sessao):
    usuario = criar_usuario()

    token = SessaoService.emitir(usuario)

    gravadas = sessoes(sessao)
    assert len(gravadas) == 1
    assert gravadas[0].usuario_id == usuario.id
    assert gravadas[0].familia is not None
    assert (
        gravadas[0].token_hash
        == hashlib.sha256(token.encode("utf-8")).hexdigest()
    )


def test_a_renovacao_emitida_expira_em_14_dias(sessao):
    usuario = criar_usuario()

    SessaoService.emitir(usuario)

    esperado = agora() + timedelta(days=14)
    assert abs(sessoes(sessao)[0].expira_em - esperado) < TOLERANCIA


# Criterio 5 — o valor cru do token de renovacao nao aparece em nenhuma coluna.


def test_o_valor_cru_do_token_de_renovacao_nao_aparece_em_nenhuma_coluna(sessao):
    usuario = criar_usuario()

    token = SessaoService.emitir(usuario)

    valores = [
        str(getattr(linha, coluna.name))
        for linha in sessoes(sessao)
        for coluna in Sessao.__table__.columns
    ]
    assert [valor for valor in valores if token in valor] == []


# Criterio 2 — rotacionar marca o anterior e cria o proximo na mesma familia.


def test_renovar_marca_o_anterior_como_rotacionado_e_segue_na_mesma_familia(sessao):
    usuario = criar_usuario()
    primeiro = SessaoService.emitir(usuario)

    _, segundo = SessaoService.renovar(primeiro)

    anterior = sessao_do_token(sessao, primeiro)
    proxima = sessao_do_token(sessao, segundo)
    assert anterior.rotacionado_em is not None
    assert proxima is not None
    assert proxima.rotacionado_em is None
    assert proxima.familia == anterior.familia
    assert len(sessoes(sessao)) == 2


# Criterio 3 — apresentar token ja rotacionado invalida toda a familia (3 rotacoes).


def test_reapresentar_token_rotacionado_invalida_toda_a_familia(sessao):
    usuario = criar_usuario()
    primeiro = SessaoService.emitir(usuario)
    _, segundo = SessaoService.renovar(primeiro)
    _, terceiro = SessaoService.renovar(segundo)
    _, corrente = SessaoService.renovar(terceiro)

    # O token roubado e reapresentado depois de ja ter sido trocado.
    assert SessaoService.renovar(primeiro) is None

    # A familia inteira cai: o token corrente, que ninguem reapresentou, tambem
    # deixa de renovar. Invalidar so o token apresentado nao satisfaz a AC3.
    assert SessaoService.renovar(corrente) is None
    gravadas = sessoes(sessao)
    assert len(gravadas) == 4
    assert [linha.revogada_em is not None for linha in gravadas] == [True] * 4


# Criterio 4 — o token de acesso expira em 15 minutos.


def test_o_token_de_acesso_expira_em_15_minutos(sessao):
    usuario = criar_usuario()

    conteudo = decode_token(SessaoService.token_de_acesso(usuario))

    assert conteudo["exp"] - conteudo["iat"] == 15 * 60
    assert conteudo["sub"] == str(usuario.id)
