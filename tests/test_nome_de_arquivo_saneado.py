"""B8 — nome do arquivo saneado no upload: sem NUL/caracteres de controle,
tamanho limitado, extensão mantida."""
import io
import os

import pytest

from app.models.evento import VersaoDeArquivo


@pytest.fixture
def rascunho(fabrica):
    autora = fabrica.usuario('Autora')
    chamada = fabrica.chamada(fabrica.evento(chair=fabrica.usuario('Chair')))
    cliente = fabrica.cliente(autora)
    submissao_id = int(cliente.post(f'/api/chamadas/{chamada.id}/submissoes', json={}).get_json()['id'])
    return cliente, submissao_id


def _enviar(rascunho, nome_arquivo, nome_do_arquivo='t.pdf'):
    cliente, submissao_id = rascunho
    return cliente.post(
        f'/api/submissoes/{submissao_id}/versoes',
        data={'arquivo': (io.BytesIO(b'%PDF'), nome_do_arquivo), 'nomeArquivo': nome_arquivo},
        content_type='multipart/form-data',
    )


def test_nul_e_controle_saem_do_nome(rascunho):
    resposta = _enviar(rascunho, 'rel\x00at\x01ório\r\n.pdf')

    assert resposta.status_code == 201, resposta.get_json()
    assert resposta.get_json()['nomeOriginal'] == 'relatório.pdf'


def test_nome_longo_e_cortado_mantendo_a_extensao(rascunho):
    resposta = _enviar(rascunho, 'a' * 400 + '.pdf')

    assert resposta.status_code == 201
    nome = resposta.get_json()['nomeOriginal']
    assert len(nome) <= 200
    assert nome.endswith('.pdf') and nome.startswith('aaa')
    caminho = VersaoDeArquivo.query.get(int(resposta.get_json()['id'])).caminho_arquivo
    assert os.path.isfile(caminho) and len(os.path.basename(caminho)) <= 120


def test_nome_so_de_controle_e_recusado_sem_gravar_nada(rascunho, app):
    antes = set(os.listdir(app.config['PASTA_UPLOADS']))
    resposta = _enviar(rascunho, '\x00\x01\x7f')

    assert resposta.status_code == 422
    assert resposta.get_json()['campos'] == {'arquivo': 'Anexe um arquivo.'}
    assert set(os.listdir(app.config['PASTA_UPLOADS'])) == antes


def test_formato_e_conferido_depois_de_sanear(rascunho):
    resposta = _enviar(rascunho, 'trabalho.do\x00cx')

    assert resposta.status_code == 422
    assert 'Formatos aceitos' in resposta.get_json()['campos']['arquivo']


def test_sem_nome_arquivo_usa_o_nome_do_arquivo_saneado(rascunho):
    cliente, submissao_id = rascunho
    resposta = cliente.post(
        f'/api/submissoes/{submissao_id}/versoes',
        data={'arquivo': (io.BytesIO(b'%PDF'), 'x\x7fy.pdf')},
        content_type='multipart/form-data',
    )
    assert resposta.status_code == 201, resposta.get_json()
    assert resposta.get_json()['nomeOriginal'] == 'xy.pdf'
