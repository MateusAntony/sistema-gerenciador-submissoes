"""Testes de ponta a ponta das trilhas do evento — API-15 AC1..AC7 (T38)."""

import uuid

from app.extensions import db
from app.modules.areas_futuras.models import Submissao
from app.modules.eventos.models import Chamada, Trilha
from tests.e2e.apoio_de_eventos import (
    cabecalhos,
    criar_chair,
    criar_evento,
    criar_usuario,
    fixar,
)


def rota_da_lista(evento_id) -> str:
    return f"/api/eventos/{evento_id}/trilhas"


def rota_da_trilha(trilha_id) -> str:
    return f"/api/trilhas/{trilha_id}"


def criar_trilha(evento, *, nome: str = "Trilha Principal", ativa: bool = True):
    trilha = Trilha(evento_id=evento.id, nome=nome, ativa=ativa)
    db.session.add(trilha)
    fixar()
    return trilha


def vincular_submissao(evento, trilha) -> None:
    """Uma submissao real ligada a trilha, para a contagem ter o que contar."""
    from datetime import datetime, timezone

    chamada = Chamada(
        evento_id=evento.id,
        titulo="Chamada",
        data_abertura=datetime(2026, 1, 1, tzinfo=timezone.utc),
        data_limite=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db.session.add(chamada)
    db.session.flush()
    db.session.add(Submissao(chamada_id=chamada.id, trilha_id=trilha.id))
    fixar()


# AC1 — `GET` devolve as trilhas do evento com `submissoesVinculadas` derivado.


def test_a_listagem_devolve_as_trilhas_do_evento(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    trilha = criar_trilha(evento, nome="Educação")

    resposta = cliente.get(rota_da_lista(evento.id), headers=cabecalhos(chair))

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert len(corpo) == 1
    assert corpo[0]["id"] == str(trilha.id)
    assert corpo[0]["eventoId"] == str(evento.id)
    assert corpo[0]["nome"] == "Educação"
    assert corpo[0]["ativa"] is True


def test_a_listagem_nao_traz_trilhas_de_outro_evento(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_trilha(evento, nome="Minha")
    criar_trilha(criar_evento(), nome="Alheia")

    corpo = cliente.get(
        rota_da_lista(evento.id), headers=cabecalhos(chair)
    ).get_json()

    assert [trilha["nome"] for trilha in corpo] == ["Minha"]


def test_submissoes_vinculadas_e_zero_sem_submissao_alguma(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_trilha(evento)

    corpo = cliente.get(
        rota_da_lista(evento.id), headers=cabecalhos(chair)
    ).get_json()

    assert corpo[0]["submissoesVinculadas"] == 0


def test_submissoes_vinculadas_conta_as_submissoes_da_trilha(cliente, sessao):
    """AC1 — a contagem e derivada por consulta: com linha inserida ela sobe."""
    evento = criar_evento()
    chair = criar_chair(evento)
    trilha = criar_trilha(evento)
    vincular_submissao(evento, trilha)

    corpo = cliente.get(
        rota_da_lista(evento.id), headers=cabecalhos(chair)
    ).get_json()

    assert corpo[0]["submissoesVinculadas"] == 1


# AC2 — `POST` devolve 201, `ativa: true`, `submissoesVinculadas: 0`.


def test_a_criacao_responde_201_com_a_trilha_ativa_e_sem_submissoes(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id),
        headers=cabecalhos(chair),
        json={"nome": "Saúde", "descricao": "Trabalhos da área de saúde"},
    )

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["nome"] == "Saúde"
    assert corpo["descricao"] == "Trabalhos da área de saúde"
    assert corpo["eventoId"] == str(evento.id)
    assert corpo["ativa"] is True
    assert corpo["submissoesVinculadas"] == 0


def test_a_criacao_persiste_a_trilha(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json={"nome": "Saúde"}
    )

    gravadas = db.session.query(Trilha).filter_by(evento_id=evento.id).all()
    assert [trilha.nome for trilha in gravadas] == ["Saúde"]


# AC3 — `nome` vazio e 422 em `campos.nome`.


def test_a_criacao_com_nome_vazio_responde_422_no_nome(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json={"nome": ""}
    )

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "nome" in corpo["campos"]


# AC7 — nome repetido dentro do mesmo evento e 422 em `campos.nome`.


def test_a_criacao_com_nome_repetido_no_mesmo_evento_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_trilha(evento, nome="Educação")

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json={"nome": "Educação"}
    )

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["campos"]


def test_o_mesmo_nome_em_outro_evento_e_permitido(cliente, sessao):
    """A unicidade e por evento: dois eventos podem ter a trilha 'Educação'."""
    criar_trilha(criar_evento(), nome="Educação")
    evento = criar_evento()
    chair = criar_chair(evento)

    resposta = cliente.post(
        rota_da_lista(evento.id), headers=cabecalhos(chair), json={"nome": "Educação"}
    )

    assert resposta.status_code == 201
    assert resposta.get_json()["nome"] == "Educação"


# AC4 — `PATCH` aplica e devolve a trilha com a contagem atualizada.


def test_a_edicao_aplica_e_devolve_a_trilha(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    trilha = criar_trilha(evento, nome="Antigo")

    resposta = cliente.patch(
        rota_da_trilha(trilha.id),
        headers=cabecalhos(chair),
        json={"nome": "Novo", "descricao": "Descrição nova"},
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["nome"] == "Novo"
    assert corpo["descricao"] == "Descrição nova"
    assert db.session.get(Trilha, trilha.id).nome == "Novo"


def test_a_edicao_com_nome_repetido_no_mesmo_evento_responde_422(cliente, sessao):
    evento = criar_evento()
    chair = criar_chair(evento)
    criar_trilha(evento, nome="Educação")
    outra = criar_trilha(evento, nome="Saúde")

    resposta = cliente.patch(
        rota_da_trilha(outra.id), headers=cabecalhos(chair), json={"nome": "Educação"}
    )

    assert resposta.status_code == 422
    assert "nome" in resposta.get_json()["campos"]


# AC5 — desativar trilha com submissoes vinculadas **e permitido**, com a contagem.


def test_desativar_trilha_com_submissoes_e_permitido_e_devolve_a_contagem(
    cliente, sessao
):
    evento = criar_evento()
    chair = criar_chair(evento)
    trilha = criar_trilha(evento)
    vincular_submissao(evento, trilha)

    resposta = cliente.patch(
        rota_da_trilha(trilha.id), headers=cabecalhos(chair), json={"ativa": False}
    )

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert corpo["ativa"] is False
    assert corpo["submissoesVinculadas"] == 1
    assert db.session.get(Trilha, trilha.id).ativa is False


# AC6 — trilha inexistente e 404 `trilha_inexistente`.


def test_a_edicao_de_trilha_inexistente_responde_404(cliente, sessao):
    resposta = cliente.patch(
        rota_da_trilha(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"nome": "X"},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "trilha_inexistente"


def test_a_edicao_de_trilha_inexistente_com_corpo_invalido_responde_404(
    cliente, sessao
):
    """Estado antes de corpo: o 404 tem precedencia sobre o 422."""
    resposta = cliente.patch(
        rota_da_trilha(uuid.uuid4()),
        headers=cabecalhos(criar_usuario(administrador=True)),
        json={"nome": ""},
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "trilha_inexistente"


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
        json={"nome": "Invadida"},
    )

    assert resposta.status_code == 403
    assert db.session.query(Trilha).filter_by(evento_id=evento.id).count() == 0


def test_a_edicao_por_quem_nao_e_chair_do_evento_responde_403(cliente, sessao):
    evento = criar_evento()
    trilha = criar_trilha(evento, nome="Original")

    resposta = cliente.patch(
        rota_da_trilha(trilha.id),
        headers=cabecalhos(criar_usuario()),
        json={"nome": "Invadida"},
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"
    assert db.session.get(Trilha, trilha.id).nome == "Original"


def test_a_listagem_sem_token_responde_401(cliente, sessao):
    evento = criar_evento()

    resposta = cliente.get(rota_da_lista(evento.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"
