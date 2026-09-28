"""B4 — código SUB-{id:04d}, único, mesmo com confirmações fora de ordem."""
from pathlib import Path

import psycopg2
import pytest

from app.extensions import db
from app.models.evento import Submissao
from tests.conftest import URL_BANCO_DE_TESTE

MIGRACAO = Path(__file__).resolve().parent.parent / 'migrations' / '13-submissoes-codigo-por-id.sql'


# Primeiro teste do módulo de propósito: o teste da migração cria o mesmo índice,
# então só antes dele a checagem prova que o init-script 13 o criou.
def test_indice_unico_de_codigo_existe(app):
    indices = db.session.execute(db.text(
        "SELECT indexdef FROM pg_indexes WHERE tablename = 'submissoes' AND indexname = 'uq_submissoes_codigo'"
    )).scalars().all()
    assert indices


def _rascunho(fabrica, autora, chamada):
    cliente = fabrica.cliente(autora)
    submissao_id = int(cliente.post(f'/api/chamadas/{chamada.id}/submissoes', json={}).get_json()['id'])
    cliente.patch(f'/api/submissoes/{submissao_id}', json={'respostas': {'titulo': 'T', 'resumo': 'R'}})
    fabrica.enviar_versao(cliente, submissao_id)
    return submissao_id


def _confirmar(fabrica, autora, submissao_id):
    resposta = fabrica.cliente(autora).post(f'/api/submissoes/{submissao_id}/confirmar')
    assert resposta.status_code == 200, resposta.get_json()
    return resposta.get_json()['codigo']


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chamada = fabrica.chamada(fabrica.evento(chair=fabrica.usuario('Chair')))
    return autora, chamada


def test_primeira_submissao_e_sub_0001(fabrica, cenario):
    autora, chamada = cenario
    submissao_id = _rascunho(fabrica, autora, chamada)
    assert _confirmar(fabrica, autora, submissao_id) == f'SUB-{submissao_id:04d}' == 'SUB-0001'


def test_confirmacoes_fora_de_ordem_nao_repetem_codigo(fabrica, cenario):
    autora, chamada = cenario
    primeira = _rascunho(fabrica, autora, chamada)
    segunda = _rascunho(fabrica, autora, chamada)

    assert _confirmar(fabrica, autora, segunda) == f'SUB-{segunda:04d}'
    assert _confirmar(fabrica, autora, primeira) == f'SUB-{primeira:04d}'


def _aplicar_migracao():
    conexao = psycopg2.connect(URL_BANCO_DE_TESTE)
    conexao.autocommit = True
    with conexao.cursor() as cursor:
        cursor.execute(MIGRACAO.read_text(encoding='utf-8'))
    conexao.close()


def test_migracao_normaliza_codigos_antigos_e_e_idempotente(fabrica, cenario):
    autora, chamada = cenario
    ids = [_rascunho(fabrica, autora, chamada) for _ in range(3)]
    for submissao_id in ids[:2]:
        _confirmar(fabrica, autora, submissao_id)
    # Códigos como o cálculo antigo gravava: deslocados de um (id 1 → SUB-0002, id 2 → SUB-0003).
    Submissao.query.get(ids[0]).codigo = 'TEMP'
    db.session.commit()
    Submissao.query.get(ids[1]).codigo = f'SUB-{ids[1] + 1:04d}'
    Submissao.query.get(ids[0]).codigo = f'SUB-{ids[0] + 1:04d}'
    db.session.commit()
    db.session.remove()

    _aplicar_migracao()
    _aplicar_migracao()

    codigos = {s.id: s.codigo for s in Submissao.query.all()}
    assert codigos == {ids[0]: f'SUB-{ids[0]:04d}', ids[1]: f'SUB-{ids[1]:04d}', ids[2]: None}
