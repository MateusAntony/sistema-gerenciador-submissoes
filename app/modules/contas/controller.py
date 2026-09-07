"""Borda HTTP do dominio de contas."""

from flask import Blueprint, jsonify, request

from app.core.unidade_de_trabalho import transacao
from app.modules.contas.schemas import (
    CadastroDeConta,
    ConfirmacaoDeEmail,
    ContaCriada,
    EmailConfirmado,
)
from app.modules.contas.service import ContaService

contas_bp = Blueprint("contas", __name__, url_prefix="/api")


@contas_bp.post("/usuarios")
def cadastrar():
    dados = CadastroDeConta.model_validate(request.get_json())

    with transacao():
        usuario = ContaService.criar(dados)
        # O corpo e montado antes do commit: depois dele os atributos expiram.
        corpo = ContaCriada(id=usuario.id, email=usuario.email).para_json()

    return jsonify(corpo), 201


@contas_bp.post("/auth/confirmar-email")
def confirmar_email():
    dados = ConfirmacaoDeEmail.model_validate(request.get_json())

    with transacao():
        email = ContaService.confirmar_email(dados.token)
        corpo = EmailConfirmado(email=email).para_json()

    return jsonify(corpo), 200
