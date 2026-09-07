"""Schemas da borda HTTP dos convites (AD-006)."""

from datetime import datetime

from pydantic import Field

from app.core.schemas import SchemaDaApi, SchemaDeEntrada


class ConviteDaApi(SchemaDaApi):
    """Resposta de `GET /api/convites/{token}` (API-08 AC1, D3, D4).

    `submissao_titulo` e opcional de proposito: convite de `participacao` nao tem
    submissao atras, e `para_json()` omite o que e `None` — o campo fica
    **ausente** da resposta, nao nulo (AC6).
    """

    tipo: str
    email: str
    evento_titulo: str
    submissao_titulo: str | None = None
    prazo: datetime | None = None
    fuso: str | None = None
    contato_da_organizacao: str
    precisa_criar_conta: bool


class AceiteDeConvite(SchemaDeEntrada):
    """Corpo de `POST /api/convites/{token}/aceitar` (API-08 AC7, AC8).

    Os dois campos sao opcionais no schema porque quem ja tem conta nao os
    envia; a obrigatoriedade e do ramo que cria a conta, e o service a impoe.
    """

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    senha: str | None = Field(default=None, min_length=8)
