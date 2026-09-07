"""Base comum a todo schema da borda HTTP (API-01 AC4, AD-006).

O contrato do front e camelCase; as tabelas sao snake_case em pt-BR. A traducao
acontece aqui, uma vez, em vez de campo a campo em 34 endpoints.
"""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel


def em_iso_utc(momento: datetime) -> str:
    """ISO-8601 em UTC terminando em `Z`. Momento sem fuso e lido como UTC."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SchemaDaApi(BaseModel):
    """Saida da API: campos em camelCase, `UUID` como string, data/hora em UTC."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @field_serializer("*", mode="wrap", when_used="json")
    def _serializar_campo(self, valor: Any, serializar_padrao) -> Any:
        if isinstance(valor, datetime):
            return em_iso_utc(valor)
        return serializar_padrao(valor)

    def para_json(self) -> dict:
        """Corpo pronto para a resposta: alias camelCase e sem campo ausente."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)


class SchemaDeEntrada(SchemaDaApi):
    """Entrada da API: campo desconhecido e recusado, e vira 422 no tratador."""

    model_config = ConfigDict(extra="forbid")
