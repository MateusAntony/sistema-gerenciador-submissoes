"""A21: to_dict da execução de fase inclui responsavelNome (ou None sem responsável)."""
from app.models.execucao_fase import ExecucaoFase

FASE = {'nome': 'Triagem', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': False, 'permiteDevolucao': False, 'ativo': True}


def _execucao(fase_id, submissao_id):
    return ExecucaoFase.query.filter_by(fase_id=fase_id, submissao_id=submissao_id).one()


def test_responsavel_nome_e_none_sem_responsavel(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    fase = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/fases', json=FASE).get_json()
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), chamada)

    execucao = _execucao(fase['id'], submissao_id)

    assert execucao.to_dict()['responsavelNome'] is None


def test_responsavel_nome_reflete_o_usuario_responsavel(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    fase = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/fases', json=FASE).get_json()
    submissao_id = fabrica.submissao_confirmada(fabrica.usuario('Autora'), chamada)
    responsavel = fabrica.usuario('Rita Responsável')

    resposta = fabrica.cliente(chair).patch(
        f"/api/fases/{fase['id']}", json={'responsavelPadraoId': responsavel.id})
    assert resposta.status_code == 200

    execucao = _execucao(fase['id'], submissao_id)
    assert execucao.to_dict()['responsavelNome'] == 'Rita Responsável'
