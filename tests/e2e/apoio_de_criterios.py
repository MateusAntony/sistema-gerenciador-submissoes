"""Apoio comum aos testes e2e de criterios (T41, T42)."""

from app.extensions import db
from app.modules.areas_futuras.models import NotaParecer
from app.modules.eventos.models import CriterioAvaliacao
from tests.e2e.apoio_de_eventos import fixar


def rota_da_lista(evento_id) -> str:
    return f"/api/eventos/{evento_id}/criterios"


def rota_do_criterio(criterio_id) -> str:
    return f"/api/criterios/{criterio_id}"


def criar_criterio(
    evento,
    *,
    titulo: str = "Originalidade",
    ordem: int = 1,
    nota_minima: float = 0,
    nota_maxima: float = 10,
    peso: float = 1,
    ativo: bool = True,
) -> CriterioAvaliacao:
    criterio = CriterioAvaliacao(
        evento_id=evento.id,
        titulo=titulo,
        nota_minima=nota_minima,
        nota_maxima=nota_maxima,
        peso=peso,
        ordem=ordem,
        ativo=ativo,
    )
    db.session.add(criterio)
    fixar()
    return criterio


def registrar_nota(criterio) -> NotaParecer:
    """Uma linha em `notas_parecer`, para `temNotas` e o 409 terem o que ver."""
    nota = NotaParecer(criterio_id=criterio.id)
    db.session.add(nota)
    fixar()
    return nota
