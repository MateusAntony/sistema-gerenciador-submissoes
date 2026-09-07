"""Borda HTTP das solicitacoes de evento (API-11, API-12)."""

from flask import Blueprint, jsonify, request

from app.core.erros import SemPermissao
from app.core.permissoes import (
    Acao,
    exige_acao,
    exige_autenticacao,
    usuario_autenticado,
)
from app.core.unidade_de_trabalho import transacao
from app.modules.eventos.repository import SolicitacaoRepository
from app.modules.eventos.schemas import (
    DecisaoDeAprovacao,
    EdicaoDeSolicitacao,
    RecusaDeSolicitacao,
    SolicitacaoDeEntrada,
)
from app.modules.eventos.services.solicitacao import SolicitacaoService

solicitacoes_bp = Blueprint("solicitacoes", __name__, url_prefix="/api")


@solicitacoes_bp.post("/solicitacoes-evento")
@exige_autenticacao
def criar():
    """201 com a solicitacao completa, `pendente` e `versao: 1` (API-11 AC1)."""
    dados = SolicitacaoDeEntrada.model_validate(request.get_json(silent=True) or {})

    with transacao():
        solicitacao = SolicitacaoService.criar(usuario_autenticado().id, dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = SolicitacaoService.projetar(solicitacao).para_json()

    return jsonify(corpo), 201


@solicitacoes_bp.patch("/solicitacoes-evento/<uuid:solicitacao_id>")
@exige_autenticacao
def editar(solicitacao_id):
    """200 com a solicitacao na versao seguinte (API-11 AC6, AC7, API-09 AC6)."""
    dados = EdicaoDeSolicitacao.model_validate(request.get_json(silent=True) or {})

    # As tres recusas sao decididas **antes** de a transacao abrir: sao leituras,
    # e abortar dentro dela desfaria a transacao da requisicao sem necessidade.
    solicitacao = SolicitacaoService.exigir_existente(solicitacao_id)

    # Editar solicitacao alheia e 403: o dono e quem decide o que e dele.
    if solicitacao.solicitante_id != usuario_autenticado().id:
        raise SemPermissao

    SolicitacaoService.exigir_pendente(solicitacao)

    with transacao():
        SolicitacaoService.editar(solicitacao, dados)
        corpo = SolicitacaoService.projetar(solicitacao).para_json()

    return jsonify(corpo), 200


@solicitacoes_bp.get("/me/solicitacoes-evento")
@exige_autenticacao
def minhas():
    """200 com **so** as solicitacoes do proprio usuario (API-11 AC8)."""
    solicitacoes = SolicitacaoRepository.por_solicitante(usuario_autenticado().id)

    return jsonify(
        [
            SolicitacaoService.projetar(solicitacao).para_json()
            for solicitacao in solicitacoes
        ]
    ), 200


@solicitacoes_bp.get("/admin/solicitacoes-evento")
@exige_acao(Acao.APROVAR_SOLICITACAO_EVENTO)
def fila():
    """200 por `criadoEm` crescente, filtrando por `status` (API-12 AC1, AC2)."""
    situacao = request.args.get("status")
    solicitacoes = SolicitacaoRepository.listar(situacao)

    return jsonify(
        [
            SolicitacaoService.projetar(solicitacao).para_json()
            for solicitacao in solicitacoes
        ]
    ), 200


@solicitacoes_bp.post("/admin/solicitacoes-evento/<uuid:solicitacao_id>/aprovar")
@exige_acao(Acao.APROVAR_SOLICITACAO_EVENTO)
def aprovar(solicitacao_id):
    """200 `{ solicitacao, evento }`; 409 se ja decidida (API-12 AC3, AC7)."""
    with transacao():
        solicitacao, evento = SolicitacaoService.aprovar(
            solicitacao_id, usuario_autenticado().id
        )
        corpo = DecisaoDeAprovacao(
            solicitacao=SolicitacaoService.projetar(solicitacao),
            evento=SolicitacaoService.projetar_evento(evento),
        ).para_json()

    return jsonify(corpo), 200


@solicitacoes_bp.post("/admin/solicitacoes-evento/<uuid:solicitacao_id>/recusar")
@exige_acao(Acao.APROVAR_SOLICITACAO_EVENTO)
def recusar(solicitacao_id):
    """200 com a solicitacao `recusada` e o motivo (API-12 AC5..AC8, AC6b).

    A **checagem de estado vem antes da validacao do corpo**: numa solicitacao
    ja decidida o motivo e irrelevante, e responder 422 mandaria a tela pedir
    "informe o motivo" quando a resposta util e "ja decidida por Fulano em tal
    data" (AC6b).

    A checagem roda numa leitura propria, fora da transacao de escrita. Valida-la
    dentro dela faria o 422 virar excecao no bloco, e o `rollback()` de
    `transacao()` desfaria escritas anteriores da mesma requisicao — validacao de
    corpo nao pode descartar trabalho ja feito. O bloqueio real contra corrida
    continua dentro da transacao, em `recusar`.
    """
    SolicitacaoService.exigir_pendente(
        SolicitacaoService.exigir_existente(solicitacao_id)
    )
    dados = RecusaDeSolicitacao.model_validate(request.get_json(silent=True) or {})

    with transacao():
        solicitacao = SolicitacaoService.bloquear_pendente(solicitacao_id)
        solicitacao = SolicitacaoService.recusar(
            solicitacao, usuario_autenticado().id, dados.motivo
        )
        corpo = SolicitacaoService.projetar(solicitacao).para_json()

    return jsonify(corpo), 200
