"""Schemas da borda HTTP do dominio de eventos (AD-006)."""

import uuid
from datetime import date, datetime

from pydantic import Field

from app.core.schemas import SchemaDaApi, SchemaDeEntrada


class ParticipacaoDaApi(SchemaDaApi):
    """Uma entrada de `GET /api/me/participacoes` (API-07 AC3).

    Uma entrada por evento, com **todos** os papeis do usuario nele (AC4) — e o
    que alimenta o seletor de evento e o menu do front.
    """

    evento_id: uuid.UUID
    evento_titulo: str
    identificador_pagina: str
    papeis: list[str]


class ChairInicialDaApi(SchemaDaApi):
    """Um chair inicial como o contrato do front o expoe (`tipos.ts`)."""

    email: str
    tem_conta: bool


class SolicitacaoDaApi(SchemaDaApi):
    """Uma solicitacao de evento como o contrato a devolve (API-11 AC1)."""

    id: uuid.UUID
    solicitante_id: uuid.UUID
    situacao: str
    criado_em: datetime
    decidido_por_id: uuid.UUID | None = None
    decidido_em: datetime | None = None
    motivo_recusa: str | None = None
    titulo: str
    sigla: str | None = None
    ano: int
    identificador_pagina: str
    tipo: str | None = None
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    fuso: str | None = None
    data_inicio: date | None = None
    data_termino: date | None = None
    data_publicacao: date | None = None
    justificativa: str | None = None
    evento_pai_id: uuid.UUID | None = None
    chairs_iniciais: list[ChairInicialDaApi]
    versao: int


class EventoDaApi(SchemaDaApi):
    """Um evento como o contrato o devolve (`Evento` de `tipos.ts`)."""

    id: uuid.UUID
    situacao: str
    titulo: str
    sigla: str | None = None
    ano: int
    identificador_pagina: str
    tipo: str | None = None
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    fuso: str | None = None
    data_inicio: date | None = None
    data_termino: date | None = None
    data_publicacao: date | None = None
    evento_pai_id: uuid.UUID | None = None
    modelo_de_avaliacao: str
    avaliadores_por_submissao: int
    rebuttal_habilitado: bool
    prazo_rebuttal_dias: int | None = None
    maximo_de_rodadas: int
    nota_de_corte: float | None = None
    limite_submissoes_por_autor: int | None = None
    versao: int


class ChairInicialDeEntrada(SchemaDeEntrada):
    """Cada item de `chairsIniciais` no corpo enviado pelo front.

    `temConta` chega do formulario mas e derivado pela API, nunca confiado:
    aceitar o campo evita 422 por `extra_forbidden` num corpo que o front ja
    monta assim.
    """

    email: str
    tem_conta: bool | None = None


class SolicitacaoDeEntrada(SchemaDeEntrada):
    """Corpo de `POST /api/solicitacoes-evento` (API-11 AC1..AC5).

    Os obrigatorios de AC3 sao exigidos aqui, com `min_length=1` para que campo
    vazio caia no mesmo 422 que campo ausente.
    """

    titulo: str = Field(min_length=1, max_length=300)
    identificador_pagina: str = Field(min_length=1, max_length=100)
    data_inicio: date
    data_termino: date
    sigla: str | None = Field(default=None, max_length=50)
    ano: int | None = None
    tipo: str | None = None
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    fuso: str | None = None
    data_publicacao: date | None = None
    justificativa: str | None = None
    evento_pai_id: uuid.UUID | None = None
    chairs_iniciais: list[ChairInicialDeEntrada] = Field(default_factory=list)


class EdicaoDeSolicitacao(SchemaDeEntrada):
    """Corpo de `PATCH /api/solicitacoes-evento/{id}` — todo campo opcional.

    O front reenvia o formulario inteiro, mas o contrato e de alteracao
    parcial: o que nao vier fica como esta (API-11 AC6).
    """

    titulo: str | None = Field(default=None, min_length=1, max_length=300)
    identificador_pagina: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    data_inicio: date | None = None
    data_termino: date | None = None
    sigla: str | None = Field(default=None, max_length=50)
    ano: int | None = None
    tipo: str | None = None
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    fuso: str | None = None
    data_publicacao: date | None = None
    justificativa: str | None = None
    evento_pai_id: uuid.UUID | None = None
    chairs_iniciais: list[ChairInicialDeEntrada] | None = None


class RecusaDeSolicitacao(SchemaDeEntrada):
    """Corpo de `POST .../recusar` — o motivo e obrigatorio (API-12 AC6)."""

    motivo: str = Field(min_length=1)


class DecisaoDeAprovacao(SchemaDaApi):
    """Resposta de `POST .../aprovar` (API-12 AC3)."""

    solicitacao: SolicitacaoDaApi
    evento: EventoDaApi


class EdicaoDeEvento(SchemaDeEntrada):
    """Corpo de `PATCH /api/eventos/{id}` (API-14 AC3..AC7, AC9, D2).

    Todo campo e opcional: o front envia so a secao que edita, e o que nao vier
    fica como esta. `versao` e obrigatoria — e a que decide entre aplicar e 409.

    Os limites de AC5 e AC7 ficam no proprio schema: `ge=1` reprova o zero e o
    negativo, e o tradutor de `ValidationError` nomeia o campo em camelCase.
    """

    versao: int
    titulo: str | None = Field(default=None, min_length=1, max_length=300)
    sigla: str | None = Field(default=None, max_length=50)
    ano: int | None = None
    identificador_pagina: str | None = Field(default=None, min_length=1, max_length=100)
    tipo: str | None = None
    cidade: str | None = None
    estado: str | None = None
    pais: str | None = None
    fuso: str | None = None
    data_inicio: date | None = None
    data_termino: date | None = None
    data_publicacao: date | None = None
    site: str | None = Field(default=None, max_length=300)
    evento_pai_id: uuid.UUID | None = None
    modelo_de_avaliacao: str | None = None
    avaliadores_por_submissao: int | None = Field(default=None, ge=1)
    rebuttal_habilitado: bool | None = None
    prazo_rebuttal_dias: int | None = Field(default=None, ge=1)
    maximo_de_rodadas: int | None = Field(default=None, ge=1)
    nota_de_corte: float | None = None
    limite_submissoes_por_autor: int | None = None


class TrilhaDaApi(SchemaDaApi):
    """Uma trilha como o contrato a devolve, com a contagem derivada (API-15 AC1)."""

    id: uuid.UUID
    evento_id: uuid.UUID
    nome: str
    descricao: str | None = None
    ativa: bool
    submissoes_vinculadas: int


class TrilhaDeEntrada(SchemaDeEntrada):
    """Corpo de `POST /api/eventos/{id}/trilhas` (API-15 AC2, AC3)."""

    nome: str = Field(min_length=1, max_length=200)
    descricao: str | None = None
    ativa: bool | None = None


class EdicaoDeTrilha(SchemaDeEntrada):
    """Corpo de `PATCH /api/trilhas/{id}` — alteracao parcial (API-15 AC4)."""

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = None
    ativa: bool | None = None
