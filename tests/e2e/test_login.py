"""Testes de ponta a ponta do login — API-03 AC1..AC6 (T16)."""

import hashlib

import pytest
from flask_jwt_extended import decode_token
from sqlalchemy import select

from app.extensions import bcrypt
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.sessao.models import Sessao

ROTA = "/api/auth/login"
EMAIL = "login@exemplo.test"
SENHA = "senha-bem-forte-1"
EMAIL_SEM_CONTA = "nao.existe.nenhuma.conta@exemplo.test"

CAMPOS_DO_USUARIO = {
    "id",
    "nome",
    "email",
    "emailConfirmado",
    "administrador",
    "ativo",
}


def criar_conta(
    email=EMAIL, senha=SENHA, ativo=True, email_confirmado=True
) -> Usuario:
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=email,
        senha_hash=bcrypt.generate_password_hash(senha).decode("utf-8"),
    )
    usuario.ativo = ativo
    usuario.email_confirmado = email_confirmado
    return usuario


def entrar(cliente, email=EMAIL, senha=SENHA):
    return cliente.post(ROTA, json={"email": email, "senha": senha})


def cabecalhos_de_cookie(resposta) -> list[str]:
    return resposta.headers.getlist("Set-Cookie")


def cookie_de_renovacao(resposta) -> str | None:
    for cabecalho in cabecalhos_de_cookie(resposta):
        if cabecalho.startswith("renovacao="):
            return cabecalho
    return None


def corpo_comparavel(resposta) -> tuple[int, dict]:
    """Status e corpo sem a correlacao, que muda a cada requisicao por desenho."""
    corpo = {
        chave: valor
        for chave, valor in resposta.get_json().items()
        if chave != "correlacao"
    }
    return resposta.status_code, corpo


# AC1 — 200 com `tokenDeAcesso` e `usuario` com os seis campos do contrato.


def test_login_valido_responde_200_com_token_de_acesso_e_usuario(cliente, sessao):
    criar_conta()

    resposta = entrar(cliente)

    assert resposta.status_code == 200
    corpo = resposta.get_json()
    assert set(corpo) == {"tokenDeAcesso", "usuario"}
    assert set(corpo["usuario"]) == CAMPOS_DO_USUARIO
    assert corpo["usuario"]["email"] == EMAIL
    assert corpo["usuario"]["nome"] == "Ada Lovelace"
    assert corpo["usuario"]["emailConfirmado"] is True
    assert corpo["usuario"]["ativo"] is True
    assert corpo["usuario"]["administrador"] is False


def test_a_resposta_do_login_nunca_carrega_a_senha_nem_o_hash(cliente, sessao):
    usuario = criar_conta()

    resposta = entrar(cliente)

    bruto = resposta.get_data(as_text=True)
    assert SENHA not in bruto
    assert usuario.senha_hash not in bruto
    for ausente in ("senha", "senhaHash", "senha_hash"):
        assert ausente not in resposta.get_json()["usuario"]


def test_o_token_de_acesso_devolvido_identifica_o_usuario(cliente, sessao):
    usuario = criar_conta()

    corpo = entrar(cliente).get_json()

    assert decode_token(corpo["tokenDeAcesso"])["sub"] == str(usuario.id)


# AC2 — 401 `credenciais_invalidas` indistinguivel entre e-mail inexistente e
# senha errada.


@pytest.mark.parametrize(
    ("email", "senha"),
    [(EMAIL, "senha-errada-1"), (EMAIL_SEM_CONTA, SENHA)],
)
def test_credenciais_invalidas_respondem_401_credenciais_invalidas(
    cliente, sessao, email, senha
):
    criar_conta()

    resposta = entrar(cliente, email=email, senha=senha)

    assert resposta.status_code == 401
    assert resposta.get_json()["codigo"] == "credenciais_invalidas"


def test_email_inexistente_e_senha_errada_produzem_a_mesma_resposta(cliente, sessao):
    criar_conta()

    sem_conta = entrar(cliente, email=EMAIL_SEM_CONTA, senha=SENHA)
    senha_errada = entrar(cliente, email=EMAIL, senha="senha-errada-1")

    # Igualdade de status **e** de corpo: um `mensagem` diferente ja diria qual
    # dos dois falhou.
    assert corpo_comparavel(sem_conta) == corpo_comparavel(senha_errada)


def test_o_401_de_email_inexistente_tambem_paga_a_verificacao_bcrypt(
    cliente, sessao, monkeypatch
):
    # A indistinguibilidade de AC2 tambem e de tempo: sem esta verificacao, a
    # resposta mais rapida entregaria quais e-mails tem conta.
    verificacoes = []
    original = bcrypt.check_password_hash
    monkeypatch.setattr(
        bcrypt,
        "check_password_hash",
        lambda hash_guardado, senha: verificacoes.append(hash_guardado)
        or original(hash_guardado, senha),
    )

    entrar(cliente, email=EMAIL_SEM_CONTA, senha=SENHA)

    assert len(verificacoes) == 1
    assert verificacoes[0].startswith("$2b$12$")


def test_o_login_que_falha_nao_emite_cookie_de_renovacao(cliente, sessao):
    criar_conta()

    resposta = entrar(cliente, senha="senha-errada-1")

    assert cookie_de_renovacao(resposta) is None
    assert sessao.scalars(select(Sessao)).first() is None


# AC3 — conta inativa responde 403 `conta_desativada`.


def test_conta_desativada_responde_403_conta_desativada(cliente, sessao):
    criar_conta(ativo=False)

    resposta = entrar(cliente)

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "conta_desativada"
    assert cookie_de_renovacao(resposta) is None


# AC4 — conta ativa com e-mail nao confirmado responde 403 `email_nao_confirmado`.


def test_email_nao_confirmado_responde_403_email_nao_confirmado(cliente, sessao):
    criar_conta(email_confirmado=False)

    resposta = entrar(cliente)

    assert resposta.status_code == 403
    assert resposta.get_json()["codigo"] == "email_nao_confirmado"
    assert cookie_de_renovacao(resposta) is None


# AC5 — cookie de renovacao httpOnly, SameSite=Lax, Path=/api/auth, Secure
# conforme o ambiente.


def test_o_cookie_de_renovacao_e_httponly_samesite_lax_e_restrito_a_api_auth(
    cliente, sessao
):
    criar_conta()

    cookie = cookie_de_renovacao(entrar(cliente))

    assert cookie is not None
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/api/auth" in cookie


def test_o_cookie_de_renovacao_nao_e_secure_fora_de_producao(cliente, sessao):
    criar_conta()

    assert "Secure" not in cookie_de_renovacao(entrar(cliente))


def test_o_cookie_de_renovacao_e_secure_quando_o_ambiente_e_de_producao(
    cliente, aplicacao, sessao, monkeypatch
):
    criar_conta()
    monkeypatch.setitem(aplicacao.config, "COOKIE_SEGURO", True)

    assert "Secure" in cookie_de_renovacao(entrar(cliente))


def test_o_cookie_carrega_o_token_de_renovacao_gravado_como_sha256(cliente, sessao):
    usuario = criar_conta()

    resposta = entrar(cliente)

    valor = cookie_de_renovacao(resposta).split(";")[0].removeprefix("renovacao=")
    gravada = sessao.scalars(select(Sessao)).one()
    assert gravada.usuario_id == usuario.id
    assert gravada.token_hash == hashlib.sha256(valor.encode("utf-8")).hexdigest()


# AC6 — a senha e conferida por bcrypt sobre o hash, nunca em texto puro.


def test_a_senha_e_conferida_por_bcrypt_e_nunca_em_texto_puro(cliente, sessao):
    usuario = criar_conta()

    # O hash guardado nao serve como senha: quem compara texto com texto deixaria
    # esta chamada passar.
    assert entrar(cliente, senha=usuario.senha_hash).status_code == 401
    assert entrar(cliente, senha=SENHA).status_code == 200
