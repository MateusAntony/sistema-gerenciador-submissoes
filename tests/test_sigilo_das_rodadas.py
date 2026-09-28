"""A9 — GET /api/submissoes/<id>/rodadas pedido por quem não é chair/admin:
decisao = null até ser comunicada, pendentes = [] e encerradaPorNome = null."""
import pytest


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair Carla')
    chamada = fabrica.chamada(fabrica.evento(chair=chair))  # modelo de avaliação 'aberta'
    submissao_id = fabrica.submissao_confirmada(autora, chamada)
    rodada_id = fabrica.rodada_atual(submissao_id).id
    fabrica.convidar(chair, rodada_id, fabrica.usuario('Avaliador Pendente'))

    cliente_chair = fabrica.cliente(chair)
    encerrada = cliente_chair.post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    assert encerrada.status_code == 200, encerrada.get_json()
    decidida = cliente_chair.post(f'/api/rodadas/{rodada_id}/decisao', json={
        'resultado': 'aceita', 'justificativa': 'Trabalho sólido.',
    })
    assert decidida.status_code == 201, decidida.get_json()
    return {
        'autora': autora, 'chair': chair, 'submissao_id': submissao_id,
        'decisao_id': decidida.get_json()['id'],
    }


def _rodada(fabrica, usuario, submissao_id):
    resposta = fabrica.cliente(usuario).get(f'/api/submissoes/{submissao_id}/rodadas')
    assert resposta.status_code == 200, resposta.get_json()
    [rodada] = resposta.get_json()
    return rodada


def _comunicar(fabrica, cenario):
    resposta = fabrica.cliente(cenario['chair']).post(f"/api/decisoes/{cenario['decisao_id']}/comunicar")
    assert resposta.status_code == 200


def test_autora_nao_ve_decisao_pendentes_nem_quem_encerrou(fabrica, cenario):
    rodada = _rodada(fabrica, cenario['autora'], cenario['submissao_id'])

    assert rodada['decisao'] is None
    assert rodada['pendentes'] == []
    assert rodada['encerradaPorNome'] is None
    assert rodada['encerradaEm'] is not None  # o resto do formato continua


def test_autora_ve_a_decisao_depois_de_comunicada_e_o_resto_continua_oculto(fabrica, cenario):
    _comunicar(fabrica, cenario)

    rodada = _rodada(fabrica, cenario['autora'], cenario['submissao_id'])

    assert rodada['decisao']['resultado'] == 'aceita'
    assert rodada['decisao']['comunicadaEm'] is not None
    assert rodada['pendentes'] == []
    assert rodada['encerradaPorNome'] is None


@pytest.mark.parametrize('comunicada', [False, True])
def test_chair_ve_os_tres_campos(fabrica, cenario, comunicada):
    if comunicada:
        _comunicar(fabrica, cenario)

    rodada = _rodada(fabrica, cenario['chair'], cenario['submissao_id'])

    assert rodada['decisao']['resultado'] == 'aceita'
    assert (rodada['decisao']['comunicadaEm'] is not None) is comunicada
    assert [p['avaliadorNome'] for p in rodada['pendentes']] == ['Avaliador Pendente']
    assert rodada['encerradaPorNome'] == 'Chair Carla'


def test_admin_ve_os_tres_campos(fabrica, cenario):
    rodada = _rodada(fabrica, fabrica.usuario('Admin', administrador=True), cenario['submissao_id'])

    assert rodada['decisao']['resultado'] == 'aceita'
    assert rodada['pendentes'] != []
    assert rodada['encerradaPorNome'] == 'Chair Carla'
