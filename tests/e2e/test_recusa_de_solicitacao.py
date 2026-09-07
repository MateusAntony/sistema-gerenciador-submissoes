"""Testes de ponta a ponta de `POST .../recusar` — API-12 AC5..AC8 (T34).

A recusa e o outro fim do caminho da solicitacao. O motivo e obrigatorio porque
e ele que a tela mostra ao solicitante; e a recusa nao pode deixar rastro de
evento nem de participacao.
"""

import uuid
from datetime import date, datetime, timezone

from flask_jwt_extended import create_access_token
from sqlalchemy import func, select

from app.extensions import db
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento, ParticipacaoEvento
from app.modules.eventos.repository import EventoRepository, SolicitacaoRepository


def rota(solicitacao_id) -> str:
    return f"/api/admin/solicitacoes-evento/{solicitacao_id}/recusar"


def criar_usuario(
    email: str = "organizador@exemplo.test", *, administrador: bool = False
) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    usuario.administrador = administrador
    return usuario


def criar_administrador(email: str = "admin@exemplo.test") -> Usuario:
    return criar_usuario(email=email, administrador=True)


def cabecalhos(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


def criar_solicitacao(
    solicitante: Usuario,
    *,
    situacao: str = "pendente",
    decidido_por: Usuario | None = None,
):
    return SolicitacaoRepository.criar(
        solicitante_id=solicitante.id,
        situacao=situacao,
        titulo="Simpósio de Extensão",
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


def contar(modelo) -> int:
    return db.session.scalar(select(func.count()).select_from(modelo))


# AC5 — 200 com `recusada`, `motivoRecusa`, `decididoPorId` e `decididoEm`.


def test_a_recusa_responde_200_com_a_solicitacao_recusada_e_o_motivo(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Fora do escopo institucional."},
        headers=cabecalhos(administrador),
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["situacao"] == "recusada"
    assert corpo["motivoRecusa"] == "Fora do escopo institucional."
    assert corpo["decididoPorId"] == str(administrador.id)
    assert corpo["decididoEm"].endswith("Z")


def test_a_recusa_persiste_a_situacao_e_o_motivo(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Datas conflitantes."},
        headers=cabecalhos(administrador),
    )

    gravada = SolicitacaoRepository.por_id(solicitacao.id)
    assert gravada.situacao == "recusada"
    assert gravada.motivo_recusa == "Datas conflitantes."
    assert gravada.decidido_por_id == administrador.id


# AC6 — motivo ausente ou vazio e 422 com `campos.motivo`.


def test_a_recusa_sem_motivo_responde_422_em_motivo(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.post(
        rota(solicitacao.id), json={}, headers=cabecalhos(administrador)
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "motivo" in corpo["campos"]
    assert SolicitacaoRepository.por_id(solicitacao.id).situacao == "pendente"


def test_a_recusa_com_motivo_vazio_responde_422_em_motivo(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.post(
        rota(solicitacao.id), json={"motivo": ""}, headers=cabecalhos(administrador)
    )

    assert resposta.status_code == 422
    assert "motivo" in resposta.get_json()["campos"]
    assert SolicitacaoRepository.por_id(solicitacao.id).situacao == "pendente"


# AC7 — recusar solicitacao ja decidida e 409 com quem decidiu e quando.


def test_a_recusa_de_solicitacao_ja_decidida_responde_409_com_quem_decidiu(
    cliente, sessao
):
    administrador = criar_administrador()
    quem_decidiu = criar_administrador(email="outro-admin@exemplo.test")
    solicitacao = criar_solicitacao(
        criar_usuario(), situacao="aprovada", decidido_por=quem_decidiu
    )

    resposta = cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Tentativa tardia."},
        headers=cabecalhos(administrador),
    )

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "solicitacao_ja_decidida"
    assert corpo["decididoPorId"] == str(quem_decidiu.id)
    assert corpo["decididoEm"] == "2026-04-01T12:00:00Z"
    assert corpo["situacao"] == "aprovada"
    assert "correlacao" in corpo
    assert "mensagem" in corpo


def test_a_segunda_recusa_nao_sobrescreve_o_motivo_da_primeira(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Motivo original."},
        headers=cabecalhos(administrador),
    )
    segunda = cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Motivo sobrescrito."},
        headers=cabecalhos(administrador),
    )

    assert segunda.status_code == 409
    assert (
        SolicitacaoRepository.por_id(solicitacao.id).motivo_recusa
        == "Motivo original."
    )


# AC8 — solicitacao inexistente e 404; e a decisao e do administrador.


def test_a_recusa_de_solicitacao_inexistente_responde_404(cliente, sessao):
    resposta = cliente.post(
        rota(uuid.uuid4()),
        json={"motivo": "Qualquer."},
        headers=cabecalhos(criar_administrador()),
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "solicitacao_inexistente"


def test_a_recusa_por_quem_nao_e_administrador_responde_403(cliente, sessao):
    solicitante = criar_usuario()
    solicitacao = criar_solicitacao(solicitante)

    resposta = cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Não pode."},
        headers=cabecalhos(solicitante),
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert SolicitacaoRepository.por_id(solicitacao.id).situacao == "pendente"


def test_a_recusa_sem_token_responde_401(cliente, sessao):
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.post(rota(solicitacao.id), json={"motivo": "Sem sessão."})

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


# A recusa **nao** cria evento nem participacao.


def test_a_recusa_nao_cria_evento_nem_participacao(cliente, sessao):
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())
    eventos_antes = contar(Evento)
    participacoes_antes = contar(ParticipacaoEvento)

    resposta = cliente.post(
        rota(solicitacao.id),
        json={"motivo": "Fora do escopo."},
        headers=cabecalhos(administrador),
    )

    assert resposta.status_code == 200
    assert contar(Evento) == eventos_antes
    assert contar(ParticipacaoEvento) == participacoes_antes
    assert EventoRepository.por_solicitacao(solicitacao.id) is None


# AC6b — o estado tem precedencia sobre a validacao de corpo.


def test_recusa_ja_decidida_e_sem_motivo_responde_409_e_nao_422(cliente, sessao):
    """Os dois erros competem aqui, e o de estado ganha.

    Antes desta regra, a validacao de corpo rodava fora da transacao e vencia:
    a tela pedia "informe o motivo" para uma recusa que nao podia acontecer, em
    vez de dizer quem ja tinha decidido.
    """
    administrador = criar_administrador()
    quem_decidiu = criar_administrador(email="outro-admin@exemplo.test")
    solicitacao = criar_solicitacao(
        criar_usuario(), situacao="aprovada", decidido_por=quem_decidiu
    )

    resposta = cliente.post(
        rota(solicitacao.id), json={}, headers=cabecalhos(administrador)
    )

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "solicitacao_ja_decidida"
    assert corpo["decididoPorId"] == str(quem_decidiu.id)
    assert "campos" not in corpo


def test_recusa_pendente_e_sem_motivo_continua_422(cliente, sessao):
    """A precedencia nao engole a validacao: pendente sem motivo ainda e 422."""
    administrador = criar_administrador()
    solicitacao = criar_solicitacao(criar_usuario())

    resposta = cliente.post(
        rota(solicitacao.id), json={}, headers=cabecalhos(administrador)
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "motivo" in corpo["campos"]
    assert solicitacao.situacao == "pendente"
