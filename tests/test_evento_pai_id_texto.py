"""eventoPaiId em texto numérico ('1'), como o front manda ids: aceito em
POST/PATCH /solicitacoes-evento e PATCH /eventos/<id>; texto não numérico
continua 422. O valor é gravado e devolvido como número."""
import pytest

from app.models.evento import SolicitacaoEvento


def _corpo(identificador, **extra):
    return {'titulo': 'Workshop', 'identificadorPagina': identificador, 'dataInicio': '2026-11-10',
            'dataTermino': '2026-11-12', 'pais': 'Brasil', 'fuso': 'America/Bahia', **extra}


@pytest.fixture
def cenario(fabrica):
    chair = fabrica.usuario('Chair')
    return {'chair': chair, 'cliente': fabrica.cliente(chair), 'pai': fabrica.evento(chair=chair),
            'evento': fabrica.evento(chair=chair)}


@pytest.mark.parametrize('formato', [str, lambda i: f' {i} '])
def test_solicitacao_aceita_id_em_texto(cenario, formato):
    resposta = cenario['cliente'].post('/api/solicitacoes-evento',
                                       json=_corpo('ws-2026', eventoPaiId=formato(cenario['pai'].id)))

    assert resposta.status_code == 201, resposta.get_json()
    assert resposta.get_json()['eventoPaiId'] == cenario['pai'].id
    assert SolicitacaoEvento.query.one().evento_pai_id == cenario['pai'].id


def test_edicao_da_solicitacao_aceita_id_em_texto(cenario):
    criada = cenario['cliente'].post('/api/solicitacoes-evento', json=_corpo('ws-2026')).get_json()
    resposta = cenario['cliente'].patch(f"/api/solicitacoes-evento/{criada['id']}",
                                        json=_corpo('ws-2026', eventoPaiId=str(cenario['pai'].id)))
    assert resposta.status_code == 200 and resposta.get_json()['eventoPaiId'] == cenario['pai'].id


def test_patch_do_evento_aceita_id_em_texto(cenario):
    resposta = cenario['cliente'].patch(f"/api/eventos/{cenario['evento'].id}",
                                        json={'eventoPaiId': str(cenario['pai'].id)})
    assert resposta.status_code == 200 and resposta.get_json()['eventoPaiId'] == cenario['pai'].id


@pytest.mark.parametrize('invalido', ['abc', '1a', '', '-1', '1.0', '²', '١', '１'])  # ², ١ e １: dígitos Unicode
def test_texto_nao_numerico_continua_422(cenario, invalido):
    solicitacao = cenario['cliente'].post('/api/solicitacoes-evento', json=_corpo('ws-2026', eventoPaiId=invalido))
    evento = cenario['cliente'].patch(f"/api/eventos/{cenario['evento'].id}", json={'eventoPaiId': invalido})

    assert solicitacao.status_code == 422 and 'eventoPaiId' in solicitacao.get_json()['campos']
    assert evento.status_code == 422 and 'eventoPaiId' in evento.get_json()['campos']


def test_texto_de_pai_alheio_continua_recusado(fabrica, cenario):
    alheio = fabrica.evento(chair=fabrica.usuario('Outro'))
    resposta = cenario['cliente'].patch(f"/api/eventos/{cenario['evento'].id}", json={'eventoPaiId': str(alheio.id)})
    assert resposta.status_code == 422
