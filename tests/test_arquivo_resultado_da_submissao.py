"""Nota B do Lince (decisão do maestro): concluir execução só aceita
arquivoResultadoId que seja versão da própria submissão (senão 422)."""
import pytest

from app.models.evento import VersaoDeArquivo
from app.models.execucao_fase import ExecucaoFase

FASE = {'nome': 'Revisão', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': True, 'permiteDevolucao': False, 'ativo': True}


@pytest.fixture
def cenario(fabrica):
    chair, rita = fabrica.usuario('Chair'), fabrica.usuario('Rita')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/fases', json={**FASE, 'responsavelPadraoId': rita.id})
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), chamada)
    outra_id = fabrica.submissao_confirmada(fabrica.usuario('Outra'), chamada)
    execucao = ExecucaoFase.query.filter_by(submissao_id=submissao_id).one()
    return {
        'rita': rita, 'execucao_id': execucao.id,
        'versao_propria': VersaoDeArquivo.query.filter_by(submissao_id=submissao_id).one().id,
        'versao_alheia': VersaoDeArquivo.query.filter_by(submissao_id=outra_id).one().id,
    }


def _concluir(fabrica, cenario, arquivo_id):
    return fabrica.cliente(cenario['rita']).post(
        f"/api/execucoes-fase/{cenario['execucao_id']}/concluir", json={'arquivoResultadoId': arquivo_id})


@pytest.mark.parametrize('formato', [int, str])
def test_versao_da_propria_submissao_e_aceita(fabrica, cenario, formato):
    resposta = _concluir(fabrica, cenario, formato(cenario['versao_propria']))
    assert resposta.status_code == 200
    assert resposta.get_json()['arquivoResultadoId'] == cenario['versao_propria']


@pytest.mark.parametrize('qual', ['versao_alheia', 'inexistente'])
def test_versao_de_outra_submissao_ou_inexistente_e_422(fabrica, cenario, qual):
    arquivo_id = cenario['versao_alheia'] if qual == 'versao_alheia' else 99999

    resposta = _concluir(fabrica, cenario, arquivo_id)

    assert resposta.status_code == 422
    assert 'arquivoResultadoId' in resposta.get_json()['campos']
    assert ExecucaoFase.query.get(cenario['execucao_id']).status != 'concluida'
