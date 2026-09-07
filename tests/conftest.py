"""Infraestrutura da suite: aplicacao, banco `sgs_test` migrado e transacao por teste.

A suite roda contra Postgres real (AD-012). O banco de teste e criado e migrado uma vez
por sessao; cada teste roda dentro de uma transacao desfeita no fim, de modo que nenhum
teste enxergue o que outro escreveu (API-22 AC1, AC2).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
DIRETORIO_DE_MIGRATIONS = RAIZ / "migrations"

load_dotenv(RAIZ / ".env")

URL_DE_DESENVOLVIMENTO = os.environ["DATABASE_URL"]

# A suite fala com o banco de teste. A troca acontece antes de a aplicacao ser importada,
# para valer qualquer que seja o momento em que a configuracao leia a variavel.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_TESTE"]

import pytest
from flask_migrate import upgrade
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db
from tests.rotas_de_guarda import guarda_bp


def _criar_banco_se_nao_existir(url: str) -> None:
    alvo = make_url(url)
    servidor = create_engine(alvo.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with servidor.connect() as conexao:
            existe = conexao.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :nome"),
                {"nome": alvo.database},
            ).scalar()
            if not existe:
                conexao.execute(text(f'CREATE DATABASE "{alvo.database}"'))
    finally:
        servidor.dispose()


@pytest.fixture(scope="session")
def raiz_do_projeto() -> Path:
    """Raiz do repositorio, para testes que olham arquivos do projeto."""
    return RAIZ


@pytest.fixture(scope="session")
def diretorio_de_migrations() -> Path:
    return DIRETORIO_DE_MIGRATIONS


@pytest.fixture(scope="session")
def banco_de_desenvolvimento() -> str:
    """Nome do banco de desenvolvimento, para provar que a suite nao fala com ele."""
    return make_url(URL_DE_DESENVOLVIMENTO).database


@pytest.fixture(scope="session")
def aplicacao():
    """Aplicacao apontada para `sgs_test`, com todas as migrations aplicadas.

    As rotas sinteticas de `tests/rotas_de_guarda` entram aqui porque um
    blueprint so pode ser registrado antes da primeira requisicao; elas existem
    para exercitar `@exige_acao` pela borda HTTP enquanto as rotas reais de
    gestao nao chegam (T23).
    """
    _criar_banco_se_nao_existir(os.environ["DATABASE_URL"])
    app = create_app()
    app.register_blueprint(guarda_bp)
    with app.app_context():
        upgrade(directory=str(DIRETORIO_DE_MIGRATIONS))
    return app


@pytest.fixture()
def sessao(aplicacao):
    """Uma transacao por teste, desfeita no fim.

    O engine padrao da aplicacao e trocado pela conexao da transacao, de modo que tudo o
    que o teste faz — inclusive dentro de uma requisicao HTTP — fale pela mesma conexao.
    `create_savepoint` faz cada commit da aplicacao virar liberacao de savepoint, nunca
    commit da transacao externa.
    """
    with aplicacao.app_context():
        motor = db.engines[None]
        conexao = motor.connect()
        transacao = conexao.begin()
        db.engines[None] = conexao
        db.session.remove()
        db.session.configure(join_transaction_mode="create_savepoint")
        try:
            yield db.session
        finally:
            db.session.remove()
            db.session.configure(join_transaction_mode="conditional_savepoint")
            db.engines[None] = motor
            transacao.rollback()
            conexao.close()


@pytest.fixture()
def cliente(aplicacao, sessao):
    """Cliente HTTP do Flask dentro da transacao do teste (API-22 AC3)."""
    return aplicacao.test_client()
