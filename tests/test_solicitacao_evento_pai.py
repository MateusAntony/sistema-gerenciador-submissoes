"""Decisão do maestro sobre a nota 1 do Lince: POST/PATCH /solicitacoes-evento
validam eventoPaiId como o PATCH do evento (pai existente e solicitante
chair/admin dele), senão 422 campos.eventoPaiId — a regra não pode ser
contornada por uma solicitação que o admin aprova."""
import pytest

from app.models.evento import SolicitacaoEvento


def _corpo(identificador, **extra):
    return {'titulo': 'Workshop', 'identificadorPagina': identificador, 'dataInicio': '2026-11-10',
            'dataTermino': '2026-11-12', 'pais': 'Brasil', 'fuso': 'America/Bahia', **extra}


@pytest.fixture
def pessoa(fabrica):
    return fabrica.usuario('Solicitante')


def _criar(fabrica, usuario, **extra):
    return fabrica.cliente(usuario).post('/api/solicitacoes-evento', json=_corpo('workshop-2026', **extra))


def test_pai_do_qual_e_chair_e_aceito(fabrica, pessoa):
    pai = fabrica.evento(chair=pessoa)
    resposta = _criar(fabrica, pessoa, eventoPaiId=pai.id)
    assert resposta.status_code == 201 and resposta.get_json()['eventoPaiId'] == pai.id


def test_sem_pai_continua_aceito(fabrica, pessoa):
    assert _criar(fabrica, pessoa).status_code == 201
    assert fabrica.cliente(pessoa).post('/api/solicitacoes-evento',
                                        json=_corpo('outro-2026', eventoPaiId=None)).status_code == 201


def test_admin_pode_indicar_qualquer_pai(fabrica):
    admin = fabrica.usuario('Admin', administrador=True)
    pai = fabrica.evento(chair=fabrica.usuario('Outro'))
    assert _criar(fabrica, admin, eventoPaiId=pai.id).status_code == 201


@pytest.mark.parametrize('pai', ['de_outro_chair', 'inexistente', 'texto', 'booleano'])
def test_pai_invalido_na_criacao_e_recusado(fabrica, pessoa, pai):
    valor = {
        'de_outro_chair': lambda: fabrica.evento(chair=fabrica.usuario('Outro')).id,
        'inexistente': lambda: 99999,
        'texto': lambda: 'x',
        'booleano': lambda: True,
    }[pai]()

    resposta = _criar(fabrica, pessoa, eventoPaiId=valor)

    assert resposta.status_code == 422
    assert 'eventoPaiId' in resposta.get_json()['campos']
    assert SolicitacaoEvento.query.count() == 0


def test_pai_invalido_na_edicao_e_recusado(fabrica, pessoa):
    criada = _criar(fabrica, pessoa).get_json()
    pai_alheio = fabrica.evento(chair=fabrica.usuario('Outro'))

    resposta = fabrica.cliente(pessoa).patch(f"/api/solicitacoes-evento/{criada['id']}",
                                             json=_corpo('workshop-2026', eventoPaiId=pai_alheio.id))

    assert resposta.status_code == 422
    assert 'eventoPaiId' in resposta.get_json()['campos']
    assert SolicitacaoEvento.query.get(criada['id']).evento_pai_id is None


def test_pai_valido_na_edicao_e_aceito(fabrica, pessoa):
    criada = _criar(fabrica, pessoa).get_json()
    pai = fabrica.evento(chair=pessoa)
    resposta = fabrica.cliente(pessoa).patch(f"/api/solicitacoes-evento/{criada['id']}",
                                             json=_corpo('workshop-2026', eventoPaiId=pai.id))
    assert resposta.status_code == 200 and resposta.get_json()['eventoPaiId'] == pai.id
