"""Regras dos criterios de avaliacao (API-17).

Nada aqui comita: o commit e da unidade de trabalho (AD-019).
"""

import uuid

from app.core.erros import Conflito, ErroDeValidacao, NaoEncontrado
from app.modules.eventos.models import CriterioAvaliacao
from app.modules.eventos.repository import CriterioRepository
from app.modules.eventos.schemas import CriterioDaApi

MENSAGEM_DE_CRITERIO_INEXISTENTE = "Critério não encontrado."
MENSAGEM_DE_FAIXA_INVALIDA = "A nota máxima precisa ser maior que a mínima."
MENSAGEM_DE_PESO_INVALIDO = "O peso precisa ser maior que zero."
MENSAGEM_DE_CRITERIO_COM_NOTAS = (
    "Este critério já possui notas registradas e não pode ser excluído."
)

ACAO_SUGERIDA_PARA_CRITERIO_COM_NOTAS = "desativar"


class CriterioService:
    @staticmethod
    def exigir_existente(criterio_id: uuid.UUID) -> CriterioAvaliacao:
        """404 `criterio_inexistente` (API-17 AC7)."""
        criterio = CriterioRepository.por_id(criterio_id)
        if criterio is None:
            raise NaoEncontrado(
                "criterio_inexistente", MENSAGEM_DE_CRITERIO_INEXISTENTE
            )
        return criterio

    @staticmethod
    def criar(evento_id: uuid.UUID, dados) -> CriterioAvaliacao:
        """201 com `ativo: true` e a ordem resolvida (API-17 AC2, AC8)."""
        CriterioService._validar_faixa(dados.nota_minima, dados.nota_maxima)
        CriterioService._validar_peso(dados.peso)

        return CriterioRepository.criar(
            evento_id=evento_id,
            titulo=dados.titulo,
            descricao=dados.descricao,
            nota_minima=dados.nota_minima,
            nota_maxima=dados.nota_maxima,
            peso=dados.peso,
            # AC8 — sem `ordem`, a proxima posicao livre **daquele evento**.
            ordem=(
                CriterioRepository.proxima_ordem(evento_id)
                if dados.ordem is None
                else dados.ordem
            ),
            ativo=True if dados.ativo is None else dados.ativo,
        )

    @staticmethod
    def atualizar(criterio: CriterioAvaliacao, dados) -> CriterioAvaliacao:
        """Aplica a alteracao parcial (API-17 AC3, AC4).

        As duas validacoes comparam o corpo com o que o criterio ja e: mudar so
        `notaMaxima` tem de ser conferido contra a minima gravada.
        """
        alteracoes = dados.model_dump(exclude_unset=True)

        CriterioService._validar_faixa(
            alteracoes.get("nota_minima", float(criterio.nota_minima)),
            alteracoes.get("nota_maxima", float(criterio.nota_maxima)),
        )
        if "peso" in alteracoes:
            CriterioService._validar_peso(alteracoes["peso"])

        for campo, valor in alteracoes.items():
            setattr(criterio, campo, valor)

        return criterio

    @staticmethod
    def exigir_sem_notas(criterio: CriterioAvaliacao) -> None:
        """409 `criterio_com_notas` se o criterio ja tem nota (API-17 AC6).

        O `acaoSugerida: "desativar"` viaja **no corpo**, ao lado de `codigo`,
        `mensagem` e `correlacao`: e o que permite a tela oferecer a saida sem
        uma segunda requisicao.

        Fica separada de `excluir` para o controller poder decidir o 409 fora da
        transacao de escrita — e uma leitura, e levanta-la dentro do bloco faria
        o `rollback()` desfazer escritas anteriores da requisicao.
        """
        if CriterioRepository.tem_notas(criterio.id):
            raise Conflito(
                "criterio_com_notas",
                MENSAGEM_DE_CRITERIO_COM_NOTAS,
                acaoSugerida=ACAO_SUGERIDA_PARA_CRITERIO_COM_NOTAS,
            )

    @staticmethod
    def excluir(criterio: CriterioAvaliacao) -> None:
        """Remove a linha (API-17 AC5).

        Recebe o criterio **ja conferido** por `exigir_sem_notas`.
        """
        CriterioRepository.remover(criterio)

    @staticmethod
    def _validar_faixa(minima: float, maxima: float) -> None:
        """AC3 — maxima menor ou igual a minima e 422 em `notaMaxima`."""
        if maxima <= minima:
            raise ErroDeValidacao({"notaMaxima": MENSAGEM_DE_FAIXA_INVALIDA})

    @staticmethod
    def _validar_peso(peso: float) -> None:
        """AC4 — peso menor ou igual a zero e 422 em `peso`."""
        if peso <= 0:
            raise ErroDeValidacao({"peso": MENSAGEM_DE_PESO_INVALIDO})

    @staticmethod
    def projetar(criterio: CriterioAvaliacao) -> CriterioDaApi:
        """O criterio com `temNotas` **derivado por consulta** (AC1)."""
        return CriterioDaApi(
            id=criterio.id,
            evento_id=criterio.evento_id,
            titulo=criterio.titulo,
            descricao=criterio.descricao,
            nota_minima=float(criterio.nota_minima),
            nota_maxima=float(criterio.nota_maxima),
            peso=float(criterio.peso),
            ordem=criterio.ordem,
            ativo=criterio.ativo,
            tem_notas=CriterioRepository.tem_notas(criterio.id),
        )
