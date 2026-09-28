"""B5 — notificações: rebuttal aberto (autor) e etapa atribuída (responsável)."""
import pytest

from app.models.execucao_fase import ExecucaoFase
from app.models.notificacao import Notificacao

FASE = {'nome': 'Triagem', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': False, 'permiteDevolucao': False, 'ativo': True}


def _notificacoes(usuario, tipo):
    return Notificacao.query.filter_by(destinatario_id=usuario.id, tipo=tipo).all()


# --- rebuttal aberto ---

@pytest.mark.parametrize('maximo, notifica', [(2, True), (1, False)])
def test_autor_e_notificado_quando_o_rebuttal_abre(fabrica, maximo, notifica):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=maximo)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento), titulo='Meu trabalho')
    rodada_id = fabrica.rodada_atual(submissao_id).id

    fabrica.cliente(chair).post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})

    notificacoes = _notificacoes(autora, 'rebuttal_aberto')
    if not notifica:
        assert notificacoes == []  # última rodada possível: não há rebuttal (A12)
        return
    [notificacao] = notificacoes
    assert (notificacao.objeto_tipo, notificacao.objeto_id) == ('submissao', str(submissao_id))
    assert 'Meu trabalho' in notificacao.assunto
    [item] = fabrica.cliente(autora).get('/api/me/notificacoes').get_json()['itens']
    assert item['tipo'] == 'rebuttal_aberto'
    assert item['objeto']['eventoIdentificadorPagina'] == evento.identificador_pagina


# --- etapa atribuída ---

@pytest.fixture
def evento_com_fase(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    return {'chair': chair, 'evento': evento, 'chamada': fabrica.chamada(evento)}


def _criar_fase(fabrica, contexto, responsavel=None):
    corpo = {**FASE, 'responsavelPadraoId': responsavel.id if responsavel else None}
    resposta = fabrica.cliente(contexto['chair']).post(f"/api/eventos/{contexto['evento'].id}/fases", json=corpo)
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()['id']


def _conferir(notificacao, execucao):
    assert (notificacao.objeto_tipo, notificacao.objeto_id) == ('execucao_fase', str(execucao.id))
    assert notificacao.submissao_id == execucao.submissao_id


def test_responsavel_padrao_e_notificado_ao_confirmar_submissao(fabrica, evento_com_fase):
    rita = fabrica.usuario('Rita')
    fase_id = _criar_fase(fabrica, evento_com_fase, responsavel=rita)

    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), evento_com_fase['chamada'])

    [notificacao] = _notificacoes(rita, 'etapa_atribuida')
    _conferir(notificacao, ExecucaoFase.query.filter_by(fase_id=fase_id, submissao_id=submissao_id).one())
    [item] = fabrica.cliente(rita).get('/api/me/notificacoes').get_json()['itens']
    assert item['objeto']['tipo'] == 'execucao_fase' and item['objeto']['submissaoId'] == str(submissao_id)


def test_fase_sem_responsavel_nao_notifica_ninguem(fabrica, evento_com_fase):
    _criar_fase(fabrica, evento_com_fase)
    fabrica.submissao_confirmada(fabrica.usuario('Autora'), evento_com_fase['chamada'])
    assert Notificacao.query.filter_by(tipo='etapa_atribuida').count() == 0


def test_responsavel_padrao_preenchendo_execucoes_notifica_uma_vez_por_execucao(fabrica, evento_com_fase):
    fase_id = _criar_fase(fabrica, evento_com_fase)
    for _ in range(2):
        fabrica.submissao_confirmada(fabrica.usuario('Autora'), evento_com_fase['chamada'])
    rita = fabrica.usuario('Rita')

    fabrica.cliente(evento_com_fase['chair']).patch(f'/api/fases/{fase_id}', json={'responsavelPadraoId': rita.id})

    notificacoes = _notificacoes(rita, 'etapa_atribuida')
    execucoes = ExecucaoFase.query.filter_by(fase_id=fase_id).all()
    assert sorted(n.objeto_id for n in notificacoes) == sorted(str(e.id) for e in execucoes)


def test_trocar_responsavel_notifica_o_novo_e_nao_repete(fabrica, evento_com_fase):
    fase_id = _criar_fase(fabrica, evento_com_fase)
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), evento_com_fase['chamada'])
    execucao = ExecucaoFase.query.filter_by(fase_id=fase_id, submissao_id=submissao_id).one()
    novo = fabrica.usuario('Novo')
    cliente = fabrica.cliente(evento_com_fase['chair'])

    assert cliente.patch(f'/api/execucoes-fase/{execucao.id}', json={'responsavelId': novo.id}).status_code == 200
    assert cliente.patch(f'/api/execucoes-fase/{execucao.id}', json={'responsavelId': novo.id}).status_code == 200

    [notificacao] = _notificacoes(novo, 'etapa_atribuida')
    _conferir(notificacao, execucao)


# --- solicitação de evento aprovada/recusada ---

@pytest.fixture
def solicitacao(fabrica):
    from app.extensions import db
    from app.models.evento import SolicitacaoEvento
    solicitante = fabrica.usuario('Sol')
    item = SolicitacaoEvento(
        solicitante_id=solicitante.id, titulo='Semana de Exatas', ano=2026, identificador_pagina='semana-2026',
        tipo='outro', pais='Brasil', fuso='America/Bahia', data_inicio='2026-11-10',
        data_termino='2026-11-12', justificativa='J.',
    )
    db.session.add(item)
    db.session.commit()
    return {'solicitante': solicitante, 'id': item.id, 'admin': fabrica.usuario('Admin', administrador=True)}


def _objeto_na_central(fabrica, usuario):
    [item] = fabrica.cliente(usuario).get('/api/me/notificacoes').get_json()['itens']
    return item


def test_solicitante_e_notificado_da_aprovacao(fabrica, solicitacao):
    resposta = fabrica.cliente(solicitacao['admin']).post(
        f"/api/admin/solicitacoes-evento/{solicitacao['id']}/aprovar")
    evento_id = resposta.get_json()['evento']['id']

    [notificacao] = _notificacoes(solicitacao['solicitante'], 'solicitacao_aprovada')
    assert notificacao.evento_id == evento_id
    assert 'Semana de Exatas' in notificacao.assunto
    item = _objeto_na_central(fabrica, solicitacao['solicitante'])
    assert item['objeto'] == {'tipo': 'solicitacao_evento', 'id': str(solicitacao['id']),
                              'eventoIdentificadorPagina': 'semana-2026', 'submissaoId': None}


def test_solicitante_e_notificado_da_recusa_sem_evento(fabrica, solicitacao):
    resposta = fabrica.cliente(solicitacao['admin']).post(
        f"/api/admin/solicitacoes-evento/{solicitacao['id']}/recusar", json={'motivo': 'Fora do escopo.'})
    assert resposta.status_code == 200

    [notificacao] = _notificacoes(solicitacao['solicitante'], 'solicitacao_recusada')
    assert notificacao.evento_id is None
    item = _objeto_na_central(fabrica, solicitacao['solicitante'])
    assert item['objeto']['tipo'] == 'solicitacao_evento'
    assert item['objeto']['eventoIdentificadorPagina'] == 'semana-2026'
    assert fabrica.cliente(solicitacao['solicitante']).get('/api/me/notificacoes').get_json()['naoLidas'] == 1


def test_decisao_recusada_por_409_nao_notifica_de_novo(fabrica, solicitacao):
    admin = fabrica.cliente(solicitacao['admin'])
    admin.post(f"/api/admin/solicitacoes-evento/{solicitacao['id']}/recusar", json={'motivo': 'M.'})
    assert admin.post(f"/api/admin/solicitacoes-evento/{solicitacao['id']}/aprovar").status_code == 409

    assert Notificacao.query.filter_by(destinatario_id=solicitacao['solicitante'].id).count() == 1
