"""Regras das trilhas do evento (API-15).

Nada aqui comita: o commit e da unidade de trabalho (AD-019).
"""

import uuid

from app.core.erros import ErroDeValidacao, NaoEncontrado
from app.modules.eventos.models import Trilha
from app.modules.eventos.repository import TrilhaRepository
from app.modules.eventos.schemas import TrilhaDaApi

MENSAGEM_DE_TRILHA_INEXISTENTE = "Trilha não encontrada."
MENSAGEM_DE_NOME_REPETIDO = "Já existe uma trilha com este nome neste evento."


class TrilhaService:
    @staticmethod
    def exigir_existente(trilha_id: uuid.UUID) -> Trilha:
        """404 `trilha_inexistente` (API-15 AC6)."""
        trilha = TrilhaRepository.por_id(trilha_id)
        if trilha is None:
            raise NaoEncontrado("trilha_inexistente", MENSAGEM_DE_TRILHA_INEXISTENTE)
        return trilha

    @staticmethod
    def criar(evento_id: uuid.UUID, dados) -> Trilha:
        """201 com a trilha `ativa` por padrao (API-15 AC2)."""
        TrilhaService._validar_nome(evento_id, dados.nome)

        return TrilhaRepository.criar(
            evento_id=evento_id,
            nome=dados.nome,
            descricao=dados.descricao,
            ativa=True if dados.ativa is None else dados.ativa,
        )

    @staticmethod
    def atualizar(trilha: Trilha, dados) -> Trilha:
        """Aplica a alteracao parcial (API-15 AC4).

        Desativar trilha com submissoes vinculadas **e permitido**: o aviso e da
        tela, e a contagem viaja na resposta para ela poder da-lo (AC5).
        """
        alteracoes = dados.model_dump(exclude_unset=True)

        nome = alteracoes.get("nome")
        if nome is not None and nome != trilha.nome:
            TrilhaService._validar_nome(trilha.evento_id, nome)

        for campo, valor in alteracoes.items():
            setattr(trilha, campo, valor)

        return trilha

    @staticmethod
    def _validar_nome(evento_id: uuid.UUID, nome: str) -> None:
        """AC7 — nome repetido **dentro do mesmo evento** e 422 em `nome`.

        A checagem antecede a constraint unica para o erro sair nomeando o
        campo, em vez de virar erro de integridade.
        """
        if TrilhaRepository.por_nome(evento_id, nome) is not None:
            raise ErroDeValidacao({"nome": MENSAGEM_DE_NOME_REPETIDO})

    @staticmethod
    def projetar(trilha: Trilha) -> TrilhaDaApi:
        """A trilha com `submissoesVinculadas` **derivado por consulta** (AC1)."""
        return TrilhaDaApi(
            id=trilha.id,
            evento_id=trilha.evento_id,
            nome=trilha.nome,
            descricao=trilha.descricao,
            ativa=trilha.ativa,
            submissoes_vinculadas=TrilhaRepository.submissoes_vinculadas(trilha.id),
        )
