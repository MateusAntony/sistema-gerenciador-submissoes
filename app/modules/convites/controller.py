"""Borda HTTP dos convites por token — consulta e aceite, sem sessao (BASE-08)."""

from flask import Blueprint, jsonify

from app.modules.convites.service import ConviteService

convites_bp = Blueprint("convites", __name__, url_prefix="/api")


@convites_bp.get("/convites/<token>")
def consultar(token: str):
    """200 **sem exigir sessao**; 404, 410 ou 409 com o contato (API-08 AC1..AC4)."""
    convite = ConviteService.consultar(token)

    return jsonify(ConviteService.projetar(convite).para_json()), 200
