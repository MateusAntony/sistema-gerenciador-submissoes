"""Guardas de autorizacao da borda HTTP.

Por ora so a autenticacao. A matriz da §3.7 e `@exige_acao` chegam com o RBAC
por evento, e este modulo e a casa das duas.
"""

import uuid
from collections.abc import Callable
from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError

from app.core.erros import NaoAutenticado
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository

CHAVE_DO_USUARIO = "usuario_autenticado"


def exige_autenticacao(rota: Callable) -> Callable:
    """Resolve o `Bearer`, carrega o usuario e deixa 401 para todo o resto."""

    @wraps(rota)
    def _guarda(*args, **kwargs):
        setattr(g, CHAVE_DO_USUARIO, _usuario_do_token())
        return rota(*args, **kwargs)

    return _guarda


def usuario_autenticado() -> Usuario:
    """O usuario da requisicao corrente. So existe sob `@exige_autenticacao`."""
    return getattr(g, CHAVE_DO_USUARIO)


def _usuario_do_token() -> Usuario:
    try:
        verify_jwt_in_request()
        identidade = get_jwt_identity()
    except (JWTExtendedException, PyJWTError) as recusa:
        # Ausente, malformado, com assinatura invalida ou expirado: tudo isso e
        # uma unica resposta, e nenhuma delas revela qual foi (API-07 AC2).
        raise NaoAutenticado from recusa

    usuario = _por_identidade(identidade)

    # O token e valido por 15 minutos; a conta pode ter sido desativada ou
    # apagada nesse meio-tempo. A checagem acontece a cada requisicao, e nao so
    # no login: sem ela, um id obsoleto viraria 500 (risco R2, Edge Case).
    if usuario is None or not usuario.ativo:
        raise NaoAutenticado

    return usuario


def _por_identidade(identidade: object) -> Usuario | None:
    try:
        return ContaRepository.por_id(uuid.UUID(str(identidade)))
    except ValueError:
        # Identidade que nao e UUID nao pertence a nenhuma conta desta base.
        return None
