"""Testes da unidade de trabalho — AD-019, risco R1, pre-requisito de API-13 AC4."""

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.core.unidade_de_trabalho import transacao
from app.extensions import db
from app.modules.contas.models import Usuario

EMAIL = "unidade.de.trabalho@exemplo.test"
OUTRO_EMAIL = "outra.escrita@exemplo.test"


def contar(sessao, *emails) -> int:
    return sessao.execute(
        select(func.count()).select_from(Usuario).where(Usuario.email.in_(emails))
    ).scalar()


def usuario(email: str) -> Usuario:
    return Usuario(nome="Pessoa", email=email, senha_hash="hash")


@pytest.fixture()
def commits(sessao):
    """Conta os commits que a sessao realmente executa no bloco."""
    ocorridos = []

    def registrar(_sessao):
        ocorridos.append(1)

    event.listen(db.session, "after_commit", registrar)
    yield ocorridos
    event.remove(db.session, "after_commit", registrar)


def test_transacao_grava_as_escritas_do_bloco_com_um_commit_so(sessao, commits):
    with transacao() as unidade:
        unidade.add(usuario(EMAIL))
        unidade.add(usuario(OUTRO_EMAIL))

    assert contar(sessao, EMAIL, OUTRO_EMAIL) == 2
    assert len(commits) == 1


def test_falha_na_segunda_escrita_nao_deixa_linha_nenhuma(sessao, commits):
    with pytest.raises(IntegrityError), transacao() as unidade:
        unidade.add(usuario(EMAIL))
        unidade.flush()
        unidade.add(usuario(EMAIL))
        unidade.flush()

    assert contar(sessao, EMAIL) == 0
    assert commits == []


def test_excecao_de_negocio_no_meio_do_bloco_desfaz_a_escrita_anterior(sessao, commits):
    class FalhaDeNegocio(Exception):
        pass

    with pytest.raises(FalhaDeNegocio), transacao() as unidade:
        unidade.add(usuario(EMAIL))
        unidade.flush()
        raise FalhaDeNegocio

    assert contar(sessao, EMAIL) == 0
    assert commits == []


def test_nenhum_modulo_da_aplicacao_chama_commit_fora_da_unidade_de_trabalho(
    raiz_do_projeto,
):
    infratores = [
        f"{arquivo.relative_to(raiz_do_projeto)}:{numero}"
        for arquivo in sorted((raiz_do_projeto / "app").rglob("*.py"))
        if arquivo.name != "unidade_de_trabalho.py"
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        )
        if ".commit()" in linha
    ]

    assert infratores == []
