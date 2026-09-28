"""A16 — em simples_cega e duplo_cega o avaliador recebe o nome neutro
'<codigo>-v<numero>.<ext>' no download (Content-Disposition), em
versaoVigente e em documento; aberta mantém o real; autor/chair sempre o real."""
import pytest

NOME_REAL = 'Silva_Maria_UEFS.pdf'


def _cenario(fabrica, modelo):
    autora, chair, avaliador = fabrica.usuario('Autora'), fabrica.usuario('Chair'), fabrica.usuario('Avaliador')
    evento = fabrica.evento(chair=chair, modelo_de_avaliacao=modelo)
    cliente = fabrica.cliente(autora)
    chamada = fabrica.chamada(evento)
    submissao_id = int(cliente.post(f'/api/chamadas/{chamada.id}/submissoes', json={}).get_json()['id'])
    cliente.patch(f'/api/submissoes/{submissao_id}', json={'respostas': {'titulo': 'T', 'resumo': 'R'}})
    versao = fabrica.enviar_versao(cliente, submissao_id, nome=NOME_REAL)
    assert cliente.post(f'/api/submissoes/{submissao_id}/confirmar').status_code == 200
    atribuicao_id = fabrica.convidar(chair, fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    return {'autora': autora, 'chair': chair, 'avaliador': avaliador, 'submissao_id': submissao_id,
            'versao_id': versao['id'], 'atribuicao_id': atribuicao_id,
            'neutro': f'SUB-{submissao_id:04d}-v1.pdf'}


def _nome_no_download(fabrica, usuario, versao_id):
    resposta = fabrica.cliente(usuario).get(f'/api/versoes/{versao_id}/arquivo')
    assert resposta.status_code == 200
    return resposta.headers['Content-Disposition'].split('filename="')[1].split('"')[0]


def _nomes_na_atribuicao(fabrica, usuario, cenario):
    cliente = fabrica.cliente(usuario)
    detalhe = cliente.get(f"/api/atribuicoes/{cenario['atribuicao_id']}").get_json()
    return detalhe['versaoVigente']['nomeOriginal'], detalhe['documento']['nome']


@pytest.mark.parametrize('modelo', ['simples_cega', 'duplo_cega'])
def test_avaliador_recebe_nome_neutro_nos_modelos_cegos(fabrica, modelo):
    cenario = _cenario(fabrica, modelo)
    avaliador = cenario['avaliador']

    assert _nome_no_download(fabrica, avaliador, cenario['versao_id']) == cenario['neutro']
    assert _nomes_na_atribuicao(fabrica, avaliador, cenario) == (cenario['neutro'], cenario['neutro'])
    [item] = fabrica.cliente(avaliador).get('/api/me/atribuicoes').get_json()
    assert item['versaoVigente']['nomeOriginal'] == cenario['neutro']
    assert item['documento']['nome'] == cenario['neutro']


@pytest.mark.parametrize('modelo', ['simples_cega', 'duplo_cega'])
def test_autora_e_chair_veem_o_nome_real_nos_modelos_cegos(fabrica, modelo):
    cenario = _cenario(fabrica, modelo)

    for usuario in (cenario['autora'], cenario['chair']):
        assert _nome_no_download(fabrica, usuario, cenario['versao_id']) == NOME_REAL
    assert _nomes_na_atribuicao(fabrica, cenario['chair'], cenario) == (NOME_REAL, NOME_REAL)


def test_modelo_aberto_mantem_o_nome_real_para_o_avaliador(fabrica):
    cenario = _cenario(fabrica, 'aberta')

    assert _nome_no_download(fabrica, cenario['avaliador'], cenario['versao_id']) == NOME_REAL
    assert _nomes_na_atribuicao(fabrica, cenario['avaliador'], cenario) == (NOME_REAL, NOME_REAL)


def test_nome_real_nao_aparece_em_lugar_nenhum_da_resposta_do_avaliador(fabrica):
    cenario = _cenario(fabrica, 'duplo_cega')
    cliente = fabrica.cliente(cenario['avaliador'])
    for url in ('/api/me/atribuicoes', f"/api/atribuicoes/{cenario['atribuicao_id']}"):
        assert 'Silva_Maria' not in cliente.get(url).get_data(as_text=True)
