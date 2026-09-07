"""Testes de ponta a ponta de `GET /api/eventos/{id}/descendentes` — API-14 AC8 (T37)."""

import uuid

from sqlalchemy import text

from app.extensions import db
from tests.e2e.apoio_de_eventos import cabecalhos, criar_evento, criar_usuario


def rota(evento_id) -> str:
    return f"/api/eventos/{evento_id}/descendentes"


# AC8 — **toda** a arvore abaixo do evento: filhos, netos e alem.


def test_os_descendentes_trazem_a_arvore_inteira_de_tres_niveis(cliente, sessao):
    raiz = criar_evento(titulo="Raiz")
    filho = criar_evento(titulo="Filho", evento_pai_id=raiz.id)
    neto = criar_evento(titulo="Neto", evento_pai_id=filho.id)
    bisneto = criar_evento(titulo="Bisneto", evento_pai_id=neto.id)

    resposta = cliente.get(rota(raiz.id), headers=cabecalhos(criar_usuario()))

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == {"descendentes"}
    assert set(corpo["descendentes"]) == {str(filho.id), str(neto.id), str(bisneto.id)}


def test_os_descendentes_nao_incluem_o_proprio_evento(cliente, sessao):
    raiz = criar_evento(titulo="Raiz")
    criar_evento(titulo="Filho", evento_pai_id=raiz.id)

    descendentes = cliente.get(
        rota(raiz.id), headers=cabecalhos(criar_usuario())
    ).get_json()["descendentes"]

    assert str(raiz.id) not in descendentes


def test_os_descendentes_nao_incluem_eventos_de_outra_arvore(cliente, sessao):
    raiz = criar_evento(titulo="Raiz")
    filho = criar_evento(titulo="Filho", evento_pai_id=raiz.id)
    alheio = criar_evento(titulo="Alheio")

    descendentes = cliente.get(
        rota(raiz.id), headers=cabecalhos(criar_usuario())
    ).get_json()["descendentes"]

    assert descendentes == [str(filho.id)]
    assert str(alheio.id) not in descendentes


# AC8 — evento folha devolve lista vazia.


def test_um_evento_folha_devolve_lista_vazia(cliente, sessao):
    folha = criar_evento(titulo="Sem Filhos")

    resposta = cliente.get(rota(folha.id), headers=cabecalhos(criar_usuario()))

    assert resposta.status_code == 200
    assert resposta.get_json()["descendentes"] == []


# Edge Case — ciclo em dados legados: a travessia termina, visitando cada um uma vez.


def test_um_ciclo_em_dados_legados_termina_visitando_cada_evento_uma_vez(
    cliente, sessao
):
    """A -> B -> C -> A. Sem o conjunto de visitados a travessia nao terminaria."""
    a = criar_evento(titulo="A")
    b = criar_evento(titulo="B", evento_pai_id=a.id)
    c = criar_evento(titulo="C", evento_pai_id=b.id)
    # O ciclo so existe em dados legados: nenhuma rota o cria, entao ele e
    # gravado por SQL direto, driblando a validacao de AC9.
    db.session.execute(
        text("UPDATE eventos SET evento_pai_id = :c WHERE id = :a"),
        {"c": c.id, "a": a.id},
    )
    db.session.commit()

    resposta = cliente.get(rota(a.id), headers=cabecalhos(criar_usuario()))

    assert resposta.status_code == 200
    descendentes = resposta.get_json()["descendentes"]
    assert sorted(descendentes) == sorted([str(b.id), str(c.id)])
    # Cada evento aparece uma vez so: nem repeticao, nem o proprio `a` de volta.
    assert len(descendentes) == len(set(descendentes))
    assert str(a.id) not in descendentes


def test_os_descendentes_de_evento_inexistente_respondem_404(cliente, sessao):
    resposta = cliente.get(rota(uuid.uuid4()), headers=cabecalhos(criar_usuario()))

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "evento_inexistente"


def test_os_descendentes_sem_token_respondem_401(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.get(rota(evento.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
