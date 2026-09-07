"""Schemas da borda HTTP do dominio de contas (AD-006)."""

import uuid

from pydantic import Field

from app.core.schemas import SchemaDaApi, SchemaDeEntrada


class CadastroDeConta(SchemaDeEntrada):
    """Corpo de `POST /api/usuarios` (API-05 AC1, AC3, AC4)."""

    nome: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=1, max_length=255)
    senha: str = Field(min_length=8)
    instituicao: str = Field(min_length=1, max_length=200)
    pais: str = Field(min_length=1, max_length=100)


class ContaCriada(SchemaDaApi):
    """Resposta de criacao: **so** `id` e `email` (API-05 AC6)."""

    id: uuid.UUID
    email: str
