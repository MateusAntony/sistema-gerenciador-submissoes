"""A12 — ciclo do rebuttal: não abre na última rodada possível; fecha
('encerrado') quando a decisão final é comunicada; a submissão fica em
'aguardando_rebuttal' enquanto ele está aberto."""
import io
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.evento import Submissao
from app.models.rebuttal import Rebuttal


def _cenario(fabrica, maximo_de_rodadas=2):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, rebuttal_habilitado=True, prazo_rebuttal_dias=3,
                            maximo_de_rodadas=maximo_de_rodadas)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    return {'autora': autora, 'chair': chair, 'evento': evento, 'submissao_id': submissao_id}


def _encerrar(fabrica, cenario):
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    resposta = fabrica.cliente(cenario['chair']).post(
        f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    assert resposta.status_code == 200, resposta.get_json()
    return rodada_id, resposta.get_json()


def _decidir(fabrica, cenario, rodada_id, resultado):
    resposta = fabrica.cliente(cenario['chair']).post(
        f'/api/rodadas/{rodada_id}/decisao', json={'resultado': resultado, 'justificativa': 'J.'})
    assert resposta.status_code == 201, resposta.get_json()
    return resposta.get_json()['id']


def _vencer_rebuttal(rodada_id):
    """O prazo passa sem resposta (não há job que expire o rebuttal)."""
    Rebuttal.query.filter_by(rodada_id=rodada_id).update({'prazo': datetime.utcnow() - timedelta(hours=1)})
    db.session.commit()


def _situacao_real(cenario):
    return Submissao.query.get(cenario['submissao_id']).situacao


def _rebuttal(rodada_id):
    return Rebuttal.query.filter_by(rodada_id=rodada_id).first()


def test_encerrar_abre_rebuttal_e_submissao_fica_aguardando_rebuttal(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, rodada = _encerrar(fabrica, cenario)

    assert rodada['rebuttal']['situacao'] == 'aguardando'
    autora = fabrica.cliente(cenario['autora'])
    assert autora.get(f"/api/submissoes/{cenario['submissao_id']}").get_json()['situacao'] == 'aguardando_rebuttal'
    assert [s['situacao'] for s in autora.get('/api/me/submissoes').get_json()] == ['aguardando_rebuttal']


def test_responder_o_rebuttal_passa_para_aguardando_decisao(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)

    enviada = fabrica.cliente(cenario['autora']).post(f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'R.'})

    assert enviada.status_code == 200
    assert _situacao_real(cenario) == 'aguardando_decisao'


@pytest.mark.parametrize('maximo', [1])
def test_nao_abre_rebuttal_quando_nao_pode_haver_nova_rodada(fabrica, maximo):
    cenario = _cenario(fabrica, maximo_de_rodadas=maximo)
    rodada_id, rodada = _encerrar(fabrica, cenario)

    assert rodada['rebuttal'] is None
    assert _rebuttal(rodada_id) is None
    assert _situacao_real(cenario) == 'submetida'


def test_nao_abre_rebuttal_na_ultima_rodada(fabrica):
    cenario = _cenario(fabrica, maximo_de_rodadas=2)
    rodada_1, _ = _encerrar(fabrica, cenario)
    _vencer_rebuttal(rodada_1)  # decidir com rebuttal aberto no prazo dá 409
    _decidir(fabrica, cenario, rodada_1, 'nova_rodada')
    aberta = fabrica.cliente(cenario['chair']).post(f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={})
    assert aberta.status_code == 201

    rodada_2, rodada = _encerrar(fabrica, cenario)

    assert rodada['numero'] == 2
    assert rodada['rebuttal'] is None and _rebuttal(rodada_2) is None


@pytest.mark.parametrize('resultado', ['aceita', 'aceita_com_correcoes', 'rejeitada'])
def test_comunicar_decisao_final_encerra_o_rebuttal_aberto(fabrica, resultado):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)
    _vencer_rebuttal(rodada_id)  # decidir com rebuttal aberto no prazo dá 409
    decisao_id = _decidir(fabrica, cenario, rodada_id, resultado)
    assert _rebuttal(rodada_id).situacao == 'aguardando'  # decidida, ainda não comunicada

    fabrica.cliente(cenario['chair']).post(f'/api/decisoes/{decisao_id}/comunicar')

    assert _rebuttal(rodada_id).situacao == 'encerrado'
    autora = fabrica.cliente(cenario['autora'])
    assert autora.get(f'/api/rodadas/{rodada_id}/rebuttal').get_json()['situacao'] == 'encerrado'
    assert autora.put(f'/api/rodadas/{rodada_id}/rebuttal', json={'texto': 'tarde'}).status_code == 409


def test_comunicar_em_lote_tambem_encerra(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)
    _vencer_rebuttal(rodada_id)  # decidir com rebuttal aberto no prazo dá 409
    decisao_id = _decidir(fabrica, cenario, rodada_id, 'rejeitada')

    resposta = fabrica.cliente(cenario['chair']).post(
        f"/api/eventos/{cenario['evento'].id}/decisoes/comunicar-lote", json={'decisaoIds': [decisao_id]})

    assert resposta.status_code == 200
    assert _rebuttal(rodada_id).situacao == 'encerrado'


def test_rebuttal_ja_enviado_continua_enviado(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)
    fabrica.cliente(cenario['autora']).post(f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'R.'})
    decisao_id = _decidir(fabrica, cenario, rodada_id, 'aceita')

    fabrica.cliente(cenario['chair']).post(f'/api/decisoes/{decisao_id}/comunicar')

    assert _rebuttal(rodada_id).situacao == 'enviado'


def test_abrir_nova_rodada_encerra_o_rebuttal_da_anterior(fabrica):
    cenario = _cenario(fabrica, maximo_de_rodadas=3)
    rodada_1, _ = _encerrar(fabrica, cenario)
    _vencer_rebuttal(rodada_1)  # decidir com rebuttal aberto no prazo dá 409
    _decidir(fabrica, cenario, rodada_1, 'nova_rodada')

    aberta = fabrica.cliente(cenario['chair']).post(f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={})

    assert aberta.status_code == 201
    assert _rebuttal(rodada_1).situacao == 'encerrado'
    assert _situacao_real(cenario) == 'em_avaliacao'


def test_depois_da_decisao_final_comunicada_rebuttal_nao_libera_versao_nova(fabrica):
    # Complementa o A17: o rebuttal aberto liberava o envio; comunicada a decisão, não mais.
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)
    _vencer_rebuttal(rodada_id)  # decidir com rebuttal aberto no prazo dá 409
    decisao_id = _decidir(fabrica, cenario, rodada_id, 'aceita')
    fabrica.cliente(cenario['chair']).post(f'/api/decisoes/{decisao_id}/comunicar')

    resposta = fabrica.cliente(cenario['autora']).post(
        f"/api/submissoes/{cenario['submissao_id']}/versoes",
        data={'arquivo': (io.BytesIO(b'%PDF'), 'v2.pdf'), 'nomeArquivo': 'v2.pdf'},
        content_type='multipart/form-data',
    )
    assert resposta.get_json()['codigo'] == 'versao_bloqueada'


# --- Revisão do P1, item 3: estágio em_rebuttal e decisão bloqueada ---

def _linha_da_fila(fabrica, cenario):
    linhas = fabrica.cliente(cenario['chair']).get(f"/api/eventos/{cenario['evento'].id}/decisoes").get_json()
    [linha] = [l for l in linhas if l['submissaoId'] == cenario['submissao_id']]
    return linha


def test_fila_mostra_em_rebuttal_e_decisao_e_bloqueada_enquanto_aberto(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)

    assert _linha_da_fila(fabrica, cenario)['estagio'] == 'em_rebuttal'
    resposta = fabrica.cliente(cenario['chair']).post(
        f'/api/rodadas/{rodada_id}/decisao', json={'resultado': 'rejeitada', 'justificativa': 'J.'})
    assert resposta.status_code == 409
    assert resposta.get_json()['codigo'] == 'rebuttal_aberto'
    assert _situacao_real(cenario) == 'aguardando_rebuttal'


def test_rebuttal_respondido_libera_a_decisao(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)
    fabrica.cliente(cenario['autora']).post(f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'R.'})

    assert _linha_da_fila(fabrica, cenario)['estagio'] == 'aguardando_decisao'
    _decidir(fabrica, cenario, rodada_id, 'rejeitada')


def test_rebuttal_vencido_libera_a_decisao(fabrica):
    cenario = _cenario(fabrica)
    rodada_id, _ = _encerrar(fabrica, cenario)
    _vencer_rebuttal(rodada_id)

    assert _linha_da_fila(fabrica, cenario)['estagio'] == 'aguardando_decisao'
    _decidir(fabrica, cenario, rodada_id, 'rejeitada')
