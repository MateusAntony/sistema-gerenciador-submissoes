"""Infraestrutura da suíte pytest.

O banco de teste (padrão `sgs_api_test`) é recriado do zero a cada sessão a
partir de `init-scripts/*.sql`, na mesma ordem em que o contêiner do Postgres
os aplica. Assim a suíte exercita o schema real, não um `create_all()` dos
models. Entre um teste e outro todas as tabelas são truncadas.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

URL_BANCO_DE_TESTE = os.environ.get(
    'DATABASE_URL_API_TESTE', 'postgresql://sgs:sgs_dev@localhost:5432/sgs_api_test'
)
NOME_DO_BANCO = urlparse(URL_BANCO_DE_TESTE).path.lstrip('/')
if not NOME_DO_BANCO.endswith('_api_test'):
    raise RuntimeError(
        f'Recuso recriar o banco {NOME_DO_BANCO!r}: o banco de teste precisa terminar em "_api_test".'
    )

# Config exige estas variáveis na importação; a suíte nunca usa o banco do .env.
os.environ['DATABASE_URL'] = URL_BANCO_DE_TESTE
os.environ.setdefault('SECRET_KEY', 'chave-dos-testes')
os.environ.pop('BREVO_API_KEY', None)

from app import create_app  # noqa: E402
from app.config import Config  # noqa: E402
from app.extensions import db  # noqa: E402


def _recriar_banco():
    alvo = urlparse(URL_BANCO_DE_TESTE)
    conexao = psycopg2.connect(
        host=alvo.hostname, port=alvo.port or 5432, user=alvo.username,
        password=alvo.password, dbname='postgres',
    )
    conexao.autocommit = True
    with conexao.cursor() as cursor:
        cursor.execute(f'DROP DATABASE IF EXISTS "{NOME_DO_BANCO}" WITH (FORCE)')
        cursor.execute(f'CREATE DATABASE "{NOME_DO_BANCO}"')
    conexao.close()

    conexao = psycopg2.connect(URL_BANCO_DE_TESTE)
    conexao.autocommit = True
    with conexao.cursor() as cursor:
        for script in sorted((RAIZ / 'init-scripts').glob('*.sql')):
            cursor.execute(script.read_text(encoding='utf-8'))
    conexao.close()


@pytest.fixture(scope='session')
def app(tmp_path_factory):
    _recriar_banco()

    class ConfigDeTeste(Config):
        TESTING = True
        BCRYPT_LOG_ROUNDS = 4  # o padrão (12) domina o tempo da suíte
        SQLALCHEMY_DATABASE_URI = URL_BANCO_DE_TESTE
        PASTA_UPLOADS = str(tmp_path_factory.mktemp('uploads'))

    aplicacao = create_app(ConfigDeTeste)
    with aplicacao.app_context():
        yield aplicacao
        db.session.remove()
        db.engine.dispose()


@pytest.fixture(autouse=True)
def banco_limpo(app):
    yield
    db.session.remove()
    tabelas = db.session.execute(db.text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    )).scalars().all()
    if tabelas:
        lista = ', '.join(f'"{nome}"' for nome in tabelas)
        db.session.execute(db.text(f'TRUNCATE {lista} RESTART IDENTITY CASCADE'))
        db.session.commit()


@pytest.fixture
def fabrica(app):
    from tests.fabrica import Fabrica
    return Fabrica(app)
