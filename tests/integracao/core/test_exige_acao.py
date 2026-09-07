"""Testes da guarda de autorizacao por papel — API-09 AC1..AC5 (T23).

A guarda e exercitada pelas rotas sinteticas de `tests/rotas_de_guarda`, pelo
cliente HTTP: o que as ACs afirmam sao codigos de status, e so a borda os produz.
"""

import uuid

from flask_jwt_extended import create_access_token

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import ParticipacaoRepository

GESTAO = "/api/_teste/eventos/{evento_id}/gestao"
RECURSO = "/api/_teste/eventos/{evento_id}/recurso"
ADMIN = "/api/_teste/admin/contas"


def criar_usuario(
    email: str = "guarda@exemplo.test", *, administrador: bool = False
) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace", email=email, senha_hash="hash-irrelevante"
    )
    usuario.email_confirmado = True
    usuario.administrador = administrador
    return usuario


def criar_evento(sessao, titulo: str = "Simpósio de Extensão") -> Evento:
    evento = Evento(
        situacao="aprovado",
        titulo=titulo,
        ano=2026,
        identificador_pagina=f"evento-{uuid.uuid4().hex[:8]}",
    )
    sessao.add(evento)
    sessao.flush()
    return evento


def autenticado(usuario: Usuario) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(identity=str(usuario.id))}"}


# AC1 — 403 `sem_permissao` para quem nao tem o papel exigido naquele evento.


def test_usuario_sem_participacao_recebe_403_sem_permissao_na_gestao(
    cliente, sessao
):
    usuario = criar_usuario()
    evento = criar_evento(sessao)

    resposta = cliente.get(
        GESTAO.format(evento_id=evento.id), headers=autenticado(usuario)
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_avaliador_do_evento_nao_configura_o_evento(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "avaliador")

    resposta = cliente.get(
        GESTAO.format(evento_id=evento.id), headers=autenticado(usuario)
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_chair_de_outro_evento_recebe_403_no_evento_alheio(cliente, sessao):
    usuario = criar_usuario()
    proprio = criar_evento(sessao, titulo="Congresso A")
    alheio = criar_evento(sessao, titulo="Congresso B")
    ParticipacaoRepository.criar(proprio.id, usuario.id, "chair")

    resposta = cliente.get(
        GESTAO.format(evento_id=alheio.id), headers=autenticado(usuario)
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_chair_do_evento_passa_na_rota_de_gestao(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")

    resposta = cliente.get(
        GESTAO.format(evento_id=evento.id), headers=autenticado(usuario)
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["eventoId"] == str(evento.id)


def test_a_participacao_de_chair_inativa_nao_abre_a_gestao(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    participacao = ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    participacao.ativo = False
    sessao.flush()

    resposta = cliente.get(
        GESTAO.format(evento_id=evento.id), headers=autenticado(usuario)
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


# AC2 — 403 em `/admin/*` para `administrador: false`.


def test_rota_de_admin_recusa_usuario_que_nao_e_administrador(cliente, sessao):
    usuario = criar_usuario()

    resposta = cliente.get(ADMIN, headers=autenticado(usuario))

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_ser_chair_de_um_evento_nao_abre_a_rota_de_admin(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")

    resposta = cliente.get(ADMIN, headers=autenticado(usuario))

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_rota_de_admin_aceita_administrador(cliente, sessao):
    usuario = criar_usuario(administrador=True)

    resposta = cliente.get(ADMIN, headers=autenticado(usuario))

    assert resposta.status_code == 200
    assert resposta.get_json()["usuario"] == str(usuario.id)


# AC3 — sem token e 401, nao 403; a distincao e preservada.


def test_a_gestao_sem_token_responde_401_e_nao_403(cliente, sessao):
    evento = criar_evento(sessao)

    resposta = cliente.get(GESTAO.format(evento_id=evento.id))

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_rota_de_admin_sem_token_responde_401_e_nao_403(cliente, sessao):
    resposta = cliente.get(ADMIN)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_gestao_com_token_invalido_responde_401_e_nao_403(cliente, sessao):
    evento = criar_evento(sessao)

    resposta = cliente.get(
        GESTAO.format(evento_id=evento.id),
        headers={"Authorization": "Bearer isto-nao-e-um-jwt"},
    )

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


def test_a_gestao_com_conta_desativada_responde_401_e_nao_403(cliente, sessao):
    usuario = criar_usuario()
    evento = criar_evento(sessao)
    ParticipacaoRepository.criar(evento.id, usuario.id, "chair")
    cabecalhos = autenticado(usuario)
    usuario.ativo = False
    sessao.flush()

    resposta = cliente.get(GESTAO.format(evento_id=evento.id), headers=cabecalhos)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "nao_autenticado"


# AC4 — administrador passa na gestao de qualquer evento, sem participacao.


def test_administrador_passa_na_gestao_de_evento_em_que_nao_participa(
    cliente, sessao
):
    usuario = criar_usuario(administrador=True)
    evento = criar_evento(sessao)

    resposta = cliente.get(
        GESTAO.format(evento_id=evento.id), headers=autenticado(usuario)
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["eventoId"] == str(evento.id)


# AC5 — a autorizacao roda antes da busca: inexistente + sem permissao e 403.


def test_evento_inexistente_para_quem_nao_tem_permissao_responde_403_e_nao_404(
    cliente, sessao
):
    usuario = criar_usuario()

    resposta = cliente.get(
        RECURSO.format(evento_id=uuid.uuid4()), headers=autenticado(usuario)
    )

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "sem_permissao"


def test_evento_inexistente_para_quem_tem_permissao_responde_404(cliente, sessao):
    # O par com o teste acima e o que prova a ordem: a mesma rota, o mesmo id
    # inexistente, e o 404 so aparece depois que a guarda deixa passar.
    usuario = criar_usuario(administrador=True)

    resposta = cliente.get(
        RECURSO.format(evento_id=uuid.uuid4()), headers=autenticado(usuario)
    )

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "evento_inexistente"
