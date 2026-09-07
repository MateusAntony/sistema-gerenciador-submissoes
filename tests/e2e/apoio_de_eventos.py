"""Apoio comum aos testes e2e da configuracao do evento (Fase 6).

Cria usuario, evento e participacao direto pelo repositorio: o caminho HTTP de
criacao de evento passa pela aprovacao de solicitacao, que ja tem os proprios
testes e so acrescentaria ruido aqui.
"""

import uuid
from datetime import date

from flask_jwt_extended import create_access_token

from app.extensions import db
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import ParticipacaoRepository


def criar_usuario(
    email: str | None = None, *, administrador: bool = False
) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=email or f"pessoa-{uuid.uuid4().hex[:8]}@exemplo.test",
        senha_hash="hash-irrelevante",
    )
    usuario.email_confirmado = True
    usuario.administrador = administrador
    return usuario


def cabecalhos(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


def criar_evento(
    *,
    titulo: str = "Simpósio de Extensão",
    identificador: str | None = None,
    situacao: str = "aprovado",
    evento_pai_id: uuid.UUID | None = None,
    **campos,
) -> Evento:
    evento = Evento(
        situacao=situacao,
        titulo=titulo,
        sigla="SEXT",
        ano=2026,
        identificador_pagina=identificador or f"evt-{uuid.uuid4().hex[:8]}",
        tipo="conferencia",
        cidade="Feira de Santana",
        estado="Bahia",
        pais="Brasil",
        fuso="America/Bahia",
        data_inicio=date(2026, 5, 1),
        data_termino=date(2026, 5, 3),
        evento_pai_id=evento_pai_id,
        modelo_avaliacao="aberta",
        avaliadores_por_submissao=1,
        rebuttal_habilitado=False,
        maximo_rodadas=1,
        versao=1,
        **campos,
    )
    db.session.add(evento)
    db.session.flush()
    return evento


def criar_chair(evento: Evento, email: str | None = None) -> Usuario:
    """Um usuario com participacao de chair naquele evento (AD-008)."""
    usuario = criar_usuario(email)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    return usuario
