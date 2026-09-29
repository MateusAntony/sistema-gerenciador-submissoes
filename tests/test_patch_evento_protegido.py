"""Revisão do P1, nota c (decisão do maestro): PATCH /eventos/<id> não muda
a situação (só a publicação muda) e só aceita eventoPaiId de evento em que
o usuário é chair/admin, sem ciclo."""
import pytest

from app.extensions import db
from app.models.evento import Evento


@pytest.fixture
def cenario(fabrica):
    chair = fabrica.usuario('Chair')
    return {'chair': chair, 'cliente': fabrica.cliente(chair), 'evento': fabrica.evento(chair=chair)}


def _patch(cenario, evento, corpo):
    return cenario['cliente'].patch(f'/api/eventos/{evento.id}', json=corpo)


def _recarregar(evento):
    db.session.expire_all()
    return Evento.query.get(evento.id)


@pytest.mark.parametrize('situacao', ['publicado', 'aprovado', 'encerrado'])
def test_situacao_no_patch_e_recusada(fabrica, cenario, situacao):
    resposta = _patch(cenario, cenario['evento'], {'situacao': situacao, 'titulo': 'Novo'})

    assert resposta.status_code == 422
    assert resposta.get_json()['campos']['situacao'] == 'Use a publicação.'
    evento = _recarregar(cenario['evento'])
    assert (evento.situacao, evento.titulo) == ('aprovado', cenario['evento'].titulo)
    assert fabrica.cliente().get('/api/eventos').get_json() == []


def test_pai_do_qual_o_chair_tambem_e_chair_e_aceito(fabrica, cenario):
    pai = fabrica.evento(chair=cenario['chair'])
    resposta = _patch(cenario, cenario['evento'], {'eventoPaiId': pai.id})
    assert resposta.status_code == 200 and resposta.get_json()['eventoPaiId'] == pai.id


def test_admin_pode_pendurar_em_qualquer_pai(fabrica, cenario):
    pai = fabrica.evento(chair=fabrica.usuario('Outro'))
    admin = fabrica.cliente(fabrica.usuario('Admin', administrador=True))
    assert admin.patch(f"/api/eventos/{cenario['evento'].id}", json={'eventoPaiId': pai.id}).status_code == 200


def test_pai_de_outro_chair_e_recusado(fabrica, cenario):
    pai = fabrica.evento(chair=fabrica.usuario('Outro chair'))

    resposta = _patch(cenario, cenario['evento'], {'eventoPaiId': pai.id})

    assert resposta.status_code == 422
    assert 'eventoPaiId' in resposta.get_json()['campos']
    assert _recarregar(cenario['evento']).evento_pai_id is None


@pytest.mark.parametrize('invalido', [99999, 'x'])
def test_pai_inexistente_e_recusado(cenario, invalido):
    resposta = _patch(cenario, cenario['evento'], {'eventoPaiId': invalido})
    assert resposta.status_code == 422 and 'eventoPaiId' in resposta.get_json()['campos']


def test_proprio_evento_como_pai_e_recusado(cenario):
    resposta = _patch(cenario, cenario['evento'], {'eventoPaiId': cenario['evento'].id})
    assert resposta.status_code == 422 and 'eventoPaiId' in resposta.get_json()['campos']


def test_ciclo_e_recusado(fabrica, cenario):
    # evento ← filho ← neto; pendurar o evento no neto fecharia o ciclo.
    filho = fabrica.evento(chair=cenario['chair'], evento_pai_id=cenario['evento'].id)
    neto = fabrica.evento(chair=cenario['chair'], evento_pai_id=filho.id)

    resposta = _patch(cenario, cenario['evento'], {'eventoPaiId': neto.id})

    assert resposta.status_code == 422 and 'eventoPaiId' in resposta.get_json()['campos']
    assert _recarregar(cenario['evento']).evento_pai_id is None


def test_tirar_o_pai_com_null_e_permitido(fabrica, cenario):
    pai = fabrica.evento(chair=cenario['chair'])
    _patch(cenario, cenario['evento'], {'eventoPaiId': pai.id})
    resposta = _patch(cenario, cenario['evento'], {'eventoPaiId': None})
    assert resposta.status_code == 200 and resposta.get_json()['eventoPaiId'] is None
