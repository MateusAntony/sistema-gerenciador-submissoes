"""Testes de ponta a ponta dos criterios — API-17 AC1..AC4, AC8 (T41)."""

import uuid

from app.extensions import db
from app.modules.eventos.models import CriterioAvaliacao
from tests.e2e.apoio_de_criterios import (
    criar_criterio,
    registrar_nota,
    rota_da_lista,
    rota_do_criterio,
)
from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_chair,
    criar_evento,
    criar_usuario,
)


def corpo_valido(**extras) -> dict:
    corpo = {
        "titulo": "Originalidade",
        "notaMinima": 0,
        "notaMaxima": 10,
        "peso": 1,
    }
    corpo.update(extras)
    return corpo


# AC1 — `GET` devolve os criterios com `temNotas` derivado por consulta.


def test_a_listagem_devolve_os_criterios_do_evento(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, titulo="Relevância", ordem=1)

    resposta = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair))

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert len(corpo) == 1
    assert corpo[0]["id"] == str(criterio.id)
    assert corpo[0]["eventoId"] == str(evento.id)
    assert corpo[0]["titulo"] == "Relevância"
    assert corpo[0]["notaMinima"] == 0
    assert corpo[0]["notaMaxima"] == 10
    assert corpo[0]["peso"] == 1
    assert corpo[0]["ordem"] == 1
    assert corpo[0]["ativo"] is True


def test_a_listagem_nao_traz_criterios_de_outro_evento(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_criterio(evento, titulo="Meu", ordem=1)
    criar_criterio(criar_evento(), titulo="Alheio", ordem=1)

    corpo = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair)).get_json()

    assert [criterio["titulo"] for criterio in corpo] == ["Meu"]


def test_tem_notas_e_falso_sem_nota_alguma(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_criterio(evento, ordem=1)

    corpo = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair)).get_json()

    assert corpo[0]["temNotas"] is False


def test_tem_notas_e_verdadeiro_com_nota_registrada(cliente, sessao):
    """AC1 — `temNotas` e derivado por consulta: com linha inserida ele vira True."""
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)
    registrar_nota(criterio)

    corpo = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair)).get_json()

    assert corpo[0]["temNotas"] is True


# AC2 — `POST` devolve 201 com `ativo: true` e `temNotas: false`.


def test_a_criacao_responde_201_com_o_criterio_ativo_e_sem_notas(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido()
    )

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["titulo"] == "Originalidade"
    assert corpo["eventoId"] == str(evento.id)
    assert corpo["notaMinima"] == 0
    assert corpo["notaMaxima"] == 10
    assert corpo["peso"] == 1
    assert corpo["ativo"] is True
    assert corpo["temNotas"] is False


def test_a_criacao_persiste_o_criterio(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido()
    )

    gravados = db.session.query(CriterioAvaliacao).filter_by(evento_id=evento.id).all()
    assert [criterio.titulo for criterio in gravados] == ["Originalidade"]


# AC3 — `notaMaxima` <= `notaMinima` e 422, na criacao **e** na edicao.


def test_a_criacao_com_nota_maxima_menor_que_a_minima_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json=corpo_valido(notaMinima=8, notaMaxima=5),
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "notaMaxima" in corpo["campos"]


def test_a_criacao_com_nota_maxima_igual_a_minima_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json=corpo_valido(notaMinima=5, notaMaxima=5),
    )

    assert resposta.status_code == 422
    assert "notaMaxima" in resposta.get_json()["campos"]


def test_a_edicao_com_nota_maxima_menor_que_a_minima_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)

    resposta = cliente.patch(
        rota_do_criterio(criterio.id),
        headers=cabecalhos(chair),
        json={"notaMaxima": 0},
    )

    assert resposta.status_code == 422
    assert "notaMaxima" in resposta.get_json()["campos"]
    assert float(db.session.get(CriterioAvaliacao, criterio.id).nota_maxima) == 10


# AC4 — `peso` <= 0 e 422, na criacao **e** na edicao.


def test_a_criacao_com_peso_zero_responde_422_no_peso(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido(peso=0)
    )

    assert resposta.status_code == 422
    assert "peso" in resposta.get_json()["campos"]


def test_a_criacao_com_peso_negativo_responde_422_no_peso(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido(peso=-2)
    )

    assert resposta.status_code == 422
    assert "peso" in resposta.get_json()["campos"]


def test_a_edicao_com_peso_zero_responde_422_no_peso(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, ordem=1)

    resposta = cliente.patch(
        rota_do_criterio(criterio.id), headers=cabecalhos(chair), json={"peso": 0}
    )

    assert resposta.status_code == 422
    assert "peso" in resposta.get_json()["campos"]
    assert float(db.session.get(CriterioAvaliacao, criterio.id).peso) == 1


# Edicao bem-sucedida.


def test_a_edicao_aplica_e_devolve_o_criterio(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criterio = criar_criterio(evento, titulo="Antigo", ordem=1)

    resposta = cliente.patch(
        rota_do_criterio(criterio.id),
        headers=cabecalhos(chair),
        json={"titulo": "Novo", "ativo": False},
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["titulo"] == "Novo"
    assert corpo["ativo"] is False
    assert db.session.get(CriterioAvaliacao, criterio.id).titulo == "Novo"


# AC8 — `ordem` ausente recebe a proxima posicao livre **dentro daquele evento**.


def test_a_ordem_ausente_recebe_a_primeira_posicao_no_evento_vazio(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    corpo = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido()
    ).get_json()

    assert corpo["ordem"] == 1


def test_a_ordem_ausente_recebe_a_proxima_posicao_livre(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_criterio(evento, titulo="Primeiro", ordem=1)
    criar_criterio(evento, titulo="Segundo", ordem=2)

    corpo = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido()
    ).get_json()

    assert corpo["ordem"] == 3


def test_a_numeracao_da_ordem_nao_vaza_entre_eventos(cliente, sessao):
    """AC8 — a proxima posicao livre e **daquele evento**, nao global.

    Com dois eventos, o primeiro criterio do segundo evento tem de ser 1: se a
    consulta ignorasse o evento, viria 4.
    """
    povoado = criar_evento(titulo="Povoado")
    criar_criterio(povoado, titulo="A", ordem=1)
    criar_criterio(povoado, titulo="B", ordem=2)
    criar_criterio(povoado, titulo="C", ordem=3)

    vazio = criar_evento(titulo="Vazio")
    chair = criar_chair(vazio)

    corpo = cliente.post(
        rota_da_lista(vazio.id), headers=cabecalhos(chair), json=corpo_valido()
    ).get_json()

    assert corpo["ordem"] == 1


def test_a_ordem_informada_e_respeitada(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    corpo = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido(ordem=7)
    ).get_json()

    assert corpo["ordem"] == 7


# AC7 — criterio inexistente e 404 `criterio_inexistente`.


def test_a_edicao_de_criterio_inexistente_responde_404(cliente, sessao):
    resposta = cliente.patch(
        rota_do_criterio(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"titulo": "X"},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "criterio_inexistente"


def test_a_edicao_de_criterio_inexistente_com_corpo_invalido_responde_404(
    cliente, sessao
):
    """Estado antes de corpo: o 404 tem precedencia sobre o 422."""
    resposta = cliente.patch(
        rota_do_criterio(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"campoQueNaoExiste": 1},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "criterio_inexistente"


# RBAC (AD-008) — 403 para quem nao e chair do evento.


def test_a_listagem_por_quem_nao_e_chair_responde_403(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.get(
        rota_da_lista(evento.id), headers=cabecalhos(criar_usuario())
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_a_criacao_por_quem_nao_e_chair_responde_403(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(criar_usuario()),
        json=corpo_valido(),
    )

    assert resposta.status_code == 403
    assert db.session.query(CriterioAvaliacao).filter_by(evento_id=evento.id).count() == 0


def test_a_edicao_por_quem_nao_e_chair_do_evento_responde_403(cliente, sessao):
    evento = criar_evento()
    criterio = criar_criterio(evento, titulo="Original", ordem=1)

    resposta = cliente.patch(
        rota_do_criterio(criterio.id),
        headers=cabecalhos(criar_usuario()),
        json={"titulo": "Invadido"},
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert db.session.get(CriterioAvaliacao, criterio.id).titulo == "Original"


def test_a_listagem_sem_token_responde_401(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.get(rota_da_lista(evento.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
