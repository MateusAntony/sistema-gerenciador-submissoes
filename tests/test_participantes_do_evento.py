"""A4 — GET /api/eventos/<id>/participantes?q= (chair/admin):
[{usuarioId, nome, email, papeis}] entre usuários ativos (não só quem já
participa), para escolher o responsável padrão da fase."""
import pytest

from app.extensions import db
from app.models.evento import ParticipacaoEvento


@pytest.fixture
def cenario(fabrica):
    chair = fabrica.usuario('Carla Chair', email='carla@uefs.br')
    evento = fabrica.evento(chair=chair)
    avaliador = fabrica.usuario('Vitor Avaliador', email='vitor@uefs.br')
    db.session.add(ParticipacaoEvento(evento_id=evento.id, usuario_id=avaliador.id, papel='avaliador'))
    db.session.commit()
    externa = fabrica.usuario('Marta Externa', email='marta@ufba.br')
    inativo = fabrica.usuario('Vitoria Inativa', email='vitoria@uefs.br')
    inativo.ativo = False
    db.session.commit()
    return {'chair': chair, 'evento': evento, 'avaliador': avaliador, 'externa': externa}


def _buscar(fabrica, usuario, evento_id, q=None):
    url = f'/api/eventos/{evento_id}/participantes' + (f'?q={q}' if q is not None else '')
    return fabrica.cliente(usuario).get(url)


def test_lista_usuarios_ativos_com_os_papeis_no_evento(fabrica, cenario):
    resposta = _buscar(fabrica, cenario['chair'], cenario['evento'].id)

    assert resposta.status_code == 200
    itens = {item['nome']: item for item in resposta.get_json()}
    assert set(itens) == {'Carla Chair', 'Vitor Avaliador', 'Marta Externa'}
    assert itens['Carla Chair'] == {'usuarioId': cenario['chair'].id, 'nome': 'Carla Chair',
                                    'email': 'carla@uefs.br', 'papeis': ['chair']}
    assert itens['Vitor Avaliador']['papeis'] == ['avaliador']
    assert itens['Marta Externa']['papeis'] == []


def test_busca_por_nome_ou_email_sem_diferenciar_maiusculas(fabrica, cenario):
    por_nome = _buscar(fabrica, cenario['chair'], cenario['evento'].id, 'vITor').get_json()
    por_email = _buscar(fabrica, cenario['chair'], cenario['evento'].id, 'ufba').get_json()

    assert [i['nome'] for i in por_nome] == ['Vitor Avaliador']
    assert [i['nome'] for i in por_email] == ['Marta Externa']


def test_papeis_sao_do_evento_pedido(fabrica, cenario):
    outro = fabrica.evento(chair=cenario['externa'])
    itens = {i['nome']: i for i in _buscar(fabrica, cenario['chair'], cenario['evento'].id).get_json()}
    assert itens['Marta Externa']['papeis'] == []
    itens_outro = {i['nome']: i for i in _buscar(fabrica, cenario['externa'], outro.id).get_json()}
    assert itens_outro['Marta Externa']['papeis'] == ['chair']
    assert itens_outro['Carla Chair']['papeis'] == []


def test_admin_pode_buscar(fabrica, cenario):
    admin = fabrica.usuario('Admin', administrador=True)
    assert _buscar(fabrica, admin, cenario['evento'].id, 'marta').status_code == 200


def test_sem_sessao_401_sem_papel_403_inexistente_404(fabrica, cenario):
    assert fabrica.cliente().get(f"/api/eventos/{cenario['evento'].id}/participantes").status_code == 401
    assert _buscar(fabrica, cenario['avaliador'], cenario['evento'].id).status_code == 403
    assert _buscar(fabrica, cenario['chair'], 99999).status_code == 404
