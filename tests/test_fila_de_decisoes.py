"""A10 — filas de decisões e de atribuições do evento."""
import pytest


@pytest.fixture
def base(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, maximo_de_rodadas=2)
    return {'chair': chair, 'evento': evento, 'chamada': fabrica.chamada(evento)}


def _submissao(fabrica, base):
    return fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])


def _linha(fabrica, base, submissao_id):
    linhas = fabrica.cliente(base['chair']).get(f"/api/eventos/{base['evento'].id}/decisoes").get_json()
    return next((l for l in linhas if l['submissaoId'] == submissao_id), None)


def _com_avaliador(fabrica, base, submissao_id, aceitar=True, parecer=False):
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    if aceitar:
        fabrica.aceitar(avaliador, atribuicao_id)
    if parecer:
        fabrica.submeter_parecer(avaliador, atribuicao_id)
    return atribuicao_id


def test_retirada_sai_das_duas_filas(fabrica, base):
    fica = _submissao(fabrica, base)
    autora = fabrica.usuario('Autora que retira')
    sai = fabrica.submissao_confirmada(autora, base['chamada'])
    _com_avaliador(fabrica, base, sai)
    assert fabrica.cliente(autora).post(f'/api/submissoes/{sai}/retirar').status_code == 200

    chair = fabrica.cliente(base['chair'])
    decisoes = chair.get(f"/api/eventos/{base['evento'].id}/decisoes").get_json()
    atribuicoes = chair.get(f"/api/eventos/{base['evento'].id}/atribuicoes").get_json()

    assert [l['submissaoId'] for l in decisoes] == [fica]
    assert [l['submissaoId'] for l in atribuicoes] == [fica]


def test_sem_atribuicao_nao_esta_pronta_para_encerrar(fabrica, base):
    linha = _linha(fabrica, base, _submissao(fabrica, base))
    assert (linha['pareceresEsperados'], linha['pareceresRecebidos']) == (0, 0)
    assert linha['estagio'] == 'em_avaliacao'


def test_convidado_conta_como_parecer_esperado(fabrica, base):
    submissao_id = _submissao(fabrica, base)
    _com_avaliador(fabrica, base, submissao_id, aceitar=False)

    linha = _linha(fabrica, base, submissao_id)

    assert (linha['pareceresEsperados'], linha['pareceresRecebidos']) == (1, 0)
    assert linha['estagio'] == 'em_avaliacao'


def test_convidado_e_aceito_com_parecer_nao_esta_pronta(fabrica, base):
    submissao_id = _submissao(fabrica, base)
    _com_avaliador(fabrica, base, submissao_id, parecer=True)
    _com_avaliador(fabrica, base, submissao_id, aceitar=False)

    linha = _linha(fabrica, base, submissao_id)

    assert (linha['pareceresEsperados'], linha['pareceresRecebidos']) == (2, 1)
    assert linha['estagio'] == 'em_avaliacao'


def test_todos_os_pareceres_recebidos_esta_pronta(fabrica, base):
    submissao_id = _submissao(fabrica, base)
    _com_avaliador(fabrica, base, submissao_id, parecer=True)

    linha = _linha(fabrica, base, submissao_id)

    assert (linha['pareceresEsperados'], linha['pareceresRecebidos']) == (1, 1)
    assert linha['estagio'] == 'pronta_para_encerrar'


def test_recusado_nao_conta_como_esperado(fabrica, base):
    submissao_id = _submissao(fabrica, base)
    _com_avaliador(fabrica, base, submissao_id, parecer=True)
    avaliador = fabrica.usuario('Recusa')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    assert fabrica.cliente(avaliador).post(f'/api/atribuicoes/{atribuicao_id}/recusar', json={}).status_code == 200

    linha = _linha(fabrica, base, submissao_id)
    assert (linha['pareceresEsperados'], linha['pareceresRecebidos'], linha['estagio']) == (1, 1, 'pronta_para_encerrar')


def test_rodada_nova_com_avaliador_preservado_nao_aparece_pronta(fabrica, base):
    # O caso do E2E: "0/0 pareceres — Pronta para encerrar" na rodada 2.
    submissao_id = _submissao(fabrica, base)
    atribuicao_id = _com_avaliador(fabrica, base, submissao_id, parecer=True)
    fabrica.encerrar_e_decidir(base['chair'], submissao_id, 'nova_rodada')
    aberta = fabrica.cliente(base['chair']).post(
        f'/api/submissoes/{submissao_id}/rodadas', json={'avaliadoresPreservados': [atribuicao_id]})
    assert aberta.status_code == 201

    linha = _linha(fabrica, base, submissao_id)
    assert (linha['numero'], linha['pareceresEsperados'], linha['pareceresRecebidos']) == (2, 1, 0)
    assert linha['estagio'] == 'em_avaliacao'
    # /rodadas (visão do chair) usa a mesma contagem.
    rodadas = fabrica.cliente(base['chair']).get(f'/api/submissoes/{submissao_id}/rodadas').get_json()
    assert (rodadas[-1]['pareceresEsperados'], rodadas[-1]['pareceresRecebidos']) == (1, 0)


def test_versao_corrigida_validada_sai_de_aguardando_versao_corrigida(fabrica, base):
    autora = fabrica.usuario('Autora')
    submissao_id = fabrica.submissao_confirmada(autora, base['chamada'])
    fabrica.encerrar_e_decidir(base['chair'], submissao_id, 'aceita_com_correcoes', comunicar=True)
    assert _linha(fabrica, base, submissao_id)['estagio'] == 'aguardando_versao_corrigida'

    versao = fabrica.enviar_versao(fabrica.cliente(autora), submissao_id, nome='corrigida.pdf')
    enviada = fabrica.cliente(autora).post(f'/api/submissoes/{submissao_id}/versao-corrigida', json={
        'versaoId': int(versao['id']), 'descricaoDasAlteracoes': 'Corrigi.'})
    assert enviada.status_code == 200, enviada.get_json()
    assert _linha(fabrica, base, submissao_id)['estagio'] == 'aguardando_versao_corrigida'

    validada = fabrica.cliente(base['chair']).post(f'/api/submissoes/{submissao_id}/versao-corrigida/validar')
    assert validada.status_code == 200
    assert _linha(fabrica, base, submissao_id)['estagio'] == 'comunicada'


def test_parecer_em_rascunho_nao_conta_como_recebido(fabrica, base):
    submissao_id = _submissao(fabrica, base)
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    rascunho = fabrica.cliente(avaliador).put(f'/api/atribuicoes/{atribuicao_id}/parecer', json={'recomendacao': 'aceitar'})
    assert rascunho.status_code == 200

    linha = _linha(fabrica, base, submissao_id)
    assert (linha['pareceresEsperados'], linha['pareceresRecebidos'], linha['estagio']) == (1, 0, 'em_avaliacao')
