"""Testes de ponta a ponta de `POST /api/convites/{token}/aceitar` (T27).

API-08 AC7..AC9 e o Edge Case de quem aceita logado com outra conta. O aceite e
a porta de entrada de quem ainda nao tem conta (AD-009): o que se afirma aqui e
que ele cria a conta ja confirmada, cria a participacao, abre sessao de verdade
e nao deixa nada pela metade quando falha.
"""

import uuid
from datetime import timedelta

from app.extensions import bcrypt, db
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import agora
from app.modules.convites.service import (
    MENSAGEM_DE_CONVITE_JA_USADO,
    ConviteService,
)
from app.modules.eventos.models import Evento
from app.modules.eventos.repository import ParticipacaoRepository

ACEITAR = "/api/convites/{token}/aceitar"
LOGIN = "/api/auth/login"

EMAIL = "convidada@exemplo.test"
SENHA = "senha-bem-forte-1"
CONTATO = "organizacao@exemplo.br"

CAMPOS_DO_USUARIO = {
    "id",
    "nome",
    "email",
    "emailConfirmado",
    "administrador",
    "ativo",
}


def criar_evento(sessao, titulo: str = "Congresso de Computação") -> Evento:
    evento = Evento(
        situacao="aprovado",
        titulo=titulo,
        ano=2026,
        identificador_pagina=f"evento-{uuid.uuid4().hex[:8]}",
        fuso="America/Bahia",
    )
    sessao.add(evento)
    sessao.flush()
    return evento


def criar_convite(sessao, email: str = EMAIL, papel: str = "chair"):
    evento = criar_evento(sessao)
    convite, token = ConviteService.criar_para_participacao(evento, email, papel)
    convite.contato_organizacao = CONTATO
    sessao.flush()
    return convite, token


def criar_conta(sessao, email: str = EMAIL, nome: str = "Ada Lovelace") -> Usuario:
    usuario = ContaRepository.criar(
        nome=nome,
        email=email,
        senha_hash=bcrypt.generate_password_hash(SENHA).decode("utf-8"),
    )
    usuario.email_confirmado = True
    sessao.flush()
    return usuario


def aceitar(cliente, token: str, corpo: dict | None = None, cabecalhos=None):
    return cliente.post(
        ACEITAR.format(token=token), json=corpo or {}, headers=cabecalhos or {}
    )


# AC7 — e-mail sem conta: cria conta confirmada, participacao, sessao e cookie.


def test_aceite_de_email_sem_conta_cria_a_conta_ja_confirmada(cliente, sessao):
    _, token = criar_convite(sessao)

    resposta = aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == {"tokenDeAcesso", "usuario"}
    assert set(corpo["usuario"]) == CAMPOS_DO_USUARIO
    assert corpo["usuario"]["email"] == EMAIL
    assert corpo["usuario"]["nome"] == "Grace Hopper"
    assert corpo["usuario"]["emailConfirmado"] is True
    assert corpo["usuario"]["ativo"] is True
    assert corpo["usuario"]["administrador"] is False


def test_o_aceite_marca_o_convite_como_aceito(cliente, sessao):
    convite, token = criar_convite(sessao)

    aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    assert convite.situacao == "aceito"
    assert convite.aceito_em is not None


def test_o_aceite_cria_a_participacao_do_papel_do_convite(cliente, sessao):
    convite, token = criar_convite(sessao, papel="chair")

    aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    usuario = ContaRepository.por_email(EMAIL)
    assert ParticipacaoRepository.papeis_no_evento(
        usuario.id, convite.evento_id
    ) == ["chair"]


def test_o_aceite_devolve_o_cookie_de_renovacao_httponly(cliente, sessao):
    _, token = criar_convite(sessao)

    resposta = aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    definido = resposta.headers.get("Set-Cookie", "")
    assert definido.startswith("renovacao=")
    assert "HttpOnly" in definido
    assert "Path=/api/auth" in definido


def test_o_token_de_acesso_do_aceite_abre_as_rotas_autenticadas(cliente, sessao):
    convite, token = criar_convite(sessao)

    corpo = aceitar(
        cliente, token, {"nome": "Grace Hopper", "senha": SENHA}
    ).get_json()

    participacoes = cliente.get(
        "/api/me/participacoes",
        headers={"Authorization": f"Bearer {corpo['tokenDeAcesso']}"},
    )
    assert participacoes.status_code == 200
    assert [entrada["eventoId"] for entrada in participacoes.get_json()] == [
        str(convite.evento_id)
    ]


def test_a_senha_informada_no_aceite_passa_a_valer_no_login(cliente, sessao):
    _, token = criar_convite(sessao)
    aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    entrada = cliente.post(LOGIN, json={"email": EMAIL, "senha": SENHA})

    assert entrada.status_code == 200
    assert entrada.get_json()["usuario"]["email"] == EMAIL


def test_aceite_sem_nome_e_senha_para_email_sem_conta_responde_422(cliente, sessao):
    _, token = criar_convite(sessao)

    resposta = aceitar(cliente, token)

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert set(corpo["campos"]) == {"nome", "senha"}
    assert ContaRepository.por_email(EMAIL) is None


# AC8 — e-mail com conta: so cria participacao, sem alterar nome nem senha.


def test_aceite_de_email_com_conta_nao_altera_nome_nem_senha(cliente, sessao):
    usuario = criar_conta(sessao, nome="Ada Lovelace")
    hash_anterior = usuario.senha_hash
    _, token = criar_convite(sessao)

    resposta = aceitar(
        cliente, token, {"nome": "Outro Nome", "senha": "outra-senha-forte-9"}
    )

    assert resposta.status_code == 200
    assert usuario.nome == "Ada Lovelace"
    assert usuario.senha_hash == hash_anterior
    assert resposta.get_json()["usuario"]["id"] == str(usuario.id)


def test_aceite_de_email_com_conta_nao_cria_uma_segunda_conta(cliente, sessao):
    usuario = criar_conta(sessao)
    convite, token = criar_convite(sessao)

    aceitar(cliente, token)

    contas = sessao.query(Usuario).filter_by(email=EMAIL).all()
    assert [conta.id for conta in contas] == [usuario.id]
    assert ParticipacaoRepository.papeis_no_evento(
        usuario.id, convite.evento_id
    ) == ["chair"]


def test_aceite_de_email_com_conta_abre_sessao_sem_nome_nem_senha(cliente, sessao):
    criar_conta(sessao)
    _, token = criar_convite(sessao)

    resposta = aceitar(cliente, token)

    assert resposta.status_code == 200
    assert resposta.get_json()["tokenDeAcesso"]
    assert "renovacao=" in resposta.headers.get("Set-Cookie", "")


# AC9 — aceite repetido: 409 `convite_ja_usado` com o contato no corpo.


def test_aceite_repetido_responde_409_convite_ja_usado_com_o_contato(
    cliente, sessao
):
    _, token = criar_convite(sessao)
    aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    resposta = aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "convite_ja_usado"
    assert corpo["mensagem"] == MENSAGEM_DE_CONVITE_JA_USADO
    assert corpo["contatoDaOrganizacao"] == CONTATO
    assert "campos" not in corpo


def test_aceite_de_token_inexistente_responde_404_convite_invalido(cliente, sessao):
    resposta = aceitar(cliente, "token-que-nunca-existiu", {"nome": "X", "senha": SENHA})

    assert resposta.status_code == 404
    assert resposta.get_json()["codigo"] == "convite_invalido"
    assert resposta.get_json()["contatoDaOrganizacao"] == "contato@sgs.local"


def test_aceite_de_convite_vencido_responde_410_convite_expirado(cliente, sessao):
    convite, token = criar_convite(sessao)
    convite.prazo = agora() - timedelta(seconds=1)
    sessao.flush()

    resposta = aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    assert resposta.status_code == 410
    assert resposta.get_json()["codigo"] == "convite_expirado"
    assert resposta.get_json()["contatoDaOrganizacao"] == CONTATO


# Edge Case — aceito por alguem logado com **outra** conta.


def test_o_aceite_vincula_ao_email_do_convite_e_nao_a_sessao_em_curso(
    cliente, sessao
):
    outra = criar_conta(sessao, email="outra@exemplo.test", nome="Outra Pessoa")
    entrada = cliente.post(
        LOGIN, json={"email": "outra@exemplo.test", "senha": SENHA}
    )
    convite, token = criar_convite(sessao)

    resposta = aceitar(
        cliente,
        token,
        {"nome": "Grace Hopper", "senha": SENHA},
        cabecalhos={
            "Authorization": f"Bearer {entrada.get_json()['tokenDeAcesso']}"
        },
    )

    assert resposta.status_code == 200
    assert resposta.get_json()["usuario"]["email"] == EMAIL
    convidada = ContaRepository.por_email(EMAIL)
    assert resposta.get_json()["usuario"]["id"] == str(convidada.id)
    assert ParticipacaoRepository.papeis_no_evento(
        convidada.id, convite.evento_id
    ) == ["chair"]
    assert ParticipacaoRepository.papeis_no_evento(outra.id, convite.evento_id) == []


# Transacao unica — falha ao criar a participacao nao deixa conta orfa.


def test_falha_ao_criar_a_participacao_nao_deixa_conta_orfa(
    cliente, sessao, monkeypatch
):
    convite, token = criar_convite(sessao)
    db.session.commit()

    def _explodir(*args, **kwargs):
        raise RuntimeError("falha ao gravar a participação")

    monkeypatch.setattr(ParticipacaoRepository, "criar", _explodir)

    resposta = aceitar(cliente, token, {"nome": "Grace Hopper", "senha": SENHA})

    assert resposta.status_code == 500
    # A conta chegou a ser criada dentro da requisicao; o rollback da transacao
    # unica e o que impede que ela sobreviva sem a participacao que a justifica.
    assert ContaRepository.por_email(EMAIL) is None
    assert convite.situacao == "pendente"
    assert convite.aceito_em is None
