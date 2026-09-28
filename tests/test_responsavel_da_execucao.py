"""A5 — responsável padrão da fase preenche execuções pendentes sem
responsável; PATCH /execucoes-fase/<id> troca o responsável (chair/admin)."""
import pytest

from app.extensions import db
from app.models.execucao_fase import ExecucaoFase

FASE = {'nome': 'Triagem', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': False, 'permiteDevolucao': False, 'ativo': True}


@pytest.fixture
def cenario(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    cliente = fabrica.cliente(chair)
    fase = cliente.post(f'/api/eventos/{evento.id}/fases', json=FASE).get_json()
    outra = cliente.post(f'/api/eventos/{evento.id}/fases', json={**FASE, 'nome': 'Revisão', 'ordem': 2,
                                                                  'obrigatoria': False}).get_json()
    submissoes = [fabrica.submissao_confirmada(fabrica.usuario('Autora'), chamada) for _ in range(3)]
    return {'chair': chair, 'evento': evento, 'fase_id': fase['id'], 'outra_id': outra['id'],
            'submissoes': submissoes}


def _execucao(fase_id, submissao_id):
    return ExecucaoFase.query.filter_by(fase_id=fase_id, submissao_id=submissao_id).one()


def test_responsavel_padrao_preenche_execucoes_pendentes_sem_responsavel(fabrica, cenario):
    ja_tinha = fabrica.usuario('Já tinha')
    s1, s2, s3 = cenario['submissoes']
    _execucao(cenario['fase_id'], s2).responsavel_id = ja_tinha.id
    _execucao(cenario['fase_id'], s3).status = 'em_andamento'
    db.session.commit()
    responsavel = fabrica.usuario('Rita Responsável')

    resposta = fabrica.cliente(cenario['chair']).patch(
        f"/api/fases/{cenario['fase_id']}", json={'responsavelPadraoId': responsavel.id})

    assert resposta.status_code == 200
    db.session.expire_all()
    assert _execucao(cenario['fase_id'], s1).responsavel_id == responsavel.id   # pendente sem responsável
    assert _execucao(cenario['fase_id'], s2).responsavel_id == ja_tinha.id      # já tinha responsável
    assert _execucao(cenario['fase_id'], s3).responsavel_id is None             # não está pendente
    assert _execucao(cenario['outra_id'], s1).responsavel_id is None            # outra fase


def test_responsavel_preenchido_ve_a_execucao_na_sua_fila(fabrica, cenario):
    responsavel = fabrica.usuario('Rita')
    fabrica.cliente(cenario['chair']).patch(f"/api/fases/{cenario['fase_id']}", json={'responsavelPadraoId': responsavel.id})

    fila = fabrica.cliente(responsavel).get('/api/me/execucoes-fase').get_json()
    assert sorted(item['submissaoId'] for item in fila) == sorted(cenario['submissoes'])


def test_responsavel_padrao_inexistente_responde_422(fabrica, cenario):
    resposta = fabrica.cliente(cenario['chair']).patch(
        f"/api/fases/{cenario['fase_id']}", json={'responsavelPadraoId': 99999})
    assert resposta.status_code == 422
    assert 'responsavelPadraoId' in resposta.get_json()['campos']


def test_limpar_responsavel_padrao_nao_mexe_nas_execucoes(fabrica, cenario):
    responsavel = fabrica.usuario('Rita')
    cliente = fabrica.cliente(cenario['chair'])
    cliente.patch(f"/api/fases/{cenario['fase_id']}", json={'responsavelPadraoId': responsavel.id})

    resposta = cliente.patch(f"/api/fases/{cenario['fase_id']}", json={'responsavelPadraoId': None})

    assert resposta.status_code == 200 and resposta.get_json()['responsavelPadraoId'] is None
    db.session.expire_all()
    assert _execucao(cenario['fase_id'], cenario['submissoes'][0]).responsavel_id == responsavel.id


# --- PATCH /execucoes-fase/<id> ---

def _trocar(fabrica, usuario, execucao_id, corpo):
    return fabrica.cliente(usuario).patch(f'/api/execucoes-fase/{execucao_id}', json=corpo)


@pytest.mark.parametrize('papel', ['chair', 'admin'])
def test_chair_e_admin_trocam_o_responsavel(fabrica, cenario, papel):
    usuario = cenario['chair'] if papel == 'chair' else fabrica.usuario('Admin', administrador=True)
    execucao = _execucao(cenario['fase_id'], cenario['submissoes'][0])
    novo = fabrica.usuario('Novo responsável')

    resposta = _trocar(fabrica, usuario, execucao.id, {'responsavelId': novo.id})

    assert resposta.status_code == 200
    assert resposta.get_json()['responsavelId'] == novo.id
    assert resposta.get_json()['semResponsavel'] is False
    db.session.expire_all()
    assert ExecucaoFase.query.get(execucao.id).responsavel_id == novo.id


def test_trocar_responsavel_sem_sessao_401_sem_papel_403(fabrica, cenario):
    execucao = _execucao(cenario['fase_id'], cenario['submissoes'][0])
    novo = fabrica.usuario('Novo')
    assert fabrica.cliente().patch(f'/api/execucoes-fase/{execucao.id}', json={'responsavelId': novo.id}).status_code == 401
    assert _trocar(fabrica, novo, execucao.id, {'responsavelId': novo.id}).status_code == 403
    outro_chair = fabrica.usuario('Outro chair')
    fabrica.evento(chair=outro_chair)
    assert _trocar(fabrica, outro_chair, execucao.id, {'responsavelId': novo.id}).status_code == 403
    db.session.expire_all()
    assert ExecucaoFase.query.get(execucao.id).responsavel_id is None


def test_trocar_responsavel_de_execucao_inexistente_404(fabrica, cenario):
    assert _trocar(fabrica, cenario['chair'], 99999, {'responsavelId': cenario['chair'].id}).status_code == 404


@pytest.mark.parametrize('corpo', [{}, {'responsavelId': 99999}, {'responsavelId': 'x'}])
def test_trocar_responsavel_invalido_422(fabrica, cenario, corpo):
    execucao = _execucao(cenario['fase_id'], cenario['submissoes'][0])
    resposta = _trocar(fabrica, cenario['chair'], execucao.id, corpo)
    assert resposta.status_code == 422
    assert 'responsavelId' in resposta.get_json()['campos']


def test_usuario_inativo_nao_pode_ser_responsavel(fabrica, cenario):
    inativo = fabrica.usuario('Inativo')
    inativo.ativo = False
    db.session.commit()
    execucao = _execucao(cenario['fase_id'], cenario['submissoes'][0])
    cliente = fabrica.cliente(cenario['chair'])

    assert cliente.patch(f'/api/execucoes-fase/{execucao.id}', json={'responsavelId': inativo.id}).status_code == 422
    assert cliente.patch(f"/api/fases/{cenario['fase_id']}", json={'responsavelPadraoId': inativo.id}).status_code == 422
