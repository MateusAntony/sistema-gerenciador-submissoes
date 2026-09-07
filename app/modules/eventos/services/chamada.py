"""Regras das chamadas — criacao, edicao, prorrogacao e encerramento (API-16).

Nada aqui comita: o commit e da unidade de trabalho (AD-019).
"""

import uuid
from datetime import datetime, timezone

from flask import current_app

from app.core.erros import ConflitoDeVersao, ErroDeValidacao, NaoEncontrado
from app.modules.eventos.models import Chamada
from app.modules.eventos.repository import ChamadaRepository
from app.modules.eventos.schemas import ChamadaDaApi

MENSAGEM_DE_CHAMADA_INEXISTENTE = "Chamada não encontrada."
MENSAGEM_DE_LIMITE_ANTES_DA_ABERTURA = (
    "A data limite precisa ser posterior à data de abertura."
)
MENSAGEM_DE_TAMANHO_ACIMA_DO_LIMITE = (
    "O tamanho máximo não pode exceder o limite do servidor."
)
MENSAGEM_DE_PRORROGACAO_QUE_ENCURTA = (
    "A nova data limite precisa ser posterior à vigente — "
    "prorrogar não encurta prazo."
)


def teto_de_anexo_mb() -> int:
    """O teto que uma chamada pode declarar em `tamanhoMaximoMb` (AC9)."""
    return current_app.config["TAMANHO_MAXIMO_DE_ANEXO_MB"]


class ChamadaService:
    @staticmethod
    def exigir_existente(chamada_id: uuid.UUID) -> Chamada:
        """404 `chamada_inexistente` (API-16 AC10)."""
        chamada = ChamadaRepository.por_id(chamada_id)
        if chamada is None:
            raise NaoEncontrado("chamada_inexistente", MENSAGEM_DE_CHAMADA_INEXISTENTE)
        return chamada

    @staticmethod
    def exigir_versao(chamada: Chamada, versao: int) -> None:
        """409 `conflito_de_versao` com a chamada atual em `atual` (AC4, D2)."""
        if chamada.versao != versao:
            raise ConflitoDeVersao(ChamadaService.projetar(chamada).para_json())

    @staticmethod
    def criar(evento_id: uuid.UUID, dados) -> Chamada:
        """201 com `encerradaManualmente: false` e `versao: 1` (AC2)."""
        ChamadaService._validar_prazo(dados.data_abertura, dados.data_limite)
        ChamadaService._validar_tamanho(dados.tamanho_maximo_mb)

        return ChamadaRepository.criar(
            evento_id=evento_id,
            trilha_id=dados.trilha_id,
            titulo=dados.titulo,
            data_abertura=dados.data_abertura,
            data_limite=dados.data_limite,
            permite_submissao_apos_prazo=bool(dados.permite_submissao_apos_prazo),
            formatos_aceitos=dados.formatos_aceitos or [],
            tamanho_maximo_mb=dados.tamanho_maximo_mb,
            # Os dois padroes de AC2 sao explicitos, e nao deixados para o
            # `server_default`: o contrato os promete no corpo da resposta.
            encerrada_manualmente=False,
            versao=1,
        )

    @staticmethod
    def atualizar(chamada: Chamada, dados) -> Chamada:
        """Aplica a alteracao parcial e incrementa `versao` em 1 (AC5).

        As duas validacoes comparam o corpo com o que a chamada ja e: mudar so
        `dataLimite` tem de ser conferido contra a abertura gravada (AC3).
        """
        alteracoes = dados.model_dump(exclude_unset=True)
        alteracoes.pop("versao", None)

        ChamadaService._validar_prazo(
            alteracoes.get("data_abertura", chamada.data_abertura),
            alteracoes.get("data_limite", chamada.data_limite),
        )
        if "tamanho_maximo_mb" in alteracoes:
            ChamadaService._validar_tamanho(alteracoes["tamanho_maximo_mb"])

        for campo, valor in alteracoes.items():
            setattr(chamada, campo, valor)

        chamada.versao += 1
        return chamada

    @staticmethod
    def prorrogar(chamada: Chamada, nova_data: datetime) -> Chamada:
        """Estende o prazo e incrementa `versao` (AC6).

        **Prorrogar nunca encurta prazo**: data anterior ou igual a vigente e
        422, ainda que a edicao normal a aceitasse (AC7). O nome da operacao e
        a promessa — quem quer encurtar usa `PATCH`.
        """
        if nova_data <= ChamadaService._em_utc(chamada.data_limite):
            raise ErroDeValidacao({"dataLimite": MENSAGEM_DE_PRORROGACAO_QUE_ENCURTA})

        chamada.data_limite = nova_data
        chamada.versao += 1
        return chamada

    @staticmethod
    def encerrar(chamada: Chamada) -> Chamada:
        """Marca `encerradaManualmente` e incrementa `versao` (AC8)."""
        chamada.encerrada_manualmente = True
        chamada.versao += 1
        return chamada

    @staticmethod
    def _validar_prazo(abertura: datetime, limite: datetime) -> None:
        """AC3 — limite menor ou igual a abertura e 422 em `dataLimite`."""
        if ChamadaService._em_utc(limite) <= ChamadaService._em_utc(abertura):
            raise ErroDeValidacao({"dataLimite": MENSAGEM_DE_LIMITE_ANTES_DA_ABERTURA})

    @staticmethod
    def _validar_tamanho(tamanho_mb: int | None) -> None:
        """AC9 — acima do teto do servidor e 422 em `tamanhoMaximoMb`."""
        if tamanho_mb is not None and tamanho_mb > teto_de_anexo_mb():
            raise ErroDeValidacao(
                {"tamanhoMaximoMb": MENSAGEM_DE_TAMANHO_ACIMA_DO_LIMITE}
            )

    @staticmethod
    def _em_utc(momento: datetime) -> datetime:
        """Momento sem fuso vem do banco como UTC; comparar exige os dois iguais."""
        if momento.tzinfo is None:
            return momento.replace(tzinfo=timezone.utc)
        return momento

    @staticmethod
    def projetar(chamada: Chamada) -> ChamadaDaApi:
        return ChamadaDaApi(
            id=chamada.id,
            evento_id=chamada.evento_id,
            trilha_id=chamada.trilha_id,
            titulo=chamada.titulo,
            data_abertura=chamada.data_abertura,
            data_limite=chamada.data_limite,
            permite_submissao_apos_prazo=chamada.permite_submissao_apos_prazo,
            formatos_aceitos=list(chamada.formatos_aceitos or []),
            tamanho_maximo_mb=chamada.tamanho_maximo_mb,
            encerrada_manualmente=chamada.encerrada_manualmente,
            versao=chamada.versao,
        )
