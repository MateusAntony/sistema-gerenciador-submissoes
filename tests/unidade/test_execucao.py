"""Testes do caminho de execucao do contêiner — API-21 AC1; risco R5."""

from app import create_app
from app.config import Config

AMBIENTE_DE_PRODUCAO = {
    "APP_ENV": "production",
    "SECRET_KEY": "chave-de-teste",
    "DATABASE_URL": "postgresql://sgs:sgs@db:5432/sgs",
    "URL_DO_FRONT": "https://sgs.exemplo.br",
}


def test_aplicacao_de_producao_nao_sobe_com_debugger():
    aplicacao_de_producao = create_app(Config(AMBIENTE_DE_PRODUCAO))

    assert aplicacao_de_producao.debug is False


def test_aplicacao_de_desenvolvimento_sobe_com_debugger():
    ambiente = {
        **AMBIENTE_DE_PRODUCAO,
        "APP_ENV": "development",
        "URL_DO_FRONT": "http://localhost:5173",
    }

    assert create_app(Config(ambiente)).debug is True


def test_o_comando_do_container_e_um_servidor_wsgi_de_producao(raiz_do_projeto):
    dockerfile = (raiz_do_projeto / "Dockerfile").read_text(encoding="utf-8")

    assert 'CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "run:app"]' in dockerfile
    assert "python run.py" not in dockerfile


def test_o_debugger_do_run_esta_preso_ao_ambiente_de_desenvolvimento(raiz_do_projeto):
    run = (raiz_do_projeto / "run.py").read_text(encoding="utf-8")

    assert "debug=True" not in run
    assert "debug=app.config['APP_ENV'] == 'development'" in run


def test_o_entrypoint_espera_o_banco_e_migra_antes_de_servir(raiz_do_projeto):
    entrypoint = (raiz_do_projeto / "entrypoint.sh").read_text(encoding="utf-8")
    dockerfile = (raiz_do_projeto / "Dockerfile").read_text(encoding="utf-8")

    assert "psycopg2.connect(url)" in entrypoint
    assert entrypoint.index("psycopg2.connect(url)") < entrypoint.index("db upgrade")
    assert entrypoint.index("db upgrade") < entrypoint.index('exec "$@"')
    assert 'ENTRYPOINT ["/app/entrypoint.sh"]' in dockerfile
