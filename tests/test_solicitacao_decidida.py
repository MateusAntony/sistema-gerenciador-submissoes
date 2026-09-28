"""A8 — 409 solicitacao_ja_decidida e to_dict trazem decididoPorNome; a fila
admin traz solicitanteNome e solicitanteInstituicao."""
import pytest

from app.extensions import db
from app.models.evento import SolicitacaoEvento


@pytest.fixture
def cenario(fabrica):
    solicitante = fabrica.usuario('Sol Solicitante')
    admin = fabrica.usuario('Ana Admin', administrador=True)
    solicitacao = SolicitacaoEvento(
        solicitante_id=solicitante.id, titulo='Semana', ano=2026, identificador_pagina='semana-2026',
        tipo='outro', pais='Brasil', fuso='America/Bahia', data_inicio='2026-11-10',
        data_termino='2026-11-12', justificativa='J.',
    )
    db.session.add(solicitacao)
    db.session.commit()
    return {'solicitante': solicitante, 'admin': admin, 'id': solicitacao.id}


def _aprovar(fabrica, usuario, cenario):
    return fabrica.cliente(usuario).post(f"/api/admin/solicitacoes-evento/{cenario['id']}/aprovar")


def test_fila_admin_traz_nome_e_instituicao_do_solicitante(fabrica, cenario):
    [item] = fabrica.cliente(cenario['admin']).get('/api/admin/solicitacoes-evento').get_json()
    assert item['solicitanteNome'] == 'Sol Solicitante'
    assert item['solicitanteInstituicao'] == 'UEFS'
    assert item['decididoPorNome'] is None


def test_aprovada_traz_decidido_por_nome(fabrica, cenario):
    resposta = _aprovar(fabrica, cenario['admin'], cenario)
    assert resposta.get_json()['solicitacao']['decididoPorNome'] == 'Ana Admin'

    [item] = fabrica.cliente(cenario['admin']).get('/api/admin/solicitacoes-evento?status=aprovada').get_json()
    assert item['decididoPorNome'] == 'Ana Admin'


@pytest.mark.parametrize('segunda_acao', ['aprovar', 'recusar', 'editar'])
def test_409_ja_decidida_traz_decidido_por_nome(fabrica, cenario, segunda_acao):
    assert _aprovar(fabrica, cenario['admin'], cenario).status_code == 200
    outro_admin = fabrica.usuario('Beto Admin', administrador=True)

    if segunda_acao == 'editar':
        resposta = fabrica.cliente(cenario['solicitante']).patch(
            f"/api/solicitacoes-evento/{cenario['id']}", json={'titulo': 'X'})
    else:
        resposta = fabrica.cliente(outro_admin).post(
            f"/api/admin/solicitacoes-evento/{cenario['id']}/{segunda_acao}", json={'motivo': 'M'})

    assert resposta.status_code == 409
    corpo = resposta.get_json()
    assert corpo['codigo'] == 'solicitacao_ja_decidida'
    assert corpo['decididoPorNome'] == 'Ana Admin'
    assert corpo['decididoPorId'] == cenario['admin'].id


def test_minhas_solicitacoes_tambem_trazem_quem_decidiu(fabrica, cenario):
    _aprovar(fabrica, cenario['admin'], cenario)
    [item] = fabrica.cliente(cenario['solicitante']).get('/api/me/solicitacoes-evento').get_json()
    assert item['decididoPorNome'] == 'Ana Admin'
