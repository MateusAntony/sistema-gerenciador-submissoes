"""Um identificador por requisicao — no header, no log e no corpo de erro (API-01 AC3).

Quem le a correlacao para montar o envelope de erro e `core/erros`; quem a cria e
devolve no header e este modulo.
"""

import uuid

from flask import Flask, Response, g

CABECALHO_DE_CORRELACAO = "X-Correlacao"


def iniciar_correlacao() -> None:
    g.correlacao = str(uuid.uuid4())


def correlacao_atual() -> str:
    correlacao = getattr(g, "correlacao", None)
    if correlacao is None:
        correlacao = str(uuid.uuid4())
        g.correlacao = correlacao
    return correlacao


def anexar_correlacao(resposta: Response) -> Response:
    resposta.headers[CABECALHO_DE_CORRELACAO] = correlacao_atual()
    return resposta


def registrar_correlacao(app: Flask) -> None:
    app.before_request(iniciar_correlacao)
    app.after_request(anexar_correlacao)
