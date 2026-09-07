"""Schemas da borda HTTP do dominio de eventos (AD-006)."""

import uuid

from app.core.schemas import SchemaDaApi


class ParticipacaoDaApi(SchemaDaApi):
    """Uma entrada de `GET /api/me/participacoes` (API-07 AC3).

    Uma entrada por evento, com **todos** os papeis do usuario nele (AC4) — e o
    que alimenta o seletor de evento e o menu do front.
    """

    evento_id: uuid.UUID
    evento_titulo: str
    identificador_pagina: str
    papeis: list[str]
