"""A11 — abrir a rodada seguinte comunica a decisão 'nova_rodada' da rodada
anterior e notifica o autor ("Nova rodada de avaliação")."""
import pytest

from app.models.decisao import Decisao
from app.models.notificacao import Notificacao


@pytest.fixture
def cenario(fabrica):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, maximo_de_rodadas=2)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    decisao_id = fabrica.encerrar_e_decidir(chair, submissao_id, 'nova_rodada')
    return {'autora': autora, 'chair': chair, 'submissao_id': submissao_id, 'decisao_id': decisao_id}


def _abrir(fabrica, cenario):
    resposta = fabrica.cliente(cenario['chair']).post(f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={})
    assert resposta.status_code == 201, resposta.get_json()


def _notificacoes_da_autora(cenario):
    return Notificacao.query.filter_by(destinatario_id=cenario['autora'].id).all()


def test_antes_de_abrir_a_decisao_nao_esta_comunicada(fabrica, cenario):
    assert Decisao.query.get(cenario['decisao_id']).comunicada_em is None
    assert _notificacoes_da_autora(cenario) == []


def test_abrir_a_rodada_seguinte_comunica_a_decisao(fabrica, cenario):
    _abrir(fabrica, cenario)

    rodadas = fabrica.cliente(cenario['autora']).get(f"/api/submissoes/{cenario['submissao_id']}/rodadas").get_json()
    assert rodadas[0]['decisao']['resultado'] == 'nova_rodada'
    assert rodadas[0]['decisao']['comunicadaEm'] is not None


def test_autora_recebe_notificacao_de_nova_rodada(fabrica, cenario):
    _abrir(fabrica, cenario)

    [notificacao] = _notificacoes_da_autora(cenario)
    assert notificacao.tipo == 'nova_rodada'
    assert notificacao.assunto.startswith('Nova rodada de avaliação')
    assert (notificacao.objeto_tipo, notificacao.objeto_id) == ('submissao', str(cenario['submissao_id']))
    sino = fabrica.cliente(cenario['autora']).get('/api/me/notificacoes').get_json()
    assert sino['naoLidas'] == 1


def test_decisao_ja_comunicada_nao_notifica_de_novo(fabrica, cenario):
    comunicada = fabrica.cliente(cenario['chair']).post(f"/api/decisoes/{cenario['decisao_id']}/comunicar")
    assert comunicada.status_code == 200
    primeira = Decisao.query.get(cenario['decisao_id']).comunicada_em

    _abrir(fabrica, cenario)

    assert Decisao.query.get(cenario['decisao_id']).comunicada_em == primeira
    assert [n.tipo for n in _notificacoes_da_autora(cenario)] == ['decisao_comunicada']
