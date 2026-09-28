"""Decisão do maestro (a), junto com o A9: para quem não é chair/admin do
evento, enquanto a decisão da rodada mais recente não tiver comunicadaEm,
/submissoes/<id> e /me/submissoes (inclusive o filtro ?status=) mostram
situacao = 'aguardando_decisao'."""
import pytest


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, maximo_de_rodadas=2)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    return {'autora': autora, 'chair': chair, 'evento': evento, 'submissao_id': submissao_id}


def _decidir(fabrica, cenario, resultado):
    chair = fabrica.cliente(cenario['chair'])
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    assert chair.post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True}).status_code == 200
    decisao = chair.post(f'/api/rodadas/{rodada_id}/decisao', json={'resultado': resultado, 'justificativa': 'J.'})
    assert decisao.status_code == 201, decisao.get_json()
    return decisao.get_json()['id']


def _comunicar(fabrica, cenario, decisao_id):
    assert fabrica.cliente(cenario['chair']).post(f'/api/decisoes/{decisao_id}/comunicar').status_code == 200


def _vista_da_autora(fabrica, cenario, status=None):
    cliente = fabrica.cliente(cenario['autora'])
    detalhe = cliente.get(f"/api/submissoes/{cenario['submissao_id']}").get_json()['situacao']
    url = '/api/me/submissoes' + (f'?status={status}' if status else '')
    lista = [item['situacao'] for item in cliente.get(url).get_json()]
    return detalhe, lista


def _vista_do_chair(fabrica, cenario):
    resposta = fabrica.cliente(cenario['chair']).get(f"/api/eventos/{cenario['evento'].id}/submissoes")
    return [item['situacao'] for item in resposta.get_json()]


def test_antes_de_decidir_a_autora_ve_a_situacao_real(fabrica, cenario):
    assert _vista_da_autora(fabrica, cenario) == ('submetida', ['submetida'])


@pytest.mark.parametrize('resultado, situacao_real', [
    ('rejeitada', 'rejeitada'),
    ('aceita', 'aceita'),
    ('aceita_com_correcoes', 'aguardando_versao_corrigida'),
])
def test_decisao_nao_comunicada_fica_oculta_ate_comunicar(fabrica, cenario, resultado, situacao_real):
    decisao_id = _decidir(fabrica, cenario, resultado)

    assert _vista_da_autora(fabrica, cenario) == ('aguardando_decisao', ['aguardando_decisao'])
    assert _vista_do_chair(fabrica, cenario) == [situacao_real]

    _comunicar(fabrica, cenario, decisao_id)
    assert _vista_da_autora(fabrica, cenario) == (situacao_real, [situacao_real])


def test_filtro_por_status_nao_encontra_a_decisao_antes_de_comunicar(fabrica, cenario):
    decisao_id = _decidir(fabrica, cenario, 'rejeitada')

    assert _vista_da_autora(fabrica, cenario, status='rejeitada')[1] == []
    assert _vista_da_autora(fabrica, cenario, status='aguardando_decisao')[1] == ['aguardando_decisao']

    _comunicar(fabrica, cenario, decisao_id)
    assert _vista_da_autora(fabrica, cenario, status='rejeitada')[1] == ['rejeitada']
    assert _vista_da_autora(fabrica, cenario, status='aguardando_decisao')[1] == []


def test_nova_rodada_nao_comunicada_tambem_fica_oculta(fabrica, cenario):
    _decidir(fabrica, cenario, 'nova_rodada')
    assert _vista_da_autora(fabrica, cenario)[0] == 'aguardando_decisao'


def test_rodada_seguinte_aberta_sem_decisao_mostra_a_situacao_real(fabrica, cenario):
    _decidir(fabrica, cenario, 'nova_rodada')
    aberta = fabrica.cliente(cenario['chair']).post(f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={})
    assert aberta.status_code == 201, aberta.get_json()

    assert _vista_da_autora(fabrica, cenario) == ('em_avaliacao', ['em_avaliacao'])


def test_confirmar_de_novo_nao_revela_a_decisao(fabrica, cenario):
    _decidir(fabrica, cenario, 'rejeitada')
    resposta = fabrica.cliente(cenario['autora']).post(f"/api/submissoes/{cenario['submissao_id']}/confirmar")
    assert resposta.get_json()['situacao'] == 'aguardando_decisao'


def test_administrador_como_chair_ve_a_situacao_real(fabrica, cenario):
    _decidir(fabrica, cenario, 'rejeitada')
    admin = fabrica.usuario('Admin', administrador=True)
    resposta = fabrica.cliente(admin).get(f"/api/eventos/{cenario['evento'].id}/submissoes")
    assert [item['situacao'] for item in resposta.get_json()] == ['rejeitada']


def test_retirada_com_decisao_nao_comunicada_depois_aparece_como_retirada(fabrica, cenario):
    # Retirar com decisão pendente é bloqueado; mas a autora retira antes e o
    # chair ainda registra uma decisão (nova_rodada não muda a situação gravada).
    retirada = fabrica.cliente(cenario['autora']).post(f"/api/submissoes/{cenario['submissao_id']}/retirar")
    assert retirada.status_code == 200
    _decidir(fabrica, cenario, 'nova_rodada')

    assert _vista_da_autora(fabrica, cenario) == ('retirada', ['retirada'])


def test_chair_que_tambem_e_autor_ve_a_situacao_real(fabrica):
    chair = fabrica.usuario('Chair autora')
    evento = fabrica.evento(chair=chair)
    cenario = {'autora': chair, 'chair': chair, 'evento': evento,
               'submissao_id': fabrica.submissao_confirmada(chair, fabrica.chamada(evento))}
    _decidir(fabrica, cenario, 'rejeitada')

    assert _vista_da_autora(fabrica, cenario) == ('rejeitada', ['rejeitada'])


def test_vale_a_decisao_da_rodada_mais_recente(fabrica, cenario):
    # Rodada 1: nova_rodada, comunicada ao abrir a 2. Rodada 2: aceita, pendente.
    _decidir(fabrica, cenario, 'nova_rodada')
    assert fabrica.cliente(cenario['chair']).post(
        f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={}).status_code == 201
    _decidir(fabrica, cenario, 'aceita')

    assert _vista_da_autora(fabrica, cenario) == ('aguardando_decisao', ['aguardando_decisao'])
