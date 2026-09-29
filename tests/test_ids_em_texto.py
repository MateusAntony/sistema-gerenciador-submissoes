"""AD-030: o front manda todos os ids como string. Todo id do corpo aceita
inteiro ou texto só com dígitos ASCII ('5', ' 5 '); o resto é inválido."""
import io

import pytest

from app.ids import id_numerico
from app.models.atribuicao import Atribuicao
from app.models.evento import Chamada, Submissao
from app.models.execucao_fase import ExecucaoFase
from app.models.fase import DefinicaoFase
from app.models.rebuttal import Rebuttal
from app.models.versao_corrigida import VersaoCorrigida

FASE = {'nome': 'Triagem', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': False, 'permiteDevolucao': False, 'ativo': True}


@pytest.mark.parametrize('valor, esperado', [
    (5, 5), ('5', 5), (' 5 ', 5), ('007', 7),
    ('', None), (' ', None), ('abc', None), ('5a', None), ('-5', None), ('+5', None), ('5.0', None),
    ('²', None), ('١', None), ('５', None), (True, None), (5.0, None), ([5], None), (None, None),
    (str(2 ** 63), None), (2 ** 63, None), (-1, None), (0, None),
])
def test_id_numerico(valor, esperado):
    assert id_numerico(valor) == esperado


@pytest.fixture
def base(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, maximo_de_rodadas=2)
    return {'chair': chair, 'evento': evento, 'chamada': fabrica.chamada(evento), 'cliente': fabrica.cliente(chair)}


# --- fases e execuções ---

def test_criar_fase_com_responsavel_em_texto(fabrica, base):
    rita = fabrica.usuario('Rita')
    resposta = base['cliente'].post(f"/api/eventos/{base['evento'].id}/fases",
                                    json={**FASE, 'responsavelPadraoId': str(rita.id)})
    assert resposta.status_code == 201 and resposta.get_json()['responsavelPadraoId'] == rita.id


def test_patch_fase_com_responsavel_em_texto(fabrica, base):
    fase_id = base['cliente'].post(f"/api/eventos/{base['evento'].id}/fases", json=FASE).get_json()['id']
    fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    rita = fabrica.usuario('Rita')

    resposta = base['cliente'].patch(f'/api/fases/{fase_id}', json={'responsavelPadraoId': str(rita.id)})

    assert resposta.status_code == 200 and resposta.get_json()['responsavelPadraoId'] == rita.id
    assert ExecucaoFase.query.filter_by(fase_id=fase_id).one().responsavel_id == rita.id


def test_trocar_responsavel_da_execucao_em_texto(fabrica, base):
    fase_id = base['cliente'].post(f"/api/eventos/{base['evento'].id}/fases", json=FASE).get_json()['id']
    fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    execucao = ExecucaoFase.query.filter_by(fase_id=fase_id).one()
    novo = fabrica.usuario('Novo')

    resposta = base['cliente'].patch(f'/api/execucoes-fase/{execucao.id}', json={'responsavelId': f' {novo.id} '})

    assert resposta.status_code == 200 and resposta.get_json()['responsavelId'] == novo.id


def test_concluir_execucao_com_arquivo_em_texto(fabrica, base):
    rita = fabrica.usuario('Rita')
    base['cliente'].post(f"/api/eventos/{base['evento'].id}/fases",
                         json={**FASE, 'exigeArquivo': True, 'responsavelPadraoId': rita.id})
    fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    execucao = ExecucaoFase.query.one()

    resposta = fabrica.cliente(rita).post(f'/api/execucoes-fase/{execucao.id}/concluir', json={'arquivoResultadoId': '42'})

    assert resposta.status_code == 200 and resposta.get_json()['arquivoResultadoId'] == 42


def test_arquivo_de_resultado_invalido_e_422(fabrica, base):
    rita = fabrica.usuario('Rita')
    base['cliente'].post(f"/api/eventos/{base['evento'].id}/fases",
                         json={**FASE, 'exigeArquivo': True, 'responsavelPadraoId': rita.id})
    fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    execucao = ExecucaoFase.query.one()

    resposta = fabrica.cliente(rita).post(f'/api/execucoes-fase/{execucao.id}/concluir', json={'arquivoResultadoId': 'abc'})

    assert resposta.status_code == 422 and 'arquivoResultadoId' in resposta.get_json()['campos']


# --- atribuições e rodadas ---

def _convidar(base, rodada_id, avaliador_id, nome='Av', email='av@teste.br'):
    return base['cliente'].post(f'/api/rodadas/{rodada_id}/atribuicoes',
                                json=[{'avaliadorId': avaliador_id, 'nome': nome, 'email': email}])


def test_convidar_avaliador_com_id_em_texto(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')

    resposta = _convidar(base, fabrica.rodada_atual(submissao_id).id, str(avaliador.id), avaliador.nome, avaliador.email)

    [resultado] = resposta.get_json()
    assert resultado['sucesso'] and resultado['atribuicao']['avaliadorId'] == avaliador.id


def test_autora_com_id_em_texto_continua_impedida(fabrica, base):
    # Sem normalizar, '5' != 5 e o impedimento de autoria era contornado.
    autora = fabrica.usuario('Autora')
    submissao_id = fabrica.submissao_confirmada(autora, base['chamada'])

    [resultado] = _convidar(base, fabrica.rodada_atual(submissao_id).id, str(autora.id),
                            autora.nome, autora.email).get_json()

    assert resultado['sucesso'] is False and resultado['codigo'] == 'autor'
    assert Atribuicao.query.count() == 0


def test_avaliador_id_invalido_falha_o_item(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    [resultado] = _convidar(base, fabrica.rodada_atual(submissao_id).id, 'abc').get_json()
    assert resultado['sucesso'] is False and resultado['codigo'] == 'avaliador_invalido'


def test_nova_rodada_preserva_avaliador_com_id_em_texto(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.encerrar_e_decidir(base['chair'], submissao_id, 'nova_rodada')

    resposta = base['cliente'].post(f'/api/submissoes/{submissao_id}/rodadas',
                                    json={'avaliadoresPreservados': [str(atribuicao_id)]})

    assert resposta.status_code == 201
    rodada_2 = fabrica.rodada_atual(submissao_id)
    assert [a.avaliador_id for a in Atribuicao.query.filter_by(rodada_id=rodada_2.id)] == [avaliador.id]


def test_comunicar_em_lote_com_ids_em_texto(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    decisao_id = fabrica.encerrar_e_decidir(base['chair'], submissao_id, 'rejeitada')

    resposta = base['cliente'].post(f"/api/eventos/{base['evento'].id}/decisoes/comunicar-lote",
                                    json={'decisaoIds': [str(decisao_id), 'abc']})

    assert [r['sucesso'] for r in resposta.get_json()] == [True, False]
    assert Submissao.query.get(submissao_id).situacao == 'rejeitada'


# --- parecer ---

def test_notas_do_parecer_com_criterio_em_texto(fabrica, base):
    criterio = base['cliente'].post(f"/api/eventos/{base['evento'].id}/criterios", json={
        'titulo': 'Mérito', 'notaMinima': 0, 'notaMaxima': 10, 'peso': 1}).get_json()
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    cliente = fabrica.cliente(avaliador)

    salvo = cliente.put(f'/api/atribuicoes/{atribuicao_id}/parecer', json={
        'recomendacao': 'aceitar', 'notas': [{'criterioId': str(criterio['id']), 'nota': 8}]})
    submetido = cliente.post(f'/api/atribuicoes/{atribuicao_id}/parecer/submeter')

    assert salvo.get_json()['notas'] == [{'criterioId': criterio['id'], 'nota': 8}]
    assert submetido.status_code == 200, submetido.get_json()
    assert submetido.get_json()['pontuacaoPonderada'] == 8


# --- submissão, versão corrigida e rebuttal ---

def test_criar_e_editar_submissao_com_trilha_em_texto(fabrica, base):
    trilha = base['cliente'].post(f"/api/eventos/{base['evento'].id}/trilhas", json={'nome': 'T1'}).get_json()
    outra = base['cliente'].post(f"/api/eventos/{base['evento'].id}/trilhas", json={'nome': 'T2'}).get_json()
    autora = fabrica.cliente(fabrica.usuario('Autora'))

    criada = autora.post(f"/api/chamadas/{base['chamada'].id}/submissoes", json={'trilhaId': str(trilha['id'])})
    assert criada.status_code == 201, criada.get_json()
    assert criada.get_json()['trilhaId'] == str(trilha['id'])

    editada = autora.patch(f"/api/submissoes/{criada.get_json()['id']}", json={'trilhaId': str(outra['id'])})
    assert editada.status_code == 200 and editada.get_json()['trilhaId'] == str(outra['id'])


def test_trilha_invalida_e_422(fabrica, base):
    base['cliente'].post(f"/api/eventos/{base['evento'].id}/trilhas", json={'nome': 'T1'})
    autora = fabrica.cliente(fabrica.usuario('Autora'))
    resposta = autora.post(f"/api/chamadas/{base['chamada'].id}/submissoes", json={'trilhaId': 'abc'})
    assert resposta.status_code == 422


def test_criar_chamada_com_trilha_em_texto(base):
    trilha = base['cliente'].post(f"/api/eventos/{base['evento'].id}/trilhas", json={'nome': 'T1'}).get_json()
    resposta = base['cliente'].post(f"/api/eventos/{base['evento'].id}/chamadas", json={
        'titulo': 'C', 'dataAbertura': '2026-01-01T00:00', 'dataLimite': '2099-01-01T00:00', 'trilhaId': str(trilha['id'])})
    assert resposta.status_code == 201 and resposta.get_json()['trilhaId'] == trilha['id']
    chamada_id = resposta.get_json()['id']
    editada = base['cliente'].patch(f'/api/chamadas/{chamada_id}', json={'trilhaId': f" {trilha['id']} "})
    assert editada.status_code == 200 and Chamada.query.get(chamada_id).trilha_id == trilha['id']


def test_chamada_com_trilha_invalida_e_422(base):
    resposta = base['cliente'].post(f"/api/eventos/{base['evento'].id}/chamadas", json={
        'titulo': 'C', 'dataAbertura': '2026-01-01T00:00', 'dataLimite': '2099-01-01T00:00', 'trilhaId': 'abc'})
    assert resposta.status_code == 422 and 'trilhaId' in resposta.get_json()['campos']


def test_versao_corrigida_com_versao_em_texto(fabrica, base):
    autora = fabrica.usuario('Autora')
    submissao_id = fabrica.submissao_confirmada(autora, base['chamada'])
    fabrica.encerrar_e_decidir(base['chair'], submissao_id, 'aceita_com_correcoes', comunicar=True)
    cliente = fabrica.cliente(autora)
    versao = fabrica.enviar_versao(cliente, submissao_id, nome='corrigida.pdf')

    resposta = cliente.post(f'/api/submissoes/{submissao_id}/versao-corrigida',
                            json={'versaoId': versao['id'], 'descricaoDasAlteracoes': 'C.'})

    assert resposta.status_code == 200 and resposta.get_json()['versaoId'] == int(versao['id'])
    assert VersaoCorrigida.query.one().versao_id == int(versao['id'])


def test_rebuttal_com_versao_em_texto(fabrica):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, rebuttal_habilitado=True, prazo_rebuttal_dias=3, maximo_de_rodadas=2)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    rodada_id = fabrica.rodada_atual(submissao_id).id
    fabrica.cliente(chair).post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    cliente = fabrica.cliente(autora)
    versao = cliente.post(f'/api/submissoes/{submissao_id}/versoes',
                          data={'arquivo': (io.BytesIO(b'%PDF'), 'v2.pdf'), 'nomeArquivo': 'v2.pdf'},
                          content_type='multipart/form-data').get_json()

    salvo = cliente.put(f'/api/rodadas/{rodada_id}/rebuttal', json={'texto': 'R.', 'versaoId': versao['id']})
    enviado = cliente.post(f'/api/rodadas/{rodada_id}/rebuttal/enviar', json={'texto': 'R.', 'versaoId': versao['id']})

    assert salvo.status_code == 200 and enviado.status_code == 200, enviado.get_json()
    assert enviado.get_json()['versaoId'] == int(versao['id'])
    assert Rebuttal.query.one().versao_id == int(versao['id'])


def test_fase_com_id_invalido_continua_422(base):
    resposta = base['cliente'].post(f"/api/eventos/{base['evento'].id}/fases",
                                    json={**FASE, 'responsavelPadraoId': '²'})
    assert resposta.status_code == 422
    assert DefinicaoFase.query.count() == 0


def test_chamada_com_trilha_de_outro_evento_e_422(fabrica, base):
    outro = fabrica.evento(chair=base['chair'])
    trilha_alheia = base['cliente'].post(f'/api/eventos/{outro.id}/trilhas', json={'nome': 'Alheia'}).get_json()
    resposta = base['cliente'].post(f"/api/eventos/{base['evento'].id}/chamadas", json={
        'titulo': 'C', 'dataAbertura': '2026-01-01T00:00', 'dataLimite': '2099-01-01T00:00',
        'trilhaId': str(trilha_alheia['id'])})
    assert resposta.status_code == 422 and 'trilhaId' in resposta.get_json()['campos']
