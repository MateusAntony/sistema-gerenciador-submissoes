"""Testes de ponta a ponta das chamadas — API-16 AC1..AC5, AC9, AC10 (T39)."""

import uuid

from app.extensions import db
from app.modules.eventos.models import Chamada
from tests.e2e.apoio_de_chamadas import (
    ABERTURA,
    LIMITE,
    criar_chamada,
    rota_da_chamada,
    rota_da_lista,
)
from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_chair,
    criar_evento,
    criar_usuario,
)


def corpo_valido(**extras) -> dict:
    corpo = {
        "titulo": "Chamada de Trabalhos",
        "dataAbertura": ABERTURA,
        "dataLimite": LIMITE,
    }
    corpo.update(extras)
    return corpo


# AC1 — `GET` devolve as chamadas do evento.


def test_a_listagem_devolve_as_chamadas_do_evento(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento, titulo="Chamada Principal")

    resposta = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair))

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert len(corpo) == 1
    assert corpo[0]["id"] == str(chamada.id)
    assert corpo[0]["eventoId"] == str(evento.id)
    assert corpo[0]["titulo"] == "Chamada Principal"


def test_a_listagem_nao_traz_chamadas_de_outro_evento(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_chamada(evento, titulo="Minha")
    criar_chamada(criar_evento(), titulo="Alheia")

    corpo = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair)).get_json()

    assert [chamada["titulo"] for chamada in corpo] == ["Minha"]


# AC2 — `POST` devolve 201 com `encerradaManualmente: false` e `versao: 1`.


def test_a_criacao_responde_201_com_a_chamada_aberta_na_versao_um(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido()
    )

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["titulo"] == "Chamada de Trabalhos"
    assert corpo["eventoId"] == str(evento.id)
    assert corpo["encerradaManualmente"] is False
    assert corpo["versao"] == 1


def test_a_criacao_persiste_a_chamada(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json=corpo_valido()
    )

    gravadas = db.session.query(Chamada).filter_by(evento_id=evento.id).all()
    assert [chamada.titulo for chamada in gravadas] == ["Chamada de Trabalhos"]


# AC3 — `dataLimite` <= `dataAbertura` e 422, na criacao **e** na edicao.


def test_a_criacao_com_limite_anterior_a_abertura_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json=corpo_valido(dataAbertura=LIMITE, dataLimite=ABERTURA),
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "dataLimite" in corpo["campos"]


def test_a_criacao_com_limite_igual_a_abertura_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json=corpo_valido(dataLimite=ABERTURA),
    )

    assert resposta.status_code == 422
    assert "dataLimite" in resposta.get_json()["campos"]


def test_a_edicao_com_limite_anterior_a_abertura_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento)

    resposta = cliente.patch(
        rota_da_chamada(chamada.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "dataLimite": ABERTURA},
    )

    assert resposta.status_code == 422
    assert "dataLimite" in resposta.get_json()["campos"]
    assert db.session.get(Chamada, chamada.id).versao == 1


# AC4 / D2 — `PATCH` com `versao` divergente: 409 com a chamada em `atual`.


def test_a_edicao_com_versao_divergente_responde_409_com_a_chamada_atual(
    cliente, sessao
):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento, titulo="Título Vigente")

    resposta = cliente.patch(
        rota_da_chamada(chamada.id),
        headers=cabecalhos(chair),
        json={"versao": 9, "titulo": "Título Perdido"},
    )

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "conflito_de_versao"
    assert corpo["atual"]["id"] == str(chamada.id)
    assert corpo["atual"]["titulo"] == "Título Vigente"
    assert corpo["atual"]["versao"] == 1
    assert db.session.get(Chamada, chamada.id).titulo == "Título Vigente"


# AC5 — `PATCH` com sucesso incrementa `versao` em 1.


def test_a_edicao_bem_sucedida_incrementa_a_versao_em_um(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento)

    resposta = cliente.patch(
        rota_da_chamada(chamada.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "titulo": "Título Novo"},
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["titulo"] == "Título Novo"
    assert corpo["versao"] == 2
    assert db.session.get(Chamada, chamada.id).versao == 2


# AC9 — `tamanhoMaximoMb` acima do limite do servidor.


def test_tamanho_maximo_acima_do_limite_do_servidor_responde_422(
    cliente, sessao, aplicacao
):
    evento = criar_evento()
    chair = criar_chair(evento)
    acima = aplicacao.config["TAMANHO_MAXIMO_DE_ANEXO_MB"] + 1

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json=corpo_valido(tamanhoMaximoMb=acima),
    )

    assert resposta.status_code == 422
    assert "tamanhoMaximoMb" in resposta.get_json()["campos"]


def test_tamanho_maximo_no_limite_do_servidor_e_aceito(cliente, sessao, aplicacao):
    evento = criar_evento()
    chair = criar_chair(evento)
    no_limite = aplicacao.config["TAMANHO_MAXIMO_DE_ANEXO_MB"]

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json=corpo_valido(tamanhoMaximoMb=no_limite),
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["tamanhoMaximoMb"] == no_limite


def test_tamanho_maximo_acima_do_limite_tambem_e_422_na_edicao(
    cliente, sessao, aplicacao
):
    evento = criar_evento()
    chair = criar_chair(evento)
    chamada = criar_chamada(evento)
    acima = aplicacao.config["TAMANHO_MAXIMO_DE_ANEXO_MB"] + 1

    resposta = cliente.patch(
        rota_da_chamada(chamada.id),
        headers=cabecalhos(chair),
        json={"versao": 1, "tamanhoMaximoMb": acima},
    )

    assert resposta.status_code == 422
    assert "tamanhoMaximoMb" in resposta.get_json()["campos"]


# AC10 — chamada inexistente e 404 `chamada_inexistente`.


def test_a_edicao_de_chamada_inexistente_responde_404(cliente, sessao):
    resposta = cliente.patch(
        rota_da_chamada(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"versao": 1, "titulo": "X"},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "chamada_inexistente"


def test_a_edicao_de_chamada_inexistente_com_corpo_invalido_responde_404(
    cliente, sessao
):
    """Estado antes de corpo: o 404 tem precedencia sobre o 422."""
    resposta = cliente.patch(
        rota_da_chamada(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"campoQueNaoExiste": True},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "chamada_inexistente"


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
        rota_da_lista(evento.id), headers=cabecalhos(criar_usuario()), json=corpo_valido()
    )

    assert resposta.status_code == 403
    assert db.session.query(Chamada).filter_by(evento_id=evento.id).count() == 0


def test_a_edicao_por_quem_nao_e_chair_do_evento_responde_403(cliente, sessao):
    evento = criar_evento()
    chamada = criar_chamada(evento, titulo="Original")

    resposta = cliente.patch(
        rota_da_chamada(chamada.id),
        headers=cabecalhos(criar_usuario()),
        json={"versao": 1, "titulo": "Invadida"},
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert db.session.get(Chamada, chamada.id).titulo == "Original"


def test_a_listagem_sem_token_responde_401(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.get(rota_da_lista(evento.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
