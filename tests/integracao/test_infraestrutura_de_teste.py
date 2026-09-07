"""Testes da rede de seguranca da suite — API-22 AC1, AC2, AC4."""

import subprocess
import sys

import pytest
from sqlalchemy import inspect, text

from app.extensions import db

TABELA_DE_ISOLAMENTO = "isolamento_da_suite"
EMAIL_REPETIDO = "mesmo.email@exemplo.test"


@pytest.fixture(scope="module")
def tabela_de_isolamento(aplicacao):
    """Tabela criada fora da transacao do teste, para os dois testes de isolamento."""
    with aplicacao.app_context(), db.engine.begin() as conexao:
        conexao.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {TABELA_DE_ISOLAMENTO} "
                "(email VARCHAR(255) PRIMARY KEY)"
            )
        )
    yield TABELA_DE_ISOLAMENTO
    with aplicacao.app_context(), db.engine.begin() as conexao:
        conexao.execute(text(f"DROP TABLE {TABELA_DE_ISOLAMENTO}"))


def test_consulta_de_fumaca_responde_pelo_banco(sessao):
    assert sessao.execute(text("SELECT 1")).scalar() == 1


def test_a_suite_usa_um_banco_separado_do_de_desenvolvimento(sessao, banco_de_desenvolvimento):
    banco_da_suite = sessao.execute(text("SELECT current_database()")).scalar()

    assert banco_da_suite == "sgs_test"
    assert banco_da_suite != banco_de_desenvolvimento


def test_a_fixture_de_sessao_aplicou_as_migrations(aplicacao, sessao):
    with aplicacao.app_context():
        tabelas = inspect(db.engines[None]).get_table_names()

    assert "alembic_version" in tabelas


def test_escreve_o_email_repetido_e_enxerga_so_o_proprio(sessao, tabela_de_isolamento):
    sessao.execute(
        text(f"INSERT INTO {tabela_de_isolamento} (email) VALUES (:email)"),
        {"email": EMAIL_REPETIDO},
    )
    total = sessao.execute(
        text(f"SELECT count(*) FROM {tabela_de_isolamento} WHERE email = :email"),
        {"email": EMAIL_REPETIDO},
    ).scalar()

    assert total == 1


def test_escreve_o_mesmo_email_de_novo_e_enxerga_so_o_proprio(sessao, tabela_de_isolamento):
    sessao.execute(
        text(f"INSERT INTO {tabela_de_isolamento} (email) VALUES (:email)"),
        {"email": EMAIL_REPETIDO},
    )
    total = sessao.execute(
        text(f"SELECT count(*) FROM {tabela_de_isolamento} WHERE email = :email"),
        {"email": EMAIL_REPETIDO},
    ).scalar()

    assert total == 1


def test_teste_que_falha_faz_o_comando_sair_com_codigo_diferente_de_zero(tmp_path):
    arquivo_que_passa = tmp_path / "test_passa.py"
    arquivo_que_passa.write_text("def test_passa():\n    assert True\n", encoding="utf-8")
    arquivo_que_falha = tmp_path / "test_falha.py"
    arquivo_que_falha.write_text("def test_falha():\n    assert 1 == 2\n", encoding="utf-8")

    def rodar(arquivo):
        return subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(arquivo)],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(tmp_path),
        ).returncode

    assert rodar(arquivo_que_passa) == 0
    assert rodar(arquivo_que_falha) != 0
