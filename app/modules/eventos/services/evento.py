"""Regras do evento ja criado — leitura, edicao e hierarquia (API-14).

Nada aqui comita: o commit e da unidade de trabalho (AD-019).
"""

import uuid

from app.core.erros import NaoEncontrado
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import EventoRepository

MENSAGEM_DE_EVENTO_INEXISTENTE = "Evento não encontrado."


class EventoService:
    @staticmethod
    def exigir_existente(evento_id: uuid.UUID) -> Evento:
        """404 `evento_inexistente` (API-14 AC1)."""
        evento = EventoRepository.por_id(evento_id)
        if evento is None:
            raise NaoEncontrado("evento_inexistente", MENSAGEM_DE_EVENTO_INEXISTENTE)
        return evento

    @staticmethod
    def exigir_por_identificador(identificador: str) -> Evento:
        """404 `evento_inexistente`; resolve **sem exigir participacao** (AC2)."""
        evento = EventoRepository.por_identificador(identificador)
        if evento is None:
            raise NaoEncontrado("evento_inexistente", MENSAGEM_DE_EVENTO_INEXISTENTE)
        return evento
