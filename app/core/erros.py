"""Hierarquia de erros de dominio e o envelope unico de resposta.

Toda resposta com status >= 400 sai como `{ codigo, mensagem, campos?, correlacao }`
(API-01 AC1). Nenhum controller monta erro a mao: o que sobe e traduzido aqui.
"""

import logging
import uuid

from flask import Flask, Response, g, jsonify
from pydantic import ValidationError
from pydantic.alias_generators import to_camel
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

CODIGOS_HTTP = {
    400: "corpo_invalido",
    401: "nao_autenticado",
    403: "sem_permissao",
    404: "nao_encontrado",
    405: "metodo_nao_permitido",
    413: "corpo_muito_grande",
    415: "corpo_invalido",
}

MENSAGENS_HTTP = {
    400: "O corpo da requisição não é um JSON válido.",
    401: "É preciso estar autenticado para continuar.",
    403: "Você não tem permissão para esta ação.",
    404: "Recurso não encontrado.",
    405: "Método não permitido para este recurso.",
    413: "O corpo da requisição excede o tamanho permitido.",
    415: "O corpo da requisição não é um JSON válido.",
}

MENSAGENS_DE_VALIDACAO = {
    "missing": "Campo obrigatório.",
    "extra_forbidden": "Campo não reconhecido.",
    "string_too_short": "Valor muito curto.",
    "string_too_long": "Valor muito longo.",
    "greater_than": "Valor abaixo do mínimo permitido.",
    "greater_than_equal": "Valor abaixo do mínimo permitido.",
    "less_than": "Valor acima do máximo permitido.",
    "less_than_equal": "Valor acima do máximo permitido.",
}

MENSAGEM_DE_VALIDACAO_PADRAO = "Valor inválido."

PREFIXO_DE_ERRO_DE_VALOR = "Value error, "


class ErroDaApi(Exception):
    """Erro de dominio que ja sabe com que status e codigo deve sair."""

    codigo = "erro_interno"
    status = 500
    mensagem = "Erro interno do servidor."

    def __init__(
        self,
        mensagem: str | None = None,
        *,
        codigo: str | None = None,
        status: int | None = None,
        **extras,
    ) -> None:
        if codigo is not None:
            self.codigo = codigo
        if status is not None:
            self.status = status
        if mensagem is not None:
            self.mensagem = mensagem
        self.extras = extras
        # Cabecalhos que fazem parte do contrato do erro, como o `Retry-After`
        # de API-20 AC1. Vazio para quase todos.
        self.cabecalhos: dict[str, str] = {}
        super().__init__(self.mensagem)


class ErroDeValidacao(ErroDaApi):
    codigo = "dados_invalidos"
    status = 422
    mensagem = "Há campos inválidos no formulário."

    def __init__(self, campos: dict[str, str], mensagem: str | None = None) -> None:
        super().__init__(mensagem, campos=campos)


class NaoAutenticado(ErroDaApi):
    codigo = "nao_autenticado"
    status = 401
    mensagem = "É preciso estar autenticado para continuar."


class SemPermissao(ErroDaApi):
    codigo = "sem_permissao"
    status = 403
    mensagem = "Você não tem permissão para esta ação."


class NaoEncontrado(ErroDaApi):
    status = 404
    mensagem = "Recurso não encontrado."

    def __init__(self, codigo: str, mensagem: str | None = None, **extras) -> None:
        super().__init__(mensagem, codigo=codigo, **extras)


class Conflito(ErroDaApi):
    status = 409
    mensagem = "A operação conflita com o estado atual do recurso."

    def __init__(self, codigo: str, mensagem: str | None = None, **extras) -> None:
        super().__init__(mensagem, codigo=codigo, **extras)


class ConflitoDeVersao(Conflito):
    """409 com o registro atual em `atual`, para a tela oferecer recarregar (D2)."""

    def __init__(self, atual: dict) -> None:
        super().__init__(
            "conflito_de_versao",
            "O registro foi alterado por outra pessoa. Recarregue e tente de novo.",
            atual=atual,
        )


def correlacao_da_requisicao() -> str:
    """Correlacao da requisicao corrente; quem a define e `core/correlacao`."""
    return getattr(g, "correlacao", None) or str(uuid.uuid4())


def montar_envelope(codigo: str, mensagem: str, extras: dict | None = None) -> dict:
    envelope = {
        "codigo": codigo,
        "mensagem": mensagem,
        "correlacao": correlacao_da_requisicao(),
    }
    envelope.update(extras or {})
    return envelope


def _responder(
    codigo: str, mensagem: str, status: int, extras=None, cabecalhos=None
) -> Response:
    resposta = jsonify(montar_envelope(codigo, mensagem, extras))
    resposta.status_code = status
    resposta.headers.update(cabecalhos or {})
    return resposta


def campos_de_validacao(erro: ValidationError) -> dict[str, str]:
    """Traduz o erro do Pydantic para `{ campoEmCamelCase: mensagem em pt-BR }`."""
    campos: dict[str, str] = {}
    for detalhe in erro.errors():
        partes = [parte for parte in detalhe["loc"] if isinstance(parte, str)]
        nome = to_camel(partes[-1]) if partes else "corpo"
        campos.setdefault(nome, _mensagem_de_validacao(detalhe))
    return campos


def _mensagem_de_validacao(detalhe: dict) -> str:
    if detalhe["type"] == "value_error":
        # Validador de dominio: a mensagem ja vem em pt-BR de quem a levantou.
        return str(detalhe["msg"]).removeprefix(PREFIXO_DE_ERRO_DE_VALOR)
    return MENSAGENS_DE_VALIDACAO.get(detalhe["type"], MENSAGEM_DE_VALIDACAO_PADRAO)


def registrar_tratadores(app: Flask) -> None:
    """Liga os tratadores que garantem o envelope em toda resposta de erro."""

    @app.errorhandler(ErroDaApi)
    def _erro_de_dominio(erro: ErroDaApi) -> Response:
        return _responder(
            erro.codigo, erro.mensagem, erro.status, erro.extras, erro.cabecalhos
        )

    @app.errorhandler(ValidationError)
    def _erro_de_validacao(erro: ValidationError) -> Response:
        return _responder(
            ErroDeValidacao.codigo,
            ErroDeValidacao.mensagem,
            ErroDeValidacao.status,
            {"campos": campos_de_validacao(erro)},
        )

    @app.errorhandler(HTTPException)
    def _erro_http(erro: HTTPException) -> Response:
        status = erro.code or 500
        return _responder(
            CODIGOS_HTTP.get(status, "erro_http"),
            MENSAGENS_HTTP.get(status, erro.description or "Erro na requisição."),
            status,
        )

    @app.errorhandler(Exception)
    def _erro_inesperado(erro: Exception) -> Response:
        envelope = montar_envelope("erro_interno", ErroDaApi.mensagem)
        # A stack fica no log, com a mesma correlacao da resposta (API-01 AC5).
        logger.exception(
            "Erro não tratado (correlacao=%s)", envelope["correlacao"], exc_info=erro
        )
        resposta = jsonify(envelope)
        resposta.status_code = 500
        return resposta
