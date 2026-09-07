"""Schemas da borda HTTP dos convites (AD-006)."""

from datetime import datetime

from pydantic import Field

from app.core.schemas import SchemaDaApi, SchemaDeEntrada
from app.modules.sessao.schemas import SessaoAberta


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


class SessaoAbertaPorConvite(SessaoAberta):
    """Resposta do aceite: o corpo do login **mais** o destino (API-08 AC10).

    `destino` nao existe no login porque so o convite sabe para onde a pessoa
    deve ir depois de aceitar. Quem decide e o servidor: BASE nao conhece as
    rotas de avaliacao (AD-013 do front), entao recebe um caminho pronto.
    """

    destino: str
