"""Testes de ponta a ponta do autocadastro — API-05 AC1..AC6 (T11)."""

import uuid

import pytest
from sqlalchemy import func, select

from app.extensions import bcrypt
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.emails.models import EmailEnviado

ROTA = "/api/usuarios"
EMAIL = "autocadastro@exemplo.test"
SENHA = "senha-bem-forte-1"

CADASTRO = {
    "nome": "Ada Lovelace",
    "email": EMAIL,
    "senha": SENHA,
    "instituicao": "UFPI",
    "pais": "Brasil",
}


def cadastro(**alteracoes) -> dict:
    return {**CADASTRO, **alteracoes}


def sem(campo: str) -> dict:
    return {chave: valor for chave, valor in CADASTRO.items() if chave != campo}


def usuario_gravado(sessao, email=EMAIL) -> Usuario | None:
    return sessao.scalars(select(Usuario).where(Usuario.email == email)).first()


def contar_usuarios(sessao, email=EMAIL) -> int:
    return sessao.execute(
        select(func.count()).select_from(Usuario).where(Usuario.email == email)
    ).scalar()


def emails_para(sessao, destinatario=EMAIL) -> list[EmailEnviado]:
    return list(
        sessao.scalars(
            select(EmailEnviado).where(EmailEnviado.destinatario == destinatario)
        )
    )


# AC1 e AC6 — 201 com exatamente `id` e `email`.


def test_cadastro_valido_responde_201_com_exatamente_id_e_email(cliente):
    resposta = cliente.post(ROTA, json=CADASTRO)

    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert set(corpo) == {"id", "email"}
    assert corpo["email"] == EMAIL
    assert isinstance(corpo["id"], str)
    assert uuid.UUID(corpo["id"])


def test_a_resposta_de_criacao_nao_carrega_o_usuario_completo(cliente):
    corpo = cliente.post(ROTA, json=CADASTRO).get_json()

    for ausente in (
        "nome",
        "senha",
        "senhaHash",
        "instituicao",
        "pais",
        "emailConfirmado",
        "ativo",
        "administrador",
        "usuario",
    ):
        assert ausente not in corpo


# AC1 e AC5 — a conta nasce nao confirmada, ativa, com a senha so como hash.


def test_a_conta_nasce_nao_confirmada_e_ativa(cliente, sessao):
    cliente.post(ROTA, json=CADASTRO)

    gravado = usuario_gravado(sessao)
    assert gravado is not None
    assert gravado.email_confirmado is False
    assert gravado.ativo is True


def test_a_senha_e_gravada_apenas_como_hash_bcrypt(cliente, sessao):
    cliente.post(ROTA, json=CADASTRO)

    gravado = usuario_gravado(sessao)
    assert gravado.senha_hash != SENHA
    assert gravado.senha_hash.startswith("$2b$")
    assert bcrypt.check_password_hash(gravado.senha_hash, SENHA) is True
    valores = [
        str(getattr(gravado, coluna.name))
        for coluna in Usuario.__table__.columns
    ]
    assert [valor for valor in valores if SENHA in valor] == []


# AC1 — o e-mail de confirmacao e disparado.


def test_o_cadastro_dispara_o_email_de_confirmacao(cliente, sessao):
    cliente.post(ROTA, json=CADASTRO)

    enviados = emails_para(sessao)
    assert len(enviados) == 1
    assert enviados[0].situacao == "enviado"


# AC2 — e-mail repetido responde 409 `email_existente`.


def test_email_duplicado_responde_409_email_existente(cliente, sessao):
    cliente.post(ROTA, json=CADASTRO)

    resposta = cliente.post(ROTA, json=cadastro(nome="Outra Pessoa"))

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo["codigo"] == "email_existente"
    assert corpo["correlacao"]
    assert contar_usuarios(sessao) == 1


def test_colisao_de_email_em_corrida_responde_409_e_nunca_500(
    cliente, sessao, monkeypatch
):
    # Edge Case da spec: os dois cadastros passam pela checagem previa ao mesmo
    # tempo e o segundo so descobre a colisao na constraint unica do banco.
    cliente.post(ROTA, json=CADASTRO)
    monkeypatch.setattr(ContaRepository, "por_email", staticmethod(lambda email: None))

    resposta = cliente.post(ROTA, json=cadastro(nome="Outra Pessoa"))

    assert resposta.status_code == 409
    assert resposta.get_json()["codigo"] == "email_existente"
    assert contar_usuarios(sessao) == 1


# AC3 — instituicao ausente ou vazia responde 422 com `campos.instituicao`.


@pytest.mark.parametrize(
    "corpo_enviado", [sem("instituicao"), cadastro(instituicao="")]
)
def test_instituicao_ausente_ou_vazia_responde_422_com_campos_instituicao(
    cliente, corpo_enviado
):
    resposta = cliente.post(ROTA, json=corpo_enviado)

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "instituicao" in corpo["campos"]


# AC4 — senha com menos de 8 caracteres responde 422 com `campos.senha`.


def test_senha_curta_responde_422_com_campos_senha(cliente, sessao):
    resposta = cliente.post(ROTA, json=cadastro(senha="curta12"))

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["codigo"] == "dados_invalidos"
    assert "senha" in corpo["campos"]
    assert contar_usuarios(sessao) == 0


def test_senha_com_oito_caracteres_e_aceita(cliente):
    resposta = cliente.post(ROTA, json=cadastro(senha="12345678"))

    assert resposta.status_code == 201
