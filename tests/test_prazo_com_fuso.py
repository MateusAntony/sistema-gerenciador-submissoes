"""B3 — prazo da chamada com hora e fuso do evento.

dataAbertura/dataLimite são strings locais "YYYY-MM-DDTHH:MM" no fuso do
evento; toda comparação com o relógio converte para UTC com zoneinfo.
"""
import io
from datetime import datetime, timezone

import pytest

from app import prazos
from app.extensions import db
from app.models.evento import Submissao


def _relogio(monkeypatch, iso_utc):
    instante = datetime.fromisoformat(iso_utc).replace(tzinfo=timezone.utc)
    monkeypatch.setattr(prazos, 'agora_utc', lambda: instante)


@pytest.fixture
def chair(fabrica):
    return fabrica.usuario('Chair')


@pytest.fixture
def autora(fabrica):
    return fabrica.usuario('Autora')


def _criar(fabrica, autora, chamada):
    return fabrica.cliente(autora).post(f'/api/chamadas/{chamada.id}/submissoes', json={})


# America/Bahia = UTC-3 o ano todo.

@pytest.mark.parametrize('agora_utc, esperado', [
    ('2026-10-31T01:00', 201),  # 30/10 22:00 na Bahia: ainda aberta
    ('2026-10-31T02:58', 201),  # 30/10 23:58
    ('2026-10-31T03:00', 409),  # 31/10 00:00: encerrada
])
def test_limite_as_23h59_fecha_no_horario_local(fabrica, chair, autora, monkeypatch, agora_utc, esperado):
    chamada = fabrica.chamada(fabrica.evento(chair=chair), data_limite='2026-10-30T23:59')
    _relogio(monkeypatch, agora_utc)

    assert _criar(fabrica, autora, chamada).status_code == esperado


@pytest.mark.parametrize('agora_utc, esperado', [
    ('2026-10-30T12:59', 201),  # 09:59 na Bahia
    ('2026-10-30T13:01', 409),  # 10:01: já passou das 10:00, mesmo sendo o mesmo dia
])
def test_limite_as_10h_nao_fica_aberto_ate_o_fim_do_dia(fabrica, chair, autora, monkeypatch, agora_utc, esperado):
    chamada = fabrica.chamada(fabrica.evento(chair=chair), data_limite='2026-10-30T10:00')
    _relogio(monkeypatch, agora_utc)

    assert _criar(fabrica, autora, chamada).status_code == esperado


@pytest.mark.parametrize('agora_utc, esperado', [
    ('2026-10-30T00:59', 201),  # 09:59 em Tóquio (UTC+9)
    ('2026-10-30T01:01', 409),
])
def test_usa_o_fuso_do_evento(fabrica, chair, autora, monkeypatch, agora_utc, esperado):
    evento = fabrica.evento(chair=chair, fuso='Asia/Tokyo')
    chamada = fabrica.chamada(evento, data_limite='2026-10-30T10:00')
    _relogio(monkeypatch, agora_utc)

    assert _criar(fabrica, autora, chamada).status_code == esperado


@pytest.mark.parametrize('agora_utc, esperado', [
    ('2026-10-31T02:00', 201),  # 30/10 23:00 na Bahia
    ('2026-10-31T03:30', 409),  # 31/10 00:30
])
def test_limite_so_com_data_vale_ate_o_fim_do_dia_local(fabrica, chair, autora, monkeypatch, agora_utc, esperado):
    chamada = fabrica.chamada(fabrica.evento(chair=chair), data_limite='2026-10-30')
    _relogio(monkeypatch, agora_utc)

    assert _criar(fabrica, autora, chamada).status_code == esperado


def _rascunho_completo(fabrica, autora, chamada):
    cliente = fabrica.cliente(autora)
    submissao_id = int(_criar(fabrica, autora, chamada).get_json()['id'])
    cliente.patch(f'/api/submissoes/{submissao_id}', json={'respostas': {'titulo': 'T', 'resumo': 'R'}})
    fabrica.enviar_versao(cliente, submissao_id)
    return submissao_id


def test_enviar_versao_depois_do_prazo_local(fabrica, chair, autora, monkeypatch):
    chamada = fabrica.chamada(fabrica.evento(chair=chair), data_limite='2026-10-30T10:00')
    _relogio(monkeypatch, '2026-10-30T12:00')
    submissao_id = _rascunho_completo(fabrica, autora, chamada)

    _relogio(monkeypatch, '2026-10-30T13:30')
    resposta = fabrica.cliente(autora).post(
        f'/api/submissoes/{submissao_id}/versoes',
        data={'arquivo': (io.BytesIO(b'%PDF'), 'v2.pdf'), 'nomeArquivo': 'v2.pdf'},
        content_type='multipart/form-data',
    )
    assert resposta.status_code == 409
    assert resposta.get_json()['codigo'] == 'chamada_encerrada'


def test_confirmar_depois_do_prazo_local_sem_tolerancia(fabrica, chair, autora, monkeypatch):
    chamada = fabrica.chamada(fabrica.evento(chair=chair), data_limite='2026-10-30T10:00')
    _relogio(monkeypatch, '2026-10-30T12:00')
    submissao_id = _rascunho_completo(fabrica, autora, chamada)

    _relogio(monkeypatch, '2026-10-30T13:30')
    resposta = fabrica.cliente(autora).post(f'/api/submissoes/{submissao_id}/confirmar')

    assert resposta.status_code == 409
    assert resposta.get_json()['codigo'] == 'prazo_encerrado'


@pytest.mark.parametrize('agora_utc, fora_do_prazo', [
    ('2026-10-30T12:30', False),
    ('2026-10-30T13:30', True),
])
def test_confirmar_marca_fora_do_prazo_pelo_horario_local(fabrica, chair, autora, monkeypatch, agora_utc, fora_do_prazo):
    chamada = fabrica.chamada(
        fabrica.evento(chair=chair), data_limite='2026-10-30T10:00', permite_submissao_apos_prazo=True,
    )
    _relogio(monkeypatch, '2026-10-30T12:00')
    submissao_id = _rascunho_completo(fabrica, autora, chamada)

    _relogio(monkeypatch, agora_utc)
    resposta = fabrica.cliente(autora).post(f'/api/submissoes/{submissao_id}/confirmar')

    assert resposta.status_code == 200
    assert resposta.get_json()['foraDoPrazo'] is fora_do_prazo


def test_encerrada_manualmente_continua_fechando(fabrica, chair, autora, monkeypatch):
    chamada = fabrica.chamada(fabrica.evento(chair=chair), encerrada_manualmente=True)
    _relogio(monkeypatch, '2026-01-02T00:00')
    assert _criar(fabrica, autora, chamada).status_code == 409


def test_instante_utc_converte_string_local():
    assert prazos.instante_utc('2026-10-30T23:59', 'America/Bahia') == datetime(2026, 10, 31, 2, 59, tzinfo=timezone.utc)
    assert prazos.instante_utc('', 'America/Bahia') is None
    assert prazos.instante_utc('não é data', 'America/Bahia') is None


def test_rascunho_criado_antes_do_prazo_ainda_existe(fabrica, chair, autora, monkeypatch):
    # Sanidade do cenário: o rascunho foi criado pelo caminho real, não gravado à mão.
    chamada = fabrica.chamada(fabrica.evento(chair=chair), data_limite='2026-10-30T10:00')
    _relogio(monkeypatch, '2026-10-30T12:00')
    submissao_id = _rascunho_completo(fabrica, autora, chamada)
    assert db.session.get(Submissao, submissao_id).situacao == 'rascunho'
