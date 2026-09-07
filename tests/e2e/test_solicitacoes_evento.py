"""Testes de ponta a ponta de `POST /api/solicitacoes-evento` — API-11 AC1..AC5 (T29).

A entrada de todo evento no sistema: o 201 com a solicitacao completa e os
cinco caminhos de recusa que o formulario do front precisa distinguir.
"""

import uuid

from flask_jwt_extended import create_access_token

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import EventoRepository, SolicitacaoRepository

ROTA = "/api/solicitacoes-evento"


def criar_usuario(email: str = "organizador@exemplo.test") -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    return usuario


def cabecalhos(usuario: Usuario) -> dict:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


def corpo_valido(**alteracoes) -> dict:
    corpo = {
        "titulo": "Simpósio de Extensão",
        "identificadorPagina": f"simposio-{uuid.uuid4().hex[:8]}",
        "dataInicio": "2026-05-01",
        "dataTermino": "2026-05-03",
        "ano": 2026,
        "tipo": "conferencia",
        "pais": "Brasil",
        "fuso": "America/Bahia",
        "justificativa": "Evento anual do curso.",
    }
    corpo.update(alteracoes)
    return corpo


def criar_evento(
    sessao, identificador: str, pai_id=None, situacao: str = "aprovado"
) -> Evento:
    """`situacao` e parametro porque a AC5 distingue pai aprovado de nao aprovado.

    Enquanto o helper fixava `aprovado`, a metade "ou nao aprovado" da AC nunca
    era exercitada — foi assim que o defeito passou pelo gate.
    """
    return EventoRepository.criar(
        situacao=situacao,
        titulo="Evento existente",
        ano=2026,
        identificador_pagina=identificador,
        evento_pai_id=pai_id,
    )


def solicitar(cliente, usuario: Usuario | None = None, corpo: dict | None = None):
    return cliente.post(
        ROTA,
        json=corpo_valido() if corpo is None else corpo,
        headers={} if usuario is None else cabecalhos(usuario),
    )


# AC1 — 201 com a solicitacao completa, `pendente`, `criadoEm` e `versao: 1`.


def test_a_criacao_responde_201_com_a_solicitacao_pendente_na_versao_um(
    cliente, sessao
):
    usuario = criar_usuario()

    resposta = solicitar(
        cliente, usuario, corpo_valido(identificadorPagina="simposio-2026")
    )

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["situacao"] == "pendente"
    assert corpo["versao"] == 1
    assert corpo["solicitanteId"] == str(usuario.id)
    assert corpo["identificadorPagina"] == "simposio-2026"
    assert corpo["titulo"] == "Simpósio de Extensão"
    assert corpo["criadoEm"].endswith("Z")
    assert uuid.UUID(corpo["id"])


def test_a_criacao_grava_os_chairs_iniciais_com_o_sinal_de_conta(cliente, sessao):
    usuario = criar_usuario()
    criar_usuario(email="ana@exemplo.test")

    corpo = solicitar(
        cliente,
        usuario,
        corpo_valido(
            chairsIniciais=[
                {"email": "ana@exemplo.test"},
                {"email": "sem-conta@exemplo.test"},
            ]
        ),
    ).get_json()

    assert corpo["chairsIniciais"] == [
        {"email": "ana@exemplo.test", "temConta": True},
        {"email": "sem-conta@exemplo.test", "temConta": False},
    ]


# AC2 — identificador ja em uso em solicitacao **ou** evento e 422 no campo.


def test_o_identificador_ja_usado_por_outra_solicitacao_responde_422_no_campo(
    cliente, sessao
):
    usuario = criar_usuario()
    solicitar(cliente, usuario, corpo_valido(identificadorPagina="repetido-2026"))

    resposta = solicitar(
        cliente, usuario, corpo_valido(identificadorPagina="repetido-2026")
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "identificadorPagina" in corpo["campos"]


def test_o_identificador_ja_usado_por_um_evento_responde_422_no_campo(cliente, sessao):
    usuario = criar_usuario()
    criar_evento(sessao, "evento-existente-2026")

    resposta = solicitar(
        cliente, usuario, corpo_valido(identificadorPagina="evento-existente-2026")
    )

    assert resposta.status_code == 422
    assert "identificadorPagina" in resposta.get_json()["campos"]


# AC3 — campo obrigatorio ausente ou vazio e 422 nomeando o campo.


def test_o_titulo_ausente_responde_422_nomeando_titulo(cliente, sessao):
    corpo = corpo_valido()
    del corpo["titulo"]

    resposta = solicitar(cliente, criar_usuario(), corpo)

    assert resposta.status_code == 422
    assert "titulo" in resposta.get_json()["campos"]


def test_o_identificador_vazio_responde_422_nomeando_identificador(cliente, sessao):
    resposta = solicitar(
        cliente, criar_usuario(), corpo_valido(identificadorPagina="")
    )

    assert resposta.status_code == 422
    assert "identificadorPagina" in resposta.get_json()["campos"]


def test_a_data_de_inicio_ausente_responde_422_nomeando_data_inicio(cliente, sessao):
    corpo = corpo_valido()
    del corpo["dataInicio"]

    resposta = solicitar(cliente, criar_usuario(), corpo)

    assert resposta.status_code == 422
    assert "dataInicio" in resposta.get_json()["campos"]


def test_a_data_de_termino_ausente_responde_422_nomeando_data_termino(cliente, sessao):
    corpo = corpo_valido()
    del corpo["dataTermino"]

    resposta = solicitar(cliente, criar_usuario(), corpo)

    assert resposta.status_code == 422
    assert "dataTermino" in resposta.get_json()["campos"]


# AC4 — termino anterior ao inicio e 422 em `dataTermino`.


def test_o_termino_anterior_ao_inicio_responde_422_em_data_termino(cliente, sessao):
    resposta = solicitar(
        cliente,
        criar_usuario(),
        corpo_valido(dataInicio="2026-05-10", dataTermino="2026-05-01"),
    )

    assert resposta.status_code == 422
    campos = resposta.get_json()["campos"]
    assert "dataTermino" in campos
    assert "dataInicio" not in campos


# AC5 — `eventoPaiId` que fecha ciclo e 422 em `eventoPaiId`.


def test_o_evento_pai_inexistente_responde_422_em_evento_pai_id(cliente, sessao):
    resposta = solicitar(
        cliente, criar_usuario(), corpo_valido(eventoPaiId=str(uuid.uuid4()))
    )

    assert resposta.status_code == 422
    assert "eventoPaiId" in resposta.get_json()["campos"]


def test_o_evento_pai_existente_e_aceito_e_ecoado_na_resposta(cliente, sessao):
    pai = criar_evento(sessao, "pai-2026")

    resposta = solicitar(
        cliente, criar_usuario(), corpo_valido(eventoPaiId=str(pai.id))
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["eventoPaiId"] == str(pai.id)


# API-09 AC3 — sem token e 401.


def test_a_criacao_sem_token_responde_401_nao_autenticado(cliente, sessao):
    resposta = solicitar(cliente)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
    assert SolicitacaoRepository.listar() == []


# AC5 — a outra metade: pai que existe mas ainda nao foi aprovado.


def test_evento_pai_pendente_de_aprovacao_responde_422(cliente, sessao):
    """Um evento que o administrador ainda nao aprovou nao pode ser pai.

    Aceitar isto deixaria a hierarquia pendurada num evento que pode ser
    recusado depois, e a AC5 exige 422 para pai "inexistente **ou nao
    aprovado**". O defeito existia porque o helper de teste fixava
    `situacao="aprovado"`: a metade da AC nunca chegava ao codigo.
    """
    pai = criar_evento(sessao, "pai-pendente", situacao="pendente_aprovacao")

    resposta = solicitar(
        cliente, criar_usuario(), corpo_valido(eventoPaiId=str(pai.id))
    )

    assert resposta.status_code == 422
    assert "eventoPaiId" in resposta.get_json()["campos"]


def test_evento_pai_encerrado_responde_422(cliente, sessao):
    pai = criar_evento(sessao, "pai-encerrado", situacao="encerrado")

    resposta = solicitar(
        cliente, criar_usuario(), corpo_valido(eventoPaiId=str(pai.id))
    )

    assert resposta.status_code == 422
    assert "eventoPaiId" in resposta.get_json()["campos"]


def test_evento_pai_publicado_e_aceito(cliente, sessao):
    """`publicado` e um evento aprovado que ja abriu — continua sendo pai valido."""
    pai = criar_evento(sessao, "pai-publicado", situacao="publicado")

    resposta = solicitar(
        cliente, criar_usuario(), corpo_valido(eventoPaiId=str(pai.id))
    )

    assert resposta.status_code == 201
