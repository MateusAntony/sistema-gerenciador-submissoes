"""B9 — rotas de escrita/gestão de evento exigem chair do evento ou admin:
401 sem sessão, 403 sem o papel (inclusive chair de outro evento)."""
import pytest

from app.extensions import db
from app.models.evento import Chamada, Criterio, Evento, Trilha
from app.models.fase import DefinicaoFase

CAMPO = {'chave': 'palavras', 'tipo': 'texto', 'rotulo': 'Palavras-chave',
         'obrigatorio': True, 'ordem': 1, 'base': False}
FASE = {'nome': 'Triagem', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': False, 'permiteDevolucao': False, 'ativo': True}


@pytest.fixture
def cenario(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    trilha = Trilha(evento_id=evento.id, nome='Trilha A')
    criterio = Criterio(evento_id=evento.id, titulo='Mérito', nota_minima=0, nota_maxima=10, peso=1)
    fase = DefinicaoFase(evento_id=evento.id, nome='Triagem', ordem=1, momento='triagem')
    db.session.add_all([trilha, criterio, fase])
    db.session.commit()
    return {'chair': chair, 'evento': evento, 'chamada': chamada, 'trilha': trilha,
            'criterio': criterio, 'fase': fase}


# (método, url, corpo) — ids resolvidos a partir do cenário.
ROTAS = [
    ('GET', '/api/eventos/{evento}/checklist-publicacao', None),
    ('POST', '/api/eventos/{evento}/publicar', {}),
    ('PATCH', '/api/eventos/{evento}', {'titulo': 'Invadido'}),
    ('POST', '/api/eventos/{evento}/trilhas', {'nome': 'Nova'}),
    ('PATCH', '/api/trilhas/{trilha}', {'nome': 'Invadida'}),
    ('POST', '/api/eventos/{evento}/chamadas', {'titulo': 'Nova', 'dataAbertura': '2026-01-01T00:00', 'dataLimite': '2099-01-01T00:00'}),
    ('PATCH', '/api/chamadas/{chamada}', {'titulo': 'Invadida'}),
    ('POST', '/api/chamadas/{chamada}/prorrogar', {'dataLimite': '2100-01-01T00:00'}),
    ('POST', '/api/chamadas/{chamada}/encerrar', {}),
    ('POST', '/api/eventos/{evento}/criterios', {'titulo': 'Novo', 'notaMinima': 0, 'notaMaxima': 10, 'peso': 1}),
    ('PATCH', '/api/criterios/{criterio}', {'titulo': 'Invadido'}),
    ('DELETE', '/api/criterios/{criterio}', None),
    ('PUT', '/api/chamadas/{chamada}/formulario/rascunho', {'versao': 1, 'campos': [CAMPO]}),
    ('POST', '/api/chamadas/{chamada}/formulario/publicar', {'versao': 1}),
    ('POST', '/api/eventos/{evento}/fases', FASE),
    ('PATCH', '/api/fases/{fase}', {'nome': 'Invadida'}),
    ('DELETE', '/api/fases/{fase}', None),
    ('PUT', '/api/chamadas/{chamada}/passos', {'passos': [{'nome': 'P', 'ordem': 1, 'campos': []}]}),
]
IDS = [f'{metodo} {url}' for metodo, url, _ in ROTAS]


def _chamar(cliente, cenario, metodo, url, corpo):
    url = url.format(**{chave: getattr(valor, 'id', None) for chave, valor in cenario.items()})
    return cliente.open(url, method=metodo, json=corpo)


@pytest.mark.parametrize('metodo, url, corpo', ROTAS, ids=IDS)
def test_sem_sessao_401(fabrica, cenario, metodo, url, corpo):
    assert _chamar(fabrica.cliente(), cenario, metodo, url, corpo).status_code == 401


@pytest.mark.parametrize('metodo, url, corpo', ROTAS, ids=IDS)
def test_usuario_sem_papel_403(fabrica, cenario, metodo, url, corpo):
    resposta = _chamar(fabrica.cliente(fabrica.usuario('Autora')), cenario, metodo, url, corpo)
    assert resposta.status_code == 403
    assert resposta.get_json()['codigo'] == 'sem_permissao'


@pytest.mark.parametrize('metodo, url, corpo', ROTAS, ids=IDS)
def test_chair_de_outro_evento_403(fabrica, cenario, metodo, url, corpo):
    outro_chair = fabrica.usuario('Outro chair')
    fabrica.evento(chair=outro_chair)
    assert _chamar(fabrica.cliente(outro_chair), cenario, metodo, url, corpo).status_code == 403


@pytest.mark.parametrize('metodo, url, corpo', ROTAS, ids=IDS)
@pytest.mark.parametrize('papel', ['chair', 'admin'])
def test_chair_e_admin_passam_pela_guarda(fabrica, cenario, metodo, url, corpo, papel):
    usuario = cenario['chair'] if papel == 'chair' else fabrica.usuario('Admin', administrador=True)
    resposta = _chamar(fabrica.cliente(usuario), cenario, metodo, url, corpo)
    # Publicar formulário sem rascunho é um 404 legítimo do próprio recurso.
    if url.endswith('formulario/publicar'):
        assert resposta.get_json()['codigo'] == 'rascunho_inexistente'
        return
    assert resposta.status_code not in (401, 403, 404, 405), resposta.get_json()


def test_recusa_nao_altera_nada(fabrica, cenario):
    autora = fabrica.cliente(fabrica.usuario('Autora'))
    autora.patch(f"/api/eventos/{cenario['evento'].id}", json={'titulo': 'Invadido'})
    autora.post(f"/api/chamadas/{cenario['chamada'].id}/encerrar")
    autora.delete(f"/api/criterios/{cenario['criterio'].id}")
    db.session.expire_all()

    assert Evento.query.get(cenario['evento'].id).titulo != 'Invadido'
    assert Chamada.query.get(cenario['chamada'].id).encerrada_manualmente is False
    assert Criterio.query.get(cenario['criterio'].id) is not None


@pytest.mark.parametrize('url', [
    '/api/eventos/99999/checklist-publicacao', '/api/trilhas/99999', '/api/chamadas/99999/encerrar',
    '/api/criterios/99999', '/api/fases/99999',
])
def test_inexistente_continua_404_para_quem_esta_logado(fabrica, cenario, url):
    metodo = 'GET' if url.endswith('checklist-publicacao') else ('POST' if url.endswith('encerrar') else 'PATCH')
    resposta = fabrica.cliente(fabrica.usuario('Admin', administrador=True)).open(url, method=metodo, json={})
    assert resposta.status_code == 404


@pytest.mark.parametrize('url', [
    '/api/eventos', '/api/eventos/{evento}', '/api/eventos/{evento}/trilhas',
    '/api/eventos/{evento}/chamadas', '/api/eventos/{evento}/criterios',
])
def test_leituras_publicas_continuam_abertas(fabrica, cenario, url):
    assert _chamar(fabrica.cliente(), cenario, 'GET', url, None).status_code == 200
