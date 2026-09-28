"""A17 — POST /submissoes/<id>/versoes só em rascunho, aguardando_rebuttal
ou aguardando_versao_corrigida (ou com rebuttal aberto na rodada atual);
fora disso 409 versao_bloqueada."""
import io

import pytest

from app.models.evento import VersaoDeArquivo


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, rebuttal_habilitado=True, prazo_rebuttal_dias=3)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    return {'autora': autora, 'chair': chair, 'submissao_id': submissao_id}


def _enviar(fabrica, cenario):
    return fabrica.cliente(cenario['autora']).post(
        f"/api/submissoes/{cenario['submissao_id']}/versoes",
        data={'arquivo': (io.BytesIO(b'%PDF v2'), 'v2.pdf'), 'nomeArquivo': 'v2.pdf'},
        content_type='multipart/form-data',
    )


def test_submissao_confirmada_com_chamada_aberta_nao_aceita_versao(fabrica, cenario):
    resposta = _enviar(fabrica, cenario)

    assert resposta.status_code == 409
    assert resposta.get_json()['codigo'] == 'versao_bloqueada'
    assert VersaoDeArquivo.query.filter_by(submissao_id=cenario['submissao_id']).count() == 1


def test_retirada_nao_aceita_versao(fabrica, cenario):
    fabrica.cliente(cenario['autora']).post(f"/api/submissoes/{cenario['submissao_id']}/retirar")
    assert _enviar(fabrica, cenario).get_json()['codigo'] == 'versao_bloqueada'


def test_rebuttal_aberto_aceita_versao(fabrica, cenario):
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    encerrada = fabrica.cliente(cenario['chair']).post(
        f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    assert encerrada.get_json()['rebuttal']['situacao'] == 'aguardando'

    assert _enviar(fabrica, cenario).status_code == 201


def test_aguardando_versao_corrigida_aceita_versao(fabrica):
    # Evento sem rebuttal, para a liberação vir só da situação.
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(fabrica.evento(chair=chair)))
    fabrica.encerrar_e_decidir(chair, submissao_id, 'aceita_com_correcoes', comunicar=True)

    assert _enviar(fabrica, {'autora': autora, 'submissao_id': submissao_id}).status_code == 201


def _encerrar(fabrica, cenario):
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    resposta = fabrica.cliente(cenario['chair']).post(
        f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    assert resposta.status_code == 200, resposta.get_json()
    return rodada_id


def _responder_rebuttal(fabrica, cenario, rodada_id):
    resposta = fabrica.cliente(cenario['autora']).post(
        f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'Resposta.'})
    assert resposta.status_code == 200, resposta.get_json()


def test_rebuttal_ja_respondido_nao_libera_versao(fabrica, cenario):
    _responder_rebuttal(fabrica, cenario, _encerrar(fabrica, cenario))
    assert _enviar(fabrica, cenario).get_json()['codigo'] == 'versao_bloqueada'


def test_vale_o_rebuttal_da_rodada_mais_recente(fabrica):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=3)
    cenario = {'autora': autora, 'chair': chair,
               'submissao_id': fabrica.submissao_confirmada(autora, fabrica.chamada(evento))}
    # Rodada 1: rebuttal respondido; decisão de nova rodada.
    rodada_1 = _encerrar(fabrica, cenario)
    _responder_rebuttal(fabrica, cenario, rodada_1)
    decisao = fabrica.cliente(chair).post(f'/api/rodadas/{rodada_1}/decisao',
                                          json={'resultado': 'nova_rodada', 'justificativa': 'J.'})
    assert decisao.status_code == 201
    assert fabrica.cliente(chair).post(
        f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={}).status_code == 201
    # Rodada 2 encerrada: rebuttal aberto de novo.
    _encerrar(fabrica, cenario)

    assert _enviar(fabrica, cenario).status_code == 201


def test_decisao_final_nao_aceita_versao(fabrica):
    # Evento sem rebuttal: o fechamento do rebuttal na decisão final é do A12.
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(fabrica.evento(chair=chair)))
    fabrica.encerrar_e_decidir(chair, submissao_id, 'aceita', comunicar=True)

    resposta = _enviar(fabrica, {'autora': autora, 'submissao_id': submissao_id})
    assert resposta.get_json()['codigo'] == 'versao_bloqueada'


def test_rascunho_continua_aceitando_varias_versoes(fabrica):
    autora = fabrica.usuario('Autora')
    chamada = fabrica.chamada(fabrica.evento(chair=fabrica.usuario('Chair')))
    cliente = fabrica.cliente(autora)
    submissao_id = int(cliente.post(f'/api/chamadas/{chamada.id}/submissoes', json={}).get_json()['id'])
    fabrica.enviar_versao(cliente, submissao_id, nome='v1.pdf')
    fabrica.enviar_versao(cliente, submissao_id, nome='v2.pdf')
    assert VersaoDeArquivo.query.filter_by(submissao_id=submissao_id, vigente=True).one().nome_original == 'v2.pdf'
