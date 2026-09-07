"""Testes do token de confirmacao de e-mail — API-06 AC7, AD-017 (T12)."""

import hashlib
from datetime import timedelta

from sqlalchemy import select

from app.modules.contas.models import TokenConfirmacaoEmail, Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import VALIDADE_DO_TOKEN_EM_HORAS, ContaService
from app.modules.emails.models import EmailEnviado

EMAIL = "token.de.confirmacao@exemplo.test"
SENHA = "senha-bem-forte-1"

CADASTRO = {
    "nome": "Ada Lovelace",
    "email": EMAIL,
    "senha": SENHA,
    "instituicao": "UFPI",
    "pais": "Brasil",
}


def novo_usuario() -> Usuario:
    return ContaRepository.criar(nome="Ada", email=EMAIL, senha_hash="hash")


def tokens_de(sessao, usuario) -> list[TokenConfirmacaoEmail]:
    return list(
        sessao.scalars(
            select(TokenConfirmacaoEmail)
            .where(TokenConfirmacaoEmail.usuario_id == usuario.id)
            .order_by(TokenConfirmacaoEmail.criado_em)
        )
    )


def test_o_banco_guarda_apenas_o_sha256_do_token(sessao):
    usuario = novo_usuario()

    token = ContaService.emitir_token_de_confirmacao(usuario)

    gravado = tokens_de(sessao, usuario)[0]
    assert gravado.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert len(gravado.token_hash) == 64
    assert gravado.token_hash != token


def test_o_token_cru_nao_aparece_em_nenhuma_coluna_da_tabela(sessao):
    usuario = novo_usuario()

    token = ContaService.emitir_token_de_confirmacao(usuario)

    linha = sessao.execute(select(TokenConfirmacaoEmail.__table__)).mappings().one()
    vazamentos = [
        coluna for coluna, valor in linha.items() if token in str(valor)
    ]
    assert vazamentos == []


def test_o_token_cru_viaja_no_corpo_do_email_e_bate_com_o_hash_gravado(
    cliente, sessao, aplicacao
):
    cliente.post("/api/usuarios", json=CADASTRO)

    corpo = sessao.scalars(
        select(EmailEnviado.corpo).where(EmailEnviado.destinatario == EMAIL)
    ).one()
    prefixo = f"{aplicacao.config['URL_DO_FRONT']}/confirmar-email?token="
    assert prefixo in corpo
    token = corpo.split(prefixo, 1)[1].split()[0]
    assert token != ""

    gravado = sessao.scalars(select(TokenConfirmacaoEmail)).one()
    assert gravado.token_hash == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_o_token_expira_em_vinte_e_quatro_horas(sessao):
    usuario = novo_usuario()

    ContaService.emitir_token_de_confirmacao(usuario)

    gravado = tokens_de(sessao, usuario)[0]
    assert VALIDADE_DO_TOKEN_EM_HORAS == 24
    assert gravado.expira_em - gravado.criado_em == timedelta(hours=24)


def test_emitir_novo_token_nao_invalida_o_anterior_em_silencio(sessao):
    usuario = novo_usuario()

    primeiro = ContaService.emitir_token_de_confirmacao(usuario)
    segundo = ContaService.emitir_token_de_confirmacao(usuario)

    gravados = tokens_de(sessao, usuario)
    assert len(gravados) == 2
    assert primeiro != segundo
    # O anterior continua pendente: nenhum sumico e nenhuma invalidacao sem registro.
    assert [token.usado_em for token in gravados] == [None, None]
    assert {token.token_hash for token in gravados} == {
        hashlib.sha256(valor.encode("utf-8")).hexdigest()
        for valor in (primeiro, segundo)
    }
