from app.models.evento import Submissao, VersaoDeArquivo


def test_submissao_confirmada_pela_api_grava_arquivo_na_pasta_de_uploads(app, fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair')
    chamada = fabrica.chamada(fabrica.evento(chair=chair))

    submissao_id = fabrica.submissao_confirmada(autora, chamada)

    assert Submissao.query.get(submissao_id).situacao == 'submetida'
    versao = VersaoDeArquivo.query.filter_by(submissao_id=submissao_id).one()
    assert versao.caminho_arquivo.startswith(app.config['PASTA_UPLOADS'])


def test_tabelas_comecam_vazias_em_cada_teste():
    assert Submissao.query.count() == 0
