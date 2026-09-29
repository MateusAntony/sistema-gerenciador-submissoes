"""Revisão do P1, nota b (decisão do maestro): rebuttal vencido sem resposta
conta como fechado — situação 'aguardando_decisao' na leitura, versão nova
bloqueada (409) e decisão liberada."""
import io
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.rebuttal import Rebuttal


@pytest.fixture
def cenario(fabrica):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=2)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    rodada_id = fabrica.rodada_atual(submissao_id).id
    fabrica.cliente(chair).post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    return {'autora': autora, 'chair': chair, 'evento': evento, 'submissao_id': submissao_id, 'rodada_id': rodada_id}


def _vencer(cenario):
    Rebuttal.query.filter_by(rodada_id=cenario['rodada_id']).update({'prazo': datetime.utcnow() - timedelta(hours=1)})
    db.session.commit()


def _situacoes(fabrica, cenario, status=None):
    autora = fabrica.cliente(cenario['autora'])
    detalhe = autora.get(f"/api/submissoes/{cenario['submissao_id']}").get_json()['situacao']
    lista = autora.get('/api/me/submissoes' + (f'?status={status}' if status else '')).get_json()
    chair = fabrica.cliente(cenario['chair']).get(f"/api/eventos/{cenario['evento'].id}/submissoes").get_json()
    return detalhe, [i['situacao'] for i in lista], [i['situacao'] for i in chair]


def _enviar_versao(fabrica, cenario):
    return fabrica.cliente(cenario['autora']).post(
        f"/api/submissoes/{cenario['submissao_id']}/versoes",
        data={'arquivo': (io.BytesIO(b'%PDF'), 'v2.pdf'), 'nomeArquivo': 'v2.pdf'},
        content_type='multipart/form-data',
    )


def test_no_prazo_continua_aguardando_rebuttal_e_aceita_versao(fabrica, cenario):
    assert _situacoes(fabrica, cenario) == ('aguardando_rebuttal', ['aguardando_rebuttal'], ['aguardando_rebuttal'])
    assert _enviar_versao(fabrica, cenario).status_code == 201


def test_vencido_vira_aguardando_decisao_para_autora_e_chair(fabrica, cenario):
    _vencer(cenario)
    assert _situacoes(fabrica, cenario) == ('aguardando_decisao', ['aguardando_decisao'], ['aguardando_decisao'])
    assert _situacoes(fabrica, cenario, status='aguardando_rebuttal')[1] == []
    assert _situacoes(fabrica, cenario, status='aguardando_decisao')[1] == ['aguardando_decisao']


def test_vencido_bloqueia_versao_nova(fabrica, cenario):
    _vencer(cenario)
    resposta = _enviar_versao(fabrica, cenario)
    assert resposta.status_code == 409 and resposta.get_json()['codigo'] == 'versao_bloqueada'


def test_vencido_libera_a_decisao(fabrica, cenario):
    _vencer(cenario)
    resposta = fabrica.cliente(cenario['chair']).post(
        f"/api/rodadas/{cenario['rodada_id']}/decisao", json={'resultado': 'rejeitada', 'justificativa': 'J.'})
    assert resposta.status_code == 201


def test_filtro_do_chair_usa_a_situacao_efetiva(fabrica, cenario):
    _vencer(cenario)
    chair = fabrica.cliente(cenario['chair'])
    url = f"/api/eventos/{cenario['evento'].id}/submissoes?situacao="
    assert [i['id'] for i in chair.get(url + 'aguardando_decisao').get_json()] == [str(cenario['submissao_id'])]
    assert chair.get(url + 'aguardando_rebuttal').get_json() == []
