"""A3 — versaoVigente em GET /api/atribuicoes/<id> e em GET /api/me/atribuicoes."""
import pytest

from app.extensions import db
from app.models.evento import VersaoDeArquivo


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair')
    chamada = fabrica.chamada(fabrica.evento(chair=chair))
    submissao_id = fabrica.submissao_confirmada(autora, chamada)
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(chair, fabrica.rodada_atual(submissao_id).id, avaliador)
    return {'autora': autora, 'chair': chair, 'avaliador': avaliador,
            'submissao_id': submissao_id, 'atribuicao_id': atribuicao_id}


def _nas_duas_rotas(fabrica, cenario):
    cliente = fabrica.cliente(cenario['avaliador'])
    detalhe = cliente.get(f"/api/atribuicoes/{cenario['atribuicao_id']}")
    fila = cliente.get('/api/me/atribuicoes')
    assert detalhe.status_code == 200 and fila.status_code == 200
    [item] = fila.get_json()
    return detalhe.get_json()['versaoVigente'], item['versaoVigente']


def test_traz_id_numero_e_nome_da_versao_vigente(fabrica, cenario):
    vigente = VersaoDeArquivo.query.filter_by(submissao_id=cenario['submissao_id'], vigente=True).one()
    esperado = {'id': str(vigente.id), 'numero': 1, 'nomeOriginal': 'trabalho.pdf'}

    assert _nas_duas_rotas(fabrica, cenario) == (esperado, esperado)


def test_acompanha_a_versao_nova(fabrica, cenario):
    # Reenvio pelo fluxo real: decisão "aceita com correções" comunicada (A17).
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], 'aceita_com_correcoes', comunicar=True)
    nova = fabrica.enviar_versao(fabrica.cliente(cenario['autora']), cenario['submissao_id'], nome='v2.pdf')
    esperado = {'id': nova['id'], 'numero': 2, 'nomeOriginal': 'v2.pdf'}

    assert _nas_duas_rotas(fabrica, cenario) == (esperado, esperado)


def test_null_quando_nao_ha_versao_vigente(fabrica, cenario):
    VersaoDeArquivo.query.filter_by(submissao_id=cenario['submissao_id']).update({'vigente': False})
    db.session.commit()

    assert _nas_duas_rotas(fabrica, cenario) == (None, None)
