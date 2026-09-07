"""Apoio comum aos testes e2e de chamadas (T39, T40)."""

from datetime import datetime, timezone

from app.extensions import db
from app.modules.eventos.models import Chamada
from tests.e2e.apoio_de_eventos import fixar

ABERTURA = "2026-01-01T00:00:00Z"
LIMITE = "2026-02-01T00:00:00Z"


def rota_da_lista(evento_id) -> str:
    return f"/api/eventos/{evento_id}/chamadas"


def rota_da_chamada(chamada_id) -> str:
    return f"/api/chamadas/{chamada_id}"


def criar_chamada(
    evento,
    *,
    titulo: str = "Chamada de Trabalhos",
    data_limite: datetime | None = None,
    **campos,
) -> Chamada:
    chamada = Chamada(
        evento_id=evento.id,
        titulo=titulo,
        data_abertura=datetime(2026, 1, 1, tzinfo=timezone.utc),
        data_limite=data_limite or datetime(2026, 2, 1, tzinfo=timezone.utc),
        versao=1,
        **campos,
    )
    db.session.add(chamada)
    fixar()
    return chamada
