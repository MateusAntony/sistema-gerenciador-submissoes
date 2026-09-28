"""B2 (A-6) — a fila de solicitações de evento é só para administrador."""
import pytest

from app.extensions import db
from app.models.evento import SolicitacaoEvento


@pytest.fixture
def solicitacao(fabrica):
    solicitante = fabrica.usuario('Solicitante')
    item = SolicitacaoEvento(
        solicitante_id=solicitante.id, titulo='Semana', ano=2026, identificador_pagina='semana-2026',
        tipo='outro', pais='Brasil', fuso='America/Bahia', data_inicio='2026-11-10',
        data_termino='2026-11-12', justificativa='Porque sim.',
    )
    db.session.add(item)
    db.session.commit()
    return item


def test_fila_sem_sessao_responde_401(fabrica, solicitacao):
    resposta = fabrica.cliente().get('/api/admin/solicitacoes-evento')
    assert resposta.status_code == 401
    assert 'titulo' not in resposta.get_data(as_text=True)


def test_fila_para_quem_nao_e_admin_responde_403(fabrica, solicitacao):
    resposta = fabrica.cliente(fabrica.usuario('Comum')).get('/api/admin/solicitacoes-evento')
    assert resposta.status_code == 403
    assert resposta.get_json()['codigo'] == 'sem_permissao'


def test_admin_ve_a_fila(fabrica, solicitacao):
    resposta = fabrica.cliente(fabrica.usuario('Admin', administrador=True)).get(
        '/api/admin/solicitacoes-evento?status=pendente'
    )
    assert resposta.status_code == 200
    assert [item['titulo'] for item in resposta.get_json()] == ['Semana']


@pytest.mark.parametrize('acao', ['aprovar', 'recusar'])
def test_decidir_tambem_exige_admin(fabrica, solicitacao, acao):
    url = f'/api/admin/solicitacoes-evento/{solicitacao.id}/{acao}'
    assert fabrica.cliente().post(url, json={'motivo': 'x'}).status_code == 401
    assert fabrica.cliente(fabrica.usuario('Comum')).post(url, json={'motivo': 'x'}).status_code == 403
    assert SolicitacaoEvento.query.get(solicitacao.id).situacao == 'pendente'
