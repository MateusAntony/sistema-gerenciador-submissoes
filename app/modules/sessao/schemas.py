"""Schemas da borda HTTP do dominio de sessao (AD-006)."""

from pydantic import Field

from app.core.schemas import SchemaDaApi, SchemaDeEntrada
from app.modules.contas.schemas import UsuarioDaApi


class Login(SchemaDeEntrada):
    """Corpo de `POST /api/auth/login` (API-03 AC1)."""

    email: str = Field(min_length=1, max_length=255)
    senha: str = Field(min_length=1)


class SessaoAberta(SchemaDaApi):
    """Resposta do login: o token de acesso e o usuario (API-03 AC1).

    O token de renovacao **nao** esta aqui: ele sai no cookie httpOnly (AD-002).
    """

    token_de_acesso: str
    usuario: UsuarioDaApi


class AcessoRenovado(SchemaDaApi):
    """Resposta da renovacao: so o token de acesso novo (API-04 AC1)."""

    token_de_acesso: str
