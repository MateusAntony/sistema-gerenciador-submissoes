"""B1 (A-12) — checklist-publicacao e publicar com formulário e etapas reais:
formularioDefinido = há formulário publicado em todas as chamadas do evento;
etapasDefinidas = há ao menos uma fase ativa no evento."""
import pytest

CAMPO = {'chave': 'palavras', 'tipo': 'texto', 'rotulo': 'Palavras-chave',
         'obrigatorio': True, 'ordem': 1, 'base': False}
FASE = {'nome': 'Triagem', 'ordem': 1, 'momento': 'triagem', 'prazoPadraoDias': 5,
        'obrigatoria': True, 'exigeArquivo': False, 'permiteDevolucao': False, 'ativo': True}


@pytest.fixture
def chair(fabrica):
    return fabrica.usuario('Chair')


@pytest.fixture
def evento(fabrica, chair):
    return fabrica.evento(chair=chair)


def _publicar_formulario(fabrica, chair, chamada, publicar=True):
    cliente = fabrica.cliente(chair)
    rascunho = cliente.put(f'/api/chamadas/{chamada.id}/formulario/rascunho', json={'versao': 1, 'campos': [CAMPO]})
    assert rascunho.status_code == 200, rascunho.get_json()
    if publicar:
        publicado = cliente.post(f'/api/chamadas/{chamada.id}/formulario/publicar', json={'versao': 1})
        assert publicado.status_code == 200, publicado.get_json()


def _criar_fase(fabrica, chair, evento, ativo=True):
    resposta = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/fases', json={**FASE, 'ativo': ativo})
    assert resposta.status_code == 201, resposta.get_json()


def _criar_criterio(fabrica, chair, evento):
    resposta = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/criterios', json={
        'titulo': 'Mérito', 'notaMinima': 0, 'notaMaxima': 10, 'peso': 1,
    })
    assert resposta.status_code == 201, resposta.get_json()


def _checklist(fabrica, chair, evento):
    resposta = fabrica.cliente(chair).get(f'/api/eventos/{evento.id}/checklist-publicacao')
    assert resposta.status_code == 200
    return resposta.get_json()


def test_sem_chamada_o_formulario_nao_esta_definido(fabrica, chair, evento):
    checklist = _checklist(fabrica, chair, evento)
    assert checklist['formularioDefinido'] is False
    assert checklist['etapasDefinidas'] is False


def test_formulario_publicado_em_todas_as_chamadas(fabrica, chair, evento):
    primeira = fabrica.chamada(evento)
    segunda = fabrica.chamada(evento, titulo='Chamada de pôsteres')
    _publicar_formulario(fabrica, chair, primeira)

    assert _checklist(fabrica, chair, evento)['formularioDefinido'] is False

    _publicar_formulario(fabrica, chair, segunda)
    assert _checklist(fabrica, chair, evento)['formularioDefinido'] is True


def test_rascunho_de_formulario_nao_conta(fabrica, chair, evento):
    _publicar_formulario(fabrica, chair, fabrica.chamada(evento), publicar=False)
    assert _checklist(fabrica, chair, evento)['formularioDefinido'] is False


def test_formulario_de_outro_evento_nao_conta(fabrica, chair, evento):
    fabrica.chamada(evento)
    outro = fabrica.evento(chair=chair)
    _publicar_formulario(fabrica, chair, fabrica.chamada(outro))
    assert _checklist(fabrica, chair, evento)['formularioDefinido'] is False


def test_etapas_definidas_exige_fase_ativa(fabrica, chair, evento):
    _criar_fase(fabrica, chair, evento, ativo=False)
    assert _checklist(fabrica, chair, evento)['etapasDefinidas'] is False

    _criar_fase(fabrica, chair, evento, ativo=True)
    assert _checklist(fabrica, chair, evento)['etapasDefinidas'] is True


def test_fase_de_outro_evento_nao_conta(fabrica, chair, evento):
    _criar_fase(fabrica, chair, fabrica.evento(chair=chair))
    assert _checklist(fabrica, chair, evento)['etapasDefinidas'] is False


def _evento_pronto(fabrica, chair, evento, com_fase=True):
    _publicar_formulario(fabrica, chair, fabrica.chamada(evento))
    _criar_criterio(fabrica, chair, evento)
    if com_fase:
        _criar_fase(fabrica, chair, evento)


def test_publicar_com_checklist_completo(fabrica, chair, evento):
    _evento_pronto(fabrica, chair, evento)

    resposta = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/publicar', json={})

    assert resposta.status_code == 200, resposta.get_json()
    assert resposta.get_json()['situacao'] == 'publicado'


def test_publicar_sem_fase_aponta_so_as_etapas(fabrica, chair, evento):
    _evento_pronto(fabrica, chair, evento, com_fase=False)

    resposta = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/publicar', json={})

    assert resposta.status_code == 422
    assert set(resposta.get_json()['campos']) == {'etapasDefinidas'}


def test_publicar_sem_formulario_publicado_aponta_o_formulario(fabrica, chair, evento):
    _publicar_formulario(fabrica, chair, fabrica.chamada(evento), publicar=False)
    _criar_criterio(fabrica, chair, evento)
    _criar_fase(fabrica, chair, evento)

    resposta = fabrica.cliente(chair).post(f'/api/eventos/{evento.id}/publicar', json={})

    assert resposta.status_code == 422
    assert set(resposta.get_json()['campos']) == {'formularioDefinido'}
