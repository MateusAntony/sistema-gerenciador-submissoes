"""A14 — GET /eventos/<id>/painel e GET /eventos/<id>/pendencias, chair/admin
do evento; 401 sem sessão, 403 sem o papel, 404 evento inexistente."""
from datetime import datetime, timedelta

import pytest

from app.extensions import db
from app.models.atribuicao import Atribuicao
from app.models.execucao_fase import ExecucaoFase
from app.models.fase import DefinicaoFase
from app.models.rebuttal import Rebuttal
from app.models.rodada import Rodada


@pytest.fixture
def base(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    return {'chair': chair, 'evento': evento, 'chamada': chamada}


def _painel(fabrica, base, consulta=''):
    return fabrica.cliente(base['chair']).get(f"/api/eventos/{base['evento'].id}/painel{consulta}")


def _pendencias(fabrica, base):
    return fabrica.cliente(base['chair']).get(f"/api/eventos/{base['evento'].id}/pendencias")


# --- Guarda (401/403/404), nas duas rotas ---

@pytest.mark.parametrize('rota', ['painel', 'pendencias'])
def test_sem_sessao_401(fabrica, base, rota):
    resposta = fabrica.cliente().get(f"/api/eventos/{base['evento'].id}/{rota}")
    assert resposta.status_code == 401
    assert resposta.get_json()['codigo'] == 'nao_autenticado'


@pytest.mark.parametrize('rota', ['painel', 'pendencias'])
def test_evento_inexistente_404(fabrica, base, rota):
    resposta = fabrica.cliente(base['chair']).get(f'/api/eventos/999999/{rota}')
    assert resposta.status_code == 404
    assert resposta.get_json()['codigo'] == 'evento_inexistente'


@pytest.mark.parametrize('rota', ['painel', 'pendencias'])
def test_sem_papel_403(fabrica, base, rota):
    intrusa = fabrica.usuario('Sem papel')
    resposta = fabrica.cliente(intrusa).get(f"/api/eventos/{base['evento'].id}/{rota}")
    assert resposta.status_code == 403
    assert resposta.get_json()['codigo'] == 'sem_permissao'


@pytest.mark.parametrize('rota', ['painel', 'pendencias'])
def test_admin_sem_papel_passa(fabrica, base, rota):
    admin = fabrica.usuario('Admin', administrador=True)
    resposta = fabrica.cliente(admin).get(f"/api/eventos/{base['evento'].id}/{rota}")
    assert resposta.status_code == 200


# --- Painel ---

def test_painel_total_exclui_rascunho_mas_inclui_retirada(fabrica, base):
    autora = fabrica.usuario('Autora')
    fabrica.submissao_confirmada(autora, base['chamada'])
    autora_2 = fabrica.usuario('Autora 2')
    retirada_id = fabrica.submissao_confirmada(autora_2, base['chamada'])
    assert fabrica.cliente(autora_2).post(f'/api/submissoes/{retirada_id}/retirar').status_code == 200

    # Um rascunho (nunca confirmado) não deve ser contado.
    fabrica.cliente(autora).post(f"/api/chamadas/{base['chamada'].id}/submissoes", json={})

    resposta = _painel(fabrica, base)
    corpo = resposta.get_json()
    assert resposta.status_code == 200
    assert 'rascunho' not in [item['situacao'] for item in corpo['porSituacao']]
    soma = sum(item['total'] for item in corpo['porSituacao'])
    assert soma == corpo['totalDeSubmissoes']
    assert corpo['totalDeSubmissoes'] >= 2


def test_painel_por_rodada_soma_o_total(fabrica, base):
    autora = fabrica.usuario('Autora')
    fabrica.submissao_confirmada(autora, base['chamada'])

    corpo = _painel(fabrica, base).get_json()
    soma = sum(item['total'] for item in corpo['porRodada'])
    assert soma == corpo['totalDeSubmissoes']
    assert corpo['porRodada'] == sorted(corpo['porRodada'], key=lambda item: item['numero'])


def test_painel_chamada_aberta_com_rascunhos(fabrica, base):
    autora = fabrica.usuario('Autora')
    fabrica.cliente(autora).post(f"/api/chamadas/{base['chamada'].id}/submissoes", json={})

    corpo = _painel(fabrica, base).get_json()
    assert corpo['chamadaAberta']['chamadaId'] == base['chamada'].id
    assert corpo['chamadaAberta']['rascunhos'] == 1


def test_painel_chamada_com_prazo_vencido_nao_e_aberta(fabrica, base):
    base['chamada'].data_limite = '2020-01-01T00:00'
    db.session.commit()

    corpo = _painel(fabrica, base).get_json()
    assert 'chamadaAberta' not in corpo


def test_painel_evento_sem_chamada(fabrica):
    chair = fabrica.usuario('Chair sem chamada')
    evento = fabrica.evento(chair=chair)
    corpo = fabrica.cliente(chair).get(f'/api/eventos/{evento.id}/painel').get_json()
    assert corpo['semChamada'] is True
    assert corpo['totalDeSubmissoes'] == 0
    assert corpo['porSituacao'] == []
    assert 'chamadaAberta' not in corpo


def test_painel_consolida_sub_evento_por_eventoPaiId(fabrica, base):
    filho = fabrica.evento(evento_pai_id=base['evento'].id, identificador_pagina='sub-a14')
    chamada_filho = fabrica.chamada(filho)
    fabrica.submissao_confirmada(fabrica.usuario('Autora do filho'), chamada_filho)
    fabrica.submissao_confirmada(fabrica.usuario('Autora do pai'), base['chamada'])

    consolidado = _painel(fabrica, base).get_json()
    assert consolidado['totalDeSubmissoes'] == 2
    assert consolidado['subEventos'] == [{'id': filho.id, 'titulo': filho.titulo}]

    do_filho = _painel(fabrica, base, f'?evento={filho.id}').get_json()
    assert do_filho['eventoId'] == filho.id
    assert do_filho['totalDeSubmissoes'] == 1


def test_painel_evento_que_nao_e_descendente_404(fabrica, base):
    outro = fabrica.evento(chair=base['chair'])
    resposta = _painel(fabrica, base, f'?evento={outro.id}')
    assert resposta.status_code == 404
    assert resposta.get_json()['codigo'] == 'evento_inexistente'


def test_painel_referencia_em_traz_o_fuso(fabrica, base):
    corpo = _painel(fabrica, base).get_json()
    assert datetime.fromisoformat(corpo['referenciaEm']).tzinfo is not None


def test_painel_com_ciclo_de_eventoPaiId_nao_trava(fabrica, base):
    # PATCH /eventos/<id> não valida eventoPaiId (achado do Lince): um ciclo
    # não pode derrubar o painel com RecursionError.
    outro = fabrica.evento(evento_pai_id=base['evento'].id, identificador_pagina='ciclo-a14')
    base['evento'].evento_pai_id = outro.id
    db.session.commit()

    resposta = _painel(fabrica, base)
    assert resposta.status_code == 200
    ids_dos_subeventos = [item['id'] for item in resposta.get_json()['subEventos']]
    assert ids_dos_subeventos == [outro.id]


# --- Pendências ---

def test_pendencias_evento_sem_nada_e_vazia(fabrica, base):
    resposta = _pendencias(fabrica, base)
    assert resposta.status_code == 200
    assert resposta.get_json() == []


def test_convite_sem_resposta_no_prazo(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)

    pendencias = _pendencias(fabrica, base).get_json()
    assert len(pendencias) == 1
    assert pendencias[0]['tipo'] == 'convite_sem_resposta'
    assert 'diasVencidos' not in pendencias[0]
    assert pendencias[0]['acao'] == {'tipo': 'enviar_lembrete', 'atribuicaoId': pendencias[0]['acao']['atribuicaoId']}


def test_convite_vencido_ha_3_dias(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    atribuicao = Atribuicao.query.get(atribuicao_id)
    atribuicao.prazo_resposta = datetime.utcnow() - timedelta(days=3)
    db.session.commit()

    pendencia = _pendencias(fabrica, base).get_json()[0]
    assert pendencia['tipo'] == 'convite_vencido'
    assert pendencia['diasVencidos'] == 3
    assert pendencia['acao']['tipo'] == 'substituir_avaliador'


def test_parecer_em_atraso_com_prazo_vencido(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    rodada = fabrica.rodada_atual(submissao_id)
    rodada.data_limite_parecer = datetime.utcnow() - timedelta(days=1)
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    assert [p['tipo'] for p in pendencias] == ['parecer_em_atraso']
    assert pendencias[0]['diasVencidos'] == 1


def test_parecer_entregue_nao_gera_pendencia(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    fabrica.submeter_parecer(avaliador, atribuicao_id)
    rodada = fabrica.rodada_atual(submissao_id)
    rodada.data_limite_parecer = datetime.utcnow() - timedelta(days=1)
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    assert 'parecer_em_atraso' not in [p['tipo'] for p in pendencias]


def test_rebuttal_vencendo_dentro_da_janela(fabrica, base):
    base['evento'].rebuttal_habilitado = True
    base['evento'].prazo_rebuttal_dias = 1
    base['evento'].maximo_de_rodadas = 2
    db.session.commit()

    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    fabrica.submeter_parecer(avaliador, atribuicao_id)

    rodada_id = fabrica.rodada_atual(submissao_id).id
    encerrada = fabrica.cliente(base['chair']).post(f'/api/rodadas/{rodada_id}/encerrar', json={'confirmarPendentes': True})
    assert encerrada.status_code == 200
    assert Rebuttal.query.filter_by(rodada_id=rodada_id).first() is not None

    pendencias = _pendencias(fabrica, base).get_json()
    tipos = [p['tipo'] for p in pendencias]
    assert 'rebuttal_vencendo' in tipos
    pendencia = next(p for p in pendencias if p['tipo'] == 'rebuttal_vencendo')
    assert 'diasVencidos' not in pendencia
    assert pendencia['acao'] == {'tipo': 'acompanhar_rebuttal', 'rodadaId': rodada_id}


def test_rebuttal_alem_da_janela_nao_aparece(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    rodada = fabrica.rodada_atual(submissao_id)
    db.session.add(Rebuttal(rodada_id=rodada.id, situacao='aguardando', prazo=datetime.utcnow() + timedelta(days=10)))
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    assert 'rebuttal_vencendo' not in [p['tipo'] for p in pendencias]


def test_fase_vencida_e_nao_concluida(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    responsavel = fabrica.usuario('Responsável')
    fase = DefinicaoFase(evento_id=base['evento'].id, nome='Triagem', ordem=1, momento='triagem')
    db.session.add(fase)
    db.session.flush()
    execucao = ExecucaoFase(
        submissao_id=submissao_id, fase_id=fase.id, responsavel_id=responsavel.id,
        status='pendente', prazo=datetime.utcnow() - timedelta(days=2),
    )
    db.session.add(execucao)
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    fase_vencida = next(p for p in pendencias if p['tipo'] == 'fase_vencida')
    assert fase_vencida['diasVencidos'] == 2
    assert fase_vencida['pessoaNome'] == responsavel.nome
    assert fase_vencida['acao'] == {'tipo': 'reatribuir_fase', 'execucaoFaseId': execucao.id}


def test_fase_concluida_com_prazo_passado_nao_e_pendencia(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    fase = DefinicaoFase(evento_id=base['evento'].id, nome='Triagem', ordem=1, momento='triagem')
    db.session.add(fase)
    db.session.flush()
    execucao = ExecucaoFase(
        submissao_id=submissao_id, fase_id=fase.id, status='concluida',
        prazo=datetime.utcnow() - timedelta(days=2),
    )
    db.session.add(execucao)
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    assert 'fase_vencida' not in [p['tipo'] for p in pendencias]


def test_abaixo_da_meta_sem_avaliador_convidado(fabrica, base):
    base['evento'].avaliadores_por_submissao = 1
    db.session.commit()
    fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])

    pendencias = _pendencias(fabrica, base).get_json()
    assert [p['tipo'] for p in pendencias] == ['abaixo_da_meta']
    assert pendencias[0]['acao'] == {'tipo': 'convidar_avaliadores'}


def test_meta_atingida_nao_gera_pendencia(fabrica, base):
    base['evento'].avaliadores_por_submissao = 1
    db.session.commit()
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    avaliador = fabrica.usuario('Avaliador')
    fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, avaliador)

    pendencias = _pendencias(fabrica, base).get_json()
    assert 'abaixo_da_meta' not in [p['tipo'] for p in pendencias]


def test_submissao_retirada_nao_gera_pendencia(fabrica, base):
    base['evento'].avaliadores_por_submissao = 5
    db.session.commit()
    autora = fabrica.usuario('Autora que retira')
    submissao_id = fabrica.submissao_confirmada(autora, base['chamada'])
    assert fabrica.cliente(autora).post(f'/api/submissoes/{submissao_id}/retirar').status_code == 200

    pendencias = _pendencias(fabrica, base).get_json()
    assert pendencias == []


def test_ordena_por_dias_vencidos_decrescente(fabrica, base):
    base['evento'].avaliadores_por_submissao = 5
    db.session.commit()
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])

    atribuicao_id_1 = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, fabrica.usuario('A1'))
    Atribuicao.query.get(atribuicao_id_1).prazo_resposta = datetime.utcnow() - timedelta(days=1)
    atribuicao_id_2 = fabrica.convidar(base['chair'], fabrica.rodada_atual(submissao_id).id, fabrica.usuario('A2'))
    Atribuicao.query.get(atribuicao_id_2).prazo_resposta = datetime.utcnow() - timedelta(days=5)
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    dias = [p.get('diasVencidos', -1) for p in pendencias]
    assert dias == sorted(dias, reverse=True)
    assert dias[0] == 5


def test_fase_vencida_sem_responsavel_e_vencida(fabrica, base):
    """Achado E2E (branch api/integracao, sgs_e2e2): execução de fase
    'pendente' sem responsável e com prazo vencido não aparecia na fila."""
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    fase = DefinicaoFase(evento_id=base['evento'].id, nome='Producao', ordem=1, momento='producao')
    db.session.add(fase)
    db.session.flush()
    execucao = ExecucaoFase(
        submissao_id=submissao_id, fase_id=fase.id, responsavel_id=None,
        status='pendente', prazo=datetime.utcnow() - timedelta(days=1),
    )
    db.session.add(execucao)
    db.session.commit()

    pendencia = next(p for p in _pendencias(fabrica, base).get_json() if p['tipo'] == 'fase_vencida')
    assert pendencia['diasVencidos'] == 1
    assert 'pessoaNome' not in pendencia
    assert pendencia['acao'] == {'tipo': 'reatribuir_fase', 'execucaoFaseId': execucao.id}


def test_fase_sem_responsavel_ainda_no_prazo_tambem_e_pendencia(fabrica, base):
    """Ninguém está de fato trabalhando na fase sem um responsável — o chair
    precisa saber mesmo antes do prazo vencer, não só depois."""
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    fase = DefinicaoFase(evento_id=base['evento'].id, nome='Producao', ordem=1, momento='producao')
    db.session.add(fase)
    db.session.flush()
    execucao = ExecucaoFase(
        submissao_id=submissao_id, fase_id=fase.id, responsavel_id=None,
        status='pendente', prazo=datetime.utcnow() + timedelta(days=5),
    )
    db.session.add(execucao)
    db.session.commit()

    pendencia = next(p for p in _pendencias(fabrica, base).get_json() if p['tipo'] == 'fase_vencida')
    assert 'diasVencidos' not in pendencia
    assert 'pessoaNome' not in pendencia
    assert pendencia['prazo'] is not None


def test_fase_com_responsavel_e_no_prazo_nao_e_pendencia(fabrica, base):
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), base['chamada'])
    responsavel = fabrica.usuario('Responsável')
    fase = DefinicaoFase(evento_id=base['evento'].id, nome='Producao', ordem=1, momento='producao')
    db.session.add(fase)
    db.session.flush()
    execucao = ExecucaoFase(
        submissao_id=submissao_id, fase_id=fase.id, responsavel_id=responsavel.id,
        status='pendente', prazo=datetime.utcnow() + timedelta(days=5),
    )
    db.session.add(execucao)
    db.session.commit()

    pendencias = _pendencias(fabrica, base).get_json()
    assert 'fase_vencida' not in [p['tipo'] for p in pendencias]
