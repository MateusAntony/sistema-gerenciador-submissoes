"""A2 — GET /api/submissoes/<id>/versoes também para chair/admin do evento."""
import pytest

CAMPOS = {'id', 'numero', 'nomeOriginal', 'tamanhoBytes', 'vigente', 'dataEnvio'}


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair')
    chamada = fabrica.chamada(fabrica.evento(chair=chair))
    submissao_id = fabrica.submissao_confirmada(autora, chamada)
    return {'autora': autora, 'chair': chair, 'submissao_id': submissao_id}


def _versoes(fabrica, usuario, submissao_id):
    return fabrica.cliente(usuario).get(f'/api/submissoes/{submissao_id}/versoes')


@pytest.mark.parametrize('papel', ['autora', 'chair', 'admin'])
def test_autora_chair_e_admin_listam_as_versoes(fabrica, cenario, papel):
    usuario = fabrica.usuario('Admin', administrador=True) if papel == 'admin' else cenario[papel]

    resposta = _versoes(fabrica, usuario, cenario['submissao_id'])

    assert resposta.status_code == 200
    [versao] = resposta.get_json()
    assert CAMPOS <= set(versao)
    assert versao['numero'] == 1 and versao['vigente'] is True
    assert versao['nomeOriginal'] == 'trabalho.pdf'


def test_chair_de_outro_evento_nao_lista(fabrica, cenario):
    outro_chair = fabrica.usuario('Outro chair')
    fabrica.evento(chair=outro_chair)
    assert _versoes(fabrica, outro_chair, cenario['submissao_id']).status_code == 404


def test_avaliador_aceito_continua_sem_acesso_a_lista(fabrica, cenario):
    avaliador = fabrica.usuario('Avaliador')
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    fabrica.aceitar(avaliador, fabrica.convidar(cenario['chair'], rodada_id, avaliador))
    assert _versoes(fabrica, avaliador, cenario['submissao_id']).status_code == 404


def test_sem_sessao_responde_401(fabrica, cenario):
    assert fabrica.cliente().get(f"/api/submissoes/{cenario['submissao_id']}/versoes").status_code == 401
