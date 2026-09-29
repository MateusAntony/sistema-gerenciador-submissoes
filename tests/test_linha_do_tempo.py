"""A13 — GET /submissoes/<id>/linha-do-tempo inclui retirada, rodada
aberta/encerrada, rebuttal aberto/enviado, decisão (registrada só para o
chair; comunicada para todos), versão corrigida enviada/devolvida/validada.
Itens: {id, tipo, rotulo, data, fuso}, em ordem de data."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.rebuttal import Rebuttal

TIPOS = {'submissao', 'versao', 'fase', 'rodada', 'rebuttal', 'decisao'}


def _cenario(fabrica, **evento):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, **evento)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    return {'autora': autora, 'chair': chair, 'submissao_id': submissao_id}


def _linha(fabrica, usuario, cenario):
    resposta = fabrica.cliente(usuario).get(f"/api/submissoes/{cenario['submissao_id']}/linha-do-tempo")
    assert resposta.status_code == 200, resposta.get_json()
    itens = resposta.get_json()
    for item in itens:
        assert set(item) == {'id', 'tipo', 'rotulo', 'data', 'fuso'}
        assert item['tipo'] in TIPOS and item['fuso'] == 'America/Bahia'
    assert [i['data'] for i in itens] == sorted(i['data'] for i in itens)
    assert len({i['id'] for i in itens}) == len(itens)
    return [i['rotulo'] for i in itens]


def test_retirada_aparece(fabrica):
    cenario = _cenario(fabrica)
    assert fabrica.cliente(cenario['autora']).post(f"/api/submissoes/{cenario['submissao_id']}/retirar").status_code == 200

    rotulos = _linha(fabrica, cenario['autora'], cenario)

    assert rotulos[-1] == 'Submissão retirada'
    assert 'Submissão confirmada' in rotulos and 'Rodada 1 aberta' in rotulos


def test_rodada_rebuttal_e_decisao_comunicada(fabrica):
    cenario = _cenario(fabrica, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=2)
    chair = fabrica.cliente(cenario['chair'])
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    chair.post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    fabrica.cliente(cenario['autora']).post(f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'R.'})
    decisao = chair.post(f'/api/rodadas/{rodada_id}/decisao', json={'resultado': 'rejeitada', 'justificativa': 'J.'})

    # Antes de comunicar: o chair vê a decisão registrada; a autora, nada da decisão.
    rotulos_chair = _linha(fabrica, cenario['chair'], cenario)
    rotulos_autora = _linha(fabrica, cenario['autora'], cenario)
    assert 'Decisão da rodada 1 registrada' in rotulos_chair
    assert not any(r.startswith('Decisão') for r in rotulos_autora)
    for rotulo in ('Rodada 1 encerrada', 'Rebuttal aberto', 'Rebuttal enviado'):
        assert rotulo in rotulos_autora

    chair.post(f"/api/decisoes/{decisao.get_json()['id']}/comunicar")
    rotulos_autora = _linha(fabrica, cenario['autora'], cenario)
    assert 'Decisão da rodada 1 comunicada' in rotulos_autora
    assert 'Decisão da rodada 1 registrada' not in rotulos_autora


def test_versao_corrigida_enviada_devolvida_e_validada(fabrica):
    cenario = _cenario(fabrica)
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], 'aceita_com_correcoes', comunicar=True)
    autora, chair = fabrica.cliente(cenario['autora']), fabrica.cliente(cenario['chair'])
    url = f"/api/submissoes/{cenario['submissao_id']}/versao-corrigida"
    versao = fabrica.enviar_versao(autora, cenario['submissao_id'], nome='corrigida.pdf')
    assert autora.post(url, json={'versaoId': int(versao['id']), 'descricaoDasAlteracoes': 'C.'}).status_code == 200
    assert chair.post(f'{url}/devolver', json={'apontamentos': 'Falta X.'}).status_code == 200
    assert autora.post(url, json={'versaoId': int(versao['id']), 'descricaoDasAlteracoes': 'C2.'}).status_code == 200
    assert chair.post(f'{url}/validar').status_code == 200

    rotulos = _linha(fabrica, cenario['autora'], cenario)

    assert 'Versão corrigida devolvida' in rotulos
    assert 'Versão corrigida enviada' in rotulos
    assert rotulos[-1] == 'Versão corrigida validada'


def test_rebuttal_vencido_aparece_como_expirado(fabrica):
    cenario = _cenario(fabrica, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=2)
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    fabrica.cliente(cenario['chair']).post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    Rebuttal.query.filter_by(rodada_id=rodada_id).update({'prazo': datetime.utcnow() - timedelta(hours=1)})
    db.session.commit()

    assert 'Rebuttal expirado' in _linha(fabrica, cenario['autora'], cenario)


@pytest.mark.parametrize('papel', ['estranho', 'avaliador'])
def test_quem_nao_e_autor_nem_chair_recebe_404(fabrica, papel):
    cenario = _cenario(fabrica)
    usuario = fabrica.usuario(papel)
    if papel == 'avaliador':
        fabrica.aceitar(usuario, fabrica.convidar(cenario['chair'], fabrica.rodada_atual(cenario['submissao_id']).id, usuario))
    resposta = fabrica.cliente(usuario).get(f"/api/submissoes/{cenario['submissao_id']}/linha-do-tempo")
    assert resposta.status_code == 404


def _encerrar_com_rebuttal(fabrica):
    cenario = _cenario(fabrica, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=2)
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    fabrica.cliente(cenario['chair']).post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    return cenario, rodada_id


def test_rebuttal_no_prazo_nao_aparece_como_expirado(fabrica):
    cenario, _ = _encerrar_com_rebuttal(fabrica)
    rotulos = _linha(fabrica, cenario['autora'], cenario)
    assert 'Rebuttal aberto' in rotulos and 'Rebuttal expirado' not in rotulos


def test_rebuttal_respondido_nao_expira_depois_do_prazo(fabrica):
    cenario, rodada_id = _encerrar_com_rebuttal(fabrica)
    fabrica.cliente(cenario['autora']).post(f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'R.'})
    Rebuttal.query.filter_by(rodada_id=rodada_id).update({'prazo': datetime.utcnow() - timedelta(hours=1)})
    db.session.commit()

    rotulos = _linha(fabrica, cenario['autora'], cenario)
    assert 'Rebuttal enviado' in rotulos and 'Rebuttal expirado' not in rotulos
