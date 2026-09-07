"""Efeitos da aprovacao — API-13 AC1..AC6 e AD-009 (T33).

Aprovar nao e so mudar uma coluna: e o que da ao solicitante o evento que ele
pediu e convida a equipe dele. Os seis casos aqui sao os que fazem
`GET /me/participacoes` deixar de voltar vazio depois da aprovacao.
"""

import uuid
from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.unidade_de_trabalho import transacao
from app.extensions import db
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.convites.models import Convite
from app.modules.emails.models import EmailEnviado
from app.modules.eventos.models import Evento, ParticipacaoEvento, SolicitacaoEvento
from app.modules.eventos.repository import (
    ParticipacaoRepository,
    SolicitacaoRepository,
)
from app.modules.eventos.services.solicitacao import SolicitacaoService


def criar_usuario(email: str) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Pessoa", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    return usuario


def criar_administrador() -> Usuario:
    usuario = criar_usuario("admin@exemplo.test")
    usuario.administrador = True
    return usuario


def criar_solicitacao(solicitante: Usuario, chairs: list[str] | None = None):
    solicitacao = SolicitacaoRepository.criar(
        solicitante_id=solicitante.id,
        situacao="pendente",
        titulo="Simpósio de Extensão",
        ano=2026,
        identificador_pagina=f"sol-{uuid.uuid4().hex[:8]}",
        data_inicio=date(2026, 5, 1),
        data_termino=date(2026, 5, 3),
        versao=1,
    )
    if chairs:
        SolicitacaoRepository.definir_chairs_iniciais(solicitacao.id, chairs)
    return solicitacao


def papeis(evento_id, usuario_id) -> list[str]:
    return ParticipacaoRepository.papeis_no_evento(usuario_id, evento_id)


def convites_de(evento_id, email: str) -> list[Convite]:
    return list(
        db.session.scalars(
            select(Convite).where(
                Convite.evento_id == evento_id, Convite.email == email
            )
        )
    )


def contar(modelo) -> int:
    return db.session.scalar(select(func.count()).select_from(modelo))


# AC1 — o solicitante vira chair ativo do evento criado.


def test_o_solicitante_vira_chair_ativo_do_evento_criado(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante)

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    assert papeis(evento.id, solicitante.id) == ["chair"]


def test_a_participacao_do_solicitante_aparece_em_me_participacoes(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante)

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    listadas = ParticipacaoRepository.por_usuario(solicitante.id)
    assert [entrada.evento_id for entrada in listadas] == [evento.id]
    assert listadas[0].papeis == ["chair"]


# AC2 — chair inicial **com** conta vira participacao.


def test_o_chair_inicial_com_conta_vira_participacao_de_chair(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    ana = criar_usuario("ana@exemplo.test")
    solicitacao = criar_solicitacao(solicitante, ["ana@exemplo.test"])

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    assert papeis(evento.id, ana.id) == ["chair"]
    assert convites_de(evento.id, "ana@exemplo.test") == []


# AC3 — chair inicial **sem** conta vira convite de participacao com e-mail.


def test_o_chair_inicial_sem_conta_vira_convite_de_participacao(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante, ["sem-conta@exemplo.test"])

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    convites = convites_de(evento.id, "sem-conta@exemplo.test")
    assert len(convites) == 1
    assert convites[0].tipo == "participacao"
    assert convites[0].papel == "chair"
    assert convites[0].situacao == "pendente"
    # D3 — convite de participacao nao tem submissao atras.
    assert convites[0].submissao_id is None
    assert convites[0].token_hash


def test_o_convite_do_chair_sem_conta_dispara_o_email(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante, ["sem-conta@exemplo.test"])

    SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    enviados = list(
        db.session.scalars(
            select(EmailEnviado).where(
                EmailEnviado.destinatario == "sem-conta@exemplo.test"
            )
        )
    )
    assert len(enviados) == 1
    assert enviados[0].situacao == "enviado"


def test_a_aprovacao_com_um_chair_de_cada_tipo_cria_uma_participacao_e_um_convite(
    sessao,
):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    bia = criar_usuario("bia@exemplo.test")
    solicitacao = criar_solicitacao(
        solicitante, ["bia@exemplo.test", "sem-conta@exemplo.test"]
    )

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    assert papeis(evento.id, bia.id) == ["chair"]
    assert len(convites_de(evento.id, "sem-conta@exemplo.test")) == 1
    assert convites_de(evento.id, "bia@exemplo.test") == []


# AC6 — o mesmo e-mail duas vezes produz **um** efeito so.


def test_o_email_repetido_com_conta_produz_uma_participacao_so(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    ana = criar_usuario("ana@exemplo.test")
    solicitacao = criar_solicitacao(solicitante)
    # A constraint impede o par repetido na tabela; a lista chega aqui com o
    # e-mail repetido do mesmo jeito quando o front reenvia o formulario.
    SolicitacaoRepository.definir_chairs_iniciais(
        solicitacao.id, ["ana@exemplo.test", "ana@exemplo.test"]
    )

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    participacoes = db.session.scalar(
        select(func.count())
        .select_from(ParticipacaoEvento)
        .where(
            ParticipacaoEvento.evento_id == evento.id,
            ParticipacaoEvento.usuario_id == ana.id,
        )
    )
    assert participacoes == 1


def test_o_email_do_solicitante_repetido_nos_chairs_nao_gera_convite(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante, ["organizador@exemplo.test"])

    _, evento = SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    assert convites_de(evento.id, "organizador@exemplo.test") == []
    participacoes = db.session.scalar(
        select(func.count())
        .select_from(ParticipacaoEvento)
        .where(
            ParticipacaoEvento.evento_id == evento.id,
            ParticipacaoEvento.usuario_id == solicitante.id,
        )
    )
    assert participacoes == 1


# AC4 — falha em qualquer etapa nao persiste nada.


def test_a_falha_no_meio_da_aprovacao_nao_persiste_linha_alguma(sessao, monkeypatch):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante, ["sem-conta@exemplo.test"])
    sessao.commit()

    eventos_antes = contar(Evento)
    participacoes_antes = contar(ParticipacaoEvento)
    convites_antes = contar(Convite)

    def explodir(*args, **kwargs):
        raise RuntimeError("falha simulada no meio da aprovação")

    # O convite e a ultima etapa: quando ela falha, o evento e a participacao
    # do solicitante ja foram gravados na sessao — e e exatamente isso que a
    # transacao unica precisa desfazer (AD-019).
    monkeypatch.setattr(
        "app.modules.eventos.services.solicitacao.ConviteService"
        ".criar_para_participacao",
        explodir,
    )

    with pytest.raises(RuntimeError), transacao():
        SolicitacaoService.aprovar(solicitacao.id, administrador.id)

    assert contar(Evento) == eventos_antes
    assert contar(ParticipacaoEvento) == participacoes_antes
    assert contar(Convite) == convites_antes
    assert (
        db.session.get(SolicitacaoEvento, solicitacao.id).situacao == "pendente"
    )


# AC5 — falha no envio do e-mail **nao** desfaz a aprovacao.


def test_a_falha_no_envio_do_email_nao_desfaz_a_aprovacao(sessao, monkeypatch):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante, ["sem-conta@exemplo.test"])

    class BackendQueFalha:
        @staticmethod
        def enviar(destinatario, assunto, corpo):
            raise RuntimeError("SMTP fora do ar")

    from flask import current_app

    from app.modules.emails.backends import CHAVE_DO_BACKEND

    monkeypatch.setitem(
        current_app.extensions, CHAVE_DO_BACKEND, BackendQueFalha()
    )

    solicitacao_decidida, evento = SolicitacaoService.aprovar(
        solicitacao.id, administrador.id
    )

    assert solicitacao_decidida.situacao == "aprovada"
    assert evento.situacao == "aprovado"
    assert len(convites_de(evento.id, "sem-conta@exemplo.test")) == 1
    assert papeis(evento.id, solicitante.id) == ["chair"]

    registro = db.session.scalars(
        select(EmailEnviado).where(
            EmailEnviado.destinatario == "sem-conta@exemplo.test"
        )
    ).first()
    assert registro.situacao == "falha"


# Edge Case — reprocessar a aprovacao nao duplica participacao.


def test_reprocessar_os_efeitos_nao_duplica_a_participacao_do_solicitante(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    ana = criar_usuario("ana@exemplo.test")
    solicitacao = criar_solicitacao(solicitante, ["ana@exemplo.test"])

    solicitacao_decidida, evento = SolicitacaoService.aprovar(
        solicitacao.id, administrador.id
    )

    # Reprocessamento: os mesmos efeitos aplicados de novo sobre o mesmo evento.
    SolicitacaoService._aplicar_efeitos(solicitacao_decidida, evento)

    total = db.session.scalar(
        select(func.count())
        .select_from(ParticipacaoEvento)
        .where(ParticipacaoEvento.evento_id == evento.id)
    )
    assert total == 2
    assert papeis(evento.id, solicitante.id) == ["chair"]
    assert papeis(evento.id, ana.id) == ["chair"]


def test_reprocessar_os_efeitos_nao_emite_um_segundo_convite(sessao):
    solicitante = criar_usuario("organizador@exemplo.test")
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(solicitante, ["sem-conta@exemplo.test"])

    solicitacao_decidida, evento = SolicitacaoService.aprovar(
        solicitacao.id, administrador.id
    )
    SolicitacaoService._aplicar_efeitos(solicitacao_decidida, evento)

    assert len(convites_de(evento.id, "sem-conta@exemplo.test")) == 1
