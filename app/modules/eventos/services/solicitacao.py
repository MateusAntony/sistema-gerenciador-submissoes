"""Regras da solicitacao de evento — criacao, edicao e decisao (API-11, API-12).

Nada aqui comita: o commit e da unidade de trabalho, uma vez por requisicao
(AD-019). E o que faz a aprovacao — solicitacao, evento, participacoes e
convites — ser uma escrita so (API-13 AC4).
"""

import uuid
from datetime import date, datetime, timezone

from app.core.erros import Conflito, ErroDeValidacao, NaoEncontrado
from app.core.schemas import em_iso_utc
from app.modules.contas.repository import ContaRepository
from app.modules.convites.repository import ConviteRepository
from app.modules.convites.service import ConviteService
from app.modules.eventos.models import Evento, SolicitacaoEvento
from app.modules.eventos.repository import (
    EventoRepository,
    ParticipacaoRepository,
    SolicitacaoRepository,
)
from app.modules.eventos.schemas import (
    ChairInicialDaApi,
    EventoDaApi,
    SolicitacaoDaApi,
)

MENSAGEM_DE_IDENTIFICADOR_EM_USO = "Este identificador já está em uso."
MENSAGEM_DE_TERMINO_ANTES_DO_INICIO = (
    "A data de término não pode ser anterior à de início."
)
MENSAGEM_DE_PAI_INEXISTENTE = "O evento pai informado não existe."
MENSAGEM_DE_CICLO = (
    "O evento pai não pode ser um descendente do próprio evento."
)

MENSAGEM_DE_JA_DECIDIDA = "Esta solicitação já foi decidida."
MENSAGEM_DE_SOLICITACAO_INEXISTENTE = "Solicitação não encontrada."

SITUACAO_PENDENTE = "pendente"
SITUACAO_APROVADO = "aprovado"

# Os padroes com que todo evento nasce da aprovacao (API-12 AC4).
PAPEL_DE_CHAIR = "chair"

MODELO_DE_AVALIACAO_PADRAO = "aberta"
AVALIADORES_POR_SUBMISSAO_PADRAO = 1
REBUTTAL_HABILITADO_PADRAO = False
MAXIMO_DE_RODADAS_PADRAO = 1
SITUACAO_APROVADA = "aprovada"
SITUACAO_RECUSADA = "recusada"


def agora() -> datetime:
    return datetime.now(timezone.utc)


class SolicitacaoService:
    @staticmethod
    def criar(solicitante_id: uuid.UUID, dados) -> SolicitacaoEvento:
        """Cria a solicitacao `pendente` com `versao: 1` (API-11 AC1).

        As quatro validacoes de API-11 rodam antes de qualquer escrita, para o
        422 sair com o campo nomeado em vez de virar erro de integridade.
        """
        SolicitacaoService._validar_identificador(dados.identificador_pagina)
        SolicitacaoService._validar_datas(dados.data_inicio, dados.data_termino)
        SolicitacaoService.validar_evento_pai(dados.evento_pai_id, evento_proprio=None)

        solicitacao = SolicitacaoRepository.criar(
            solicitante_id=solicitante_id,
            situacao=SITUACAO_PENDENTE,
            titulo=dados.titulo,
            sigla=dados.sigla,
            ano=dados.ano or dados.data_inicio.year,
            identificador_pagina=dados.identificador_pagina,
            tipo=dados.tipo,
            cidade=dados.cidade,
            estado=dados.estado,
            pais=dados.pais,
            fuso=dados.fuso,
            data_inicio=dados.data_inicio,
            data_termino=dados.data_termino,
            data_publicacao=dados.data_publicacao,
            justificativa=dados.justificativa,
            evento_pai_id=dados.evento_pai_id,
            versao=1,
        )

        SolicitacaoRepository.definir_chairs_iniciais(
            solicitacao.id, [chair.email for chair in dados.chairs_iniciais]
        )
        return solicitacao

    @staticmethod
    def editar(solicitacao: SolicitacaoEvento, dados) -> SolicitacaoEvento:
        """Aplica a alteracao parcial e incrementa `versao` (API-11 AC6).

        So a solicitacao `pendente` chega aqui: quem ja foi decidida e barrada
        antes, com o 409 que a tela usa para parar de oferecer a edicao (AC7).
        """
        alteracoes = dados.model_dump(exclude_unset=True)

        identificador = alteracoes.get("identificador_pagina")
        if identificador is not None:
            SolicitacaoService._validar_identificador(
                identificador, solicitacao_id=solicitacao.id
            )

        SolicitacaoService._validar_datas(
            alteracoes.get("data_inicio", solicitacao.data_inicio),
            alteracoes.get("data_termino", solicitacao.data_termino),
        )

        if "evento_pai_id" in alteracoes:
            evento = EventoRepository.por_solicitacao(solicitacao.id)
            SolicitacaoService.validar_evento_pai(
                alteracoes["evento_pai_id"],
                evento_proprio=None if evento is None else evento.id,
            )

        chairs = alteracoes.pop("chairs_iniciais", None)
        for campo, valor in alteracoes.items():
            setattr(solicitacao, campo, valor)

        if chairs is not None:
            SolicitacaoRepository.definir_chairs_iniciais(
                solicitacao.id, [chair["email"] for chair in chairs]
            )

        solicitacao.versao += 1
        return solicitacao

    @staticmethod
    def exigir_pendente(solicitacao: SolicitacaoEvento) -> None:
        """409 `solicitacao_ja_decidida` com quem decidiu e quando (API-12 AC7).

        Os tres extras viajam **no corpo**, ao lado de `codigo`, `mensagem` e
        `correlacao`: e o que permite a tela dizer quem decidiu, sem uma segunda
        requisicao.
        """
        if solicitacao.situacao != SITUACAO_PENDENTE:
            raise Conflito(
                "solicitacao_ja_decidida",
                MENSAGEM_DE_JA_DECIDIDA,
                decididoPorId=(
                    None
                    if solicitacao.decidido_por_id is None
                    else str(solicitacao.decidido_por_id)
                ),
                decididoEm=(
                    None
                    if solicitacao.decidido_em is None
                    else em_iso_utc(solicitacao.decidido_em)
                ),
                situacao=solicitacao.situacao,
            )

    @staticmethod
    def aprovar(solicitacao_id: uuid.UUID, administrador_id: uuid.UUID) -> tuple:
        """Marca a solicitacao `aprovada` e cria o evento (API-12 AC3, AC4).

        A linha e travada e a situacao reconferida **dentro** da transacao: e o
        que garante que duas aprovacoes simultaneas produzam um evento so, e a
        outra receba 409 (Edge Case da spec).
        """
        solicitacao = SolicitacaoService._bloquear_existente(solicitacao_id)
        SolicitacaoService.exigir_pendente(solicitacao)

        solicitacao.situacao = SITUACAO_APROVADA
        solicitacao.decidido_por_id = administrador_id
        solicitacao.decidido_em = agora()

        evento = EventoRepository.criar(
            solicitacao_id=solicitacao.id,
            situacao=SITUACAO_APROVADO,
            titulo=solicitacao.titulo,
            sigla=solicitacao.sigla,
            ano=solicitacao.ano,
            identificador_pagina=solicitacao.identificador_pagina,
            tipo=solicitacao.tipo,
            cidade=solicitacao.cidade,
            estado=solicitacao.estado,
            pais=solicitacao.pais,
            fuso=solicitacao.fuso,
            data_inicio=solicitacao.data_inicio,
            data_termino=solicitacao.data_termino,
            data_publicacao=solicitacao.data_publicacao,
            evento_pai_id=solicitacao.evento_pai_id,
            # Os cinco padroes de AC4 sao explicitos aqui, e nao deixados para o
            # `server_default`: o contrato os promete no corpo da resposta.
            modelo_avaliacao=MODELO_DE_AVALIACAO_PADRAO,
            avaliadores_por_submissao=AVALIADORES_POR_SUBMISSAO_PADRAO,
            rebuttal_habilitado=REBUTTAL_HABILITADO_PADRAO,
            maximo_rodadas=MAXIMO_DE_RODADAS_PADRAO,
            versao=1,
        )

        SolicitacaoService._aplicar_efeitos(solicitacao, evento)
        return solicitacao, evento

    @staticmethod
    def _aplicar_efeitos(solicitacao: SolicitacaoEvento, evento: Evento) -> None:
        """Os efeitos que a aprovacao dispara (API-13 AC1..AC3, AC6, AD-009).

        Tudo acontece na transacao aberta pelo controller: se qualquer etapa
        falhar, nem a solicitacao nem o evento sao gravados (AC4). O envio de
        e-mail e a unica excecao, porque `EmailService.enviar` nunca propaga
        falha — o convite fica gravado e a mensagem registrada como `falha`
        (AC5).
        """
        ParticipacaoRepository.garantir(
            evento.id, solicitacao.solicitante_id, PAPEL_DE_CHAIR
        )

        # Nenhuma das duas etapas abaixo precisa de defesa contra repeticao: as
        # duas sao idempotentes por construcao. E o que faz o e-mail repetido em
        # `chairsIniciais` (AC6), o e-mail do proprio solicitante na lista, e o
        # reprocessamento inteiro da aprovacao (Edge Case) renderem um efeito so.
        for email in SolicitacaoRepository.chairs_iniciais(solicitacao.id):
            conta = ContaRepository.por_email(email)
            if conta is not None:
                ParticipacaoRepository.garantir(evento.id, conta.id, PAPEL_DE_CHAIR)
                continue

            # Sem conta: convite por token, com o e-mail disparado por dentro
            # (AC3). Reprocessar nao gera um segundo convite pendente.
            if ConviteRepository.pendente_de_participacao(evento.id, email) is None:
                ConviteService.criar_para_participacao(evento, email, PAPEL_DE_CHAIR)

    @staticmethod
    def bloquear_pendente(solicitacao_id: uuid.UUID) -> SolicitacaoEvento:
        """Bloqueia a linha e exige que ela ainda esteja pendente (API-12 AC6b).

        Existe separada de `recusar` para que o controller possa checar o
        **estado antes de validar o corpo**: o 409 tem precedencia sobre o 422.
        """
        solicitacao = SolicitacaoService._bloquear_existente(solicitacao_id)
        SolicitacaoService.exigir_pendente(solicitacao)
        return solicitacao

    @staticmethod
    def recusar(
        solicitacao: SolicitacaoEvento, administrador_id: uuid.UUID, motivo: str
    ) -> SolicitacaoEvento:
        """Marca a solicitacao `recusada` com o motivo (API-12 AC5).

        Recebe a solicitacao **ja bloqueada e conferida** por
        `bloquear_pendente`. Nenhum evento e criado: a recusa e o fim do
        caminho da solicitacao.
        """
        solicitacao.situacao = SITUACAO_RECUSADA
        solicitacao.motivo_recusa = motivo
        solicitacao.decidido_por_id = administrador_id
        solicitacao.decidido_em = agora()
        return solicitacao

    @staticmethod
    def _bloquear_existente(solicitacao_id: uuid.UUID) -> SolicitacaoEvento:
        solicitacao = SolicitacaoRepository.por_id_bloqueada(solicitacao_id)
        if solicitacao is None:
            raise NaoEncontrado(
                "solicitacao_inexistente", MENSAGEM_DE_SOLICITACAO_INEXISTENTE
            )
        return solicitacao

    @staticmethod
    def exigir_existente(solicitacao_id: uuid.UUID) -> SolicitacaoEvento:
        """404 `solicitacao_inexistente` (API-12 AC8)."""
        solicitacao = SolicitacaoRepository.por_id(solicitacao_id)
        if solicitacao is None:
            raise NaoEncontrado(
                "solicitacao_inexistente", MENSAGEM_DE_SOLICITACAO_INEXISTENTE
            )
        return solicitacao

    # --- Validacoes ---------------------------------------------------------

    @staticmethod
    def _validar_identificador(
        identificador: str, *, solicitacao_id: uuid.UUID | None = None
    ) -> None:
        """API-11 AC2 — unico entre solicitacoes **e** eventos.

        A constraint unica cobre so uma tabela de cada vez; a checagem cruzada
        e o que faz o identificador ser unico no sistema inteiro.
        """
        existente = SolicitacaoRepository.por_identificador(identificador)
        if existente is not None and existente.id != solicitacao_id:
            raise ErroDeValidacao(
                {"identificadorPagina": MENSAGEM_DE_IDENTIFICADOR_EM_USO}
            )

        if EventoRepository.por_identificador(identificador) is not None:
            raise ErroDeValidacao(
                {"identificadorPagina": MENSAGEM_DE_IDENTIFICADOR_EM_USO}
            )

    @staticmethod
    def _validar_datas(inicio: date | None, termino: date | None) -> None:
        """API-11 AC4 — termino antes do inicio e 422 em `dataTermino`."""
        if inicio is not None and termino is not None and termino < inicio:
            raise ErroDeValidacao({"dataTermino": MENSAGEM_DE_TERMINO_ANTES_DO_INICIO})

    @staticmethod
    def validar_evento_pai(
        evento_pai_id: uuid.UUID | None, *, evento_proprio: uuid.UUID | None
    ) -> None:
        """API-11 AC5 — o pai nao pode ser o proprio evento nem um descendente.

        A travessia sobe pelos ancestrais do pai. O conjunto de visitados
        existe porque um ciclo ja gravado em dados legados faria a subida nunca
        terminar (Edge Case da spec): cada evento e visitado uma vez so.
        """
        if evento_pai_id is None:
            return

        pai = EventoRepository.por_id(evento_pai_id)
        if pai is None:
            raise ErroDeValidacao({"eventoPaiId": MENSAGEM_DE_PAI_INEXISTENTE})

        if evento_proprio is None:
            return

        visitados: set[uuid.UUID] = set()
        atual: Evento | None = pai
        while atual is not None and atual.id not in visitados:
            if atual.id == evento_proprio:
                raise ErroDeValidacao({"eventoPaiId": MENSAGEM_DE_CICLO})
            visitados.add(atual.id)
            atual = (
                None
                if atual.evento_pai_id is None
                else EventoRepository.por_id(atual.evento_pai_id)
            )

    # --- Projecao para a borda HTTP ----------------------------------------

    @staticmethod
    def projetar(solicitacao: SolicitacaoEvento) -> SolicitacaoDaApi:
        """A solicitacao como o contrato a expoe, com `temConta` derivado."""
        emails = SolicitacaoRepository.chairs_iniciais(solicitacao.id)
        return SolicitacaoDaApi(
            id=solicitacao.id,
            solicitante_id=solicitacao.solicitante_id,
            situacao=solicitacao.situacao,
            criado_em=solicitacao.criado_em,
            decidido_por_id=solicitacao.decidido_por_id,
            decidido_em=solicitacao.decidido_em,
            motivo_recusa=solicitacao.motivo_recusa,
            titulo=solicitacao.titulo,
            sigla=solicitacao.sigla,
            ano=solicitacao.ano,
            identificador_pagina=solicitacao.identificador_pagina,
            tipo=solicitacao.tipo,
            cidade=solicitacao.cidade,
            estado=solicitacao.estado,
            pais=solicitacao.pais,
            fuso=solicitacao.fuso,
            data_inicio=solicitacao.data_inicio,
            data_termino=solicitacao.data_termino,
            data_publicacao=solicitacao.data_publicacao,
            justificativa=solicitacao.justificativa,
            evento_pai_id=solicitacao.evento_pai_id,
            chairs_iniciais=[
                ChairInicialDaApi(
                    email=email,
                    tem_conta=ContaRepository.por_email(email) is not None,
                )
                for email in emails
            ],
            versao=solicitacao.versao,
        )

    @staticmethod
    def projetar_evento(evento: Evento) -> EventoDaApi:
        return EventoDaApi(
            id=evento.id,
            situacao=evento.situacao,
            titulo=evento.titulo,
            sigla=evento.sigla,
            ano=evento.ano,
            identificador_pagina=evento.identificador_pagina,
            tipo=evento.tipo,
            cidade=evento.cidade,
            estado=evento.estado,
            pais=evento.pais,
            fuso=evento.fuso,
            data_inicio=evento.data_inicio,
            data_termino=evento.data_termino,
            data_publicacao=evento.data_publicacao,
            evento_pai_id=evento.evento_pai_id,
            modelo_de_avaliacao=evento.modelo_avaliacao,
            avaliadores_por_submissao=evento.avaliadores_por_submissao,
            rebuttal_habilitado=evento.rebuttal_habilitado,
            prazo_rebuttal_dias=evento.prazo_rebuttal_dias,
            maximo_de_rodadas=evento.maximo_rodadas,
            nota_de_corte=(
                None if evento.nota_corte is None else float(evento.nota_corte)
            ),
            limite_submissoes_por_autor=evento.limite_submissoes_por_autor,
            versao=evento.versao,
        )
