"""Schemas da borda HTTP dos convites (AD-006)."""

from datetime import datetime

from app.core.schemas import SchemaDaApi


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
