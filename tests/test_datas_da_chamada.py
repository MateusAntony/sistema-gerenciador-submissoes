"""Revisão do P1, obs. g: criar/editar/prorrogar chamada comparam instantes
no fuso do evento, não strings (limite só com data vale até 23:59:59)."""
import pytest


@pytest.fixture
def cenario(fabrica):
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    return {'chair': chair, 'evento': evento, 'cliente': fabrica.cliente(chair)}


@pytest.mark.parametrize('limite_atual, nova, esperado', [
    ('2026-10-30', '2026-10-30T10:00', 422),        # encurtaria o prazo
    ('2026-10-30', '2026-10-31', 200),
    ('2026-10-30T10:00', '2026-10-30', 200),        # fim do dia é depois das 10:00
    ('2026-10-30T10:00', '2026-10-30T09:00', 422),
    ('2026-10-30T10:00', '2026-10-30T10:00', 422),
])
def test_prorrogar(fabrica, cenario, limite_atual, nova, esperado):
    chamada = fabrica.chamada(cenario['evento'], data_limite=limite_atual)
    resposta = cenario['cliente'].post(f'/api/chamadas/{chamada.id}/prorrogar', json={'dataLimite': nova})
    assert resposta.status_code == esperado


@pytest.mark.parametrize('abertura, limite, esperado', [
    ('2026-10-30T10:00', '2026-10-30', 201),        # limite só com data vale até o fim do dia
    ('2026-10-30T10:00', '2026-10-30T09:00', 422),
    ('2026-10-30', '2026-10-30', 201),              # abertura 00:00, limite 23:59:59
])
def test_criar_chamada(fabrica, cenario, abertura, limite, esperado):
    resposta = cenario['cliente'].post(f"/api/eventos/{cenario['evento'].id}/chamadas", json={
        'titulo': 'C', 'dataAbertura': abertura, 'dataLimite': limite})
    assert resposta.status_code == esperado


def test_editar_chamada_compara_instantes(fabrica, cenario):
    chamada = fabrica.chamada(cenario['evento'], data_abertura='2026-10-30T10:00', data_limite='2026-11-30')
    resposta = cenario['cliente'].patch(f'/api/chamadas/{chamada.id}', json={'dataLimite': '2026-10-30'})
    assert resposta.status_code == 200
    resposta = cenario['cliente'].patch(f'/api/chamadas/{chamada.id}', json={'dataLimite': '2026-10-30T09:00'})
    assert resposta.status_code == 422
