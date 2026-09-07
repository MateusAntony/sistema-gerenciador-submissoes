"""Testes do modelo e do repositorio de contas — AD-016, riscos R1 e R3 (T9)."""

import uuid

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository

COLUNAS_DO_SCHEMA = {
    "id",
    "nome",
    "email",
    "email_confirmado",
    "senha_hash",
    "instituicao",
    "pais",
    "identificador_orcid",
    "administrador",
    "ativo",
    "criado_em",
    "atualizado_em",
}

EMAIL = "repositorio.de.contas@exemplo.test"


def test_criacao_grava_o_usuario_com_chave_primaria_uuid(sessao):
    usuario = ContaRepository.criar(
        nome="Ada Lovelace",
        email=EMAIL,
        senha_hash="hash-bcrypt",
        instituicao="UFPI",
        pais="Brasil",
    )

    assert isinstance(usuario.id, uuid.UUID)
    assert usuario.nome == "Ada Lovelace"
    assert usuario.instituicao == "UFPI"
    assert usuario.pais == "Brasil"


def test_busca_por_email_devolve_o_usuario_gravado(sessao):
    criado = ContaRepository.criar(nome="Ada", email=EMAIL, senha_hash="hash")

    encontrado = ContaRepository.por_email(EMAIL)

    assert encontrado is not None
    assert encontrado.id == criado.id
    assert encontrado.email == EMAIL


def test_busca_por_email_inexistente_devolve_none(sessao):
    assert ContaRepository.por_email("ninguem@exemplo.test") is None


def test_busca_por_id_devolve_o_usuario_gravado(sessao):
    criado = ContaRepository.criar(nome="Ada", email=EMAIL, senha_hash="hash")

    encontrado = ContaRepository.por_id(criado.id)

    assert encontrado is not None
    assert encontrado.email == EMAIL


def test_busca_por_id_inexistente_devolve_none(sessao):
    assert ContaRepository.por_id(uuid.uuid4()) is None


def test_o_modelo_de_usuario_vive_no_modulo_de_contas():
    assert Usuario.__module__ == "app.modules.contas.models"
    assert Usuario.__tablename__ == "usuarios"


def test_o_modelo_de_usuario_preserva_as_colunas_do_schema():
    assert {coluna.name for coluna in Usuario.__table__.columns} == COLUNAS_DO_SCHEMA


def test_o_modelo_de_usuario_nao_serializa_a_si_mesmo():
    # A serializacao passa a ser dos schemas Pydantic (AD-006); `to_dict` sai.
    assert not hasattr(Usuario, "to_dict")


def test_nenhum_modulo_da_aplicacao_usa_a_consulta_do_sqlalchemy_1(raiz_do_projeto):
    # Risco R3: `Modelo.query.get()` esta depreciada no SQLAlchemy 2.
    infratores = [
        f"{arquivo.relative_to(raiz_do_projeto)}:{numero}"
        for arquivo in sorted((raiz_do_projeto / "app").rglob("*.py"))
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        )
        if ".query.get(" in linha or ".query.filter" in linha
    ]

    assert infratores == []


def test_os_pacotes_antigos_por_camada_nao_existem_mais(raiz_do_projeto):
    antigos = ["models", "repositories", "services", "controllers"]

    restantes = [
        nome for nome in antigos if (raiz_do_projeto / "app" / nome).exists()
    ]

    assert restantes == []
