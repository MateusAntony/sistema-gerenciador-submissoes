"""Revisão do P1, item 1 (A15 × A17): enquanto houver decisão registrada e
não comunicada, quem não é chair recebe a mesma resposta para qualquer
resultado — senão enviar versão ou retirar revelariam a decisão.
Decisão do maestro (1A): versão → 409 versao_bloqueada; retirar → 409
retirada_bloqueada. Depois de comunicada, decisão final → 409
decisao_ja_emitida."""
import io

import pytest

from app.models.evento import Submissao, VersaoDeArquivo

RESULTADOS = ['aceita', 'aceita_com_correcoes', 'nova_rodada', 'rejeitada']


def _cenario(fabrica):
    autora, chair = fabrica.usuario('Autora'), fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair, modelo_de_avaliacao='simples_cega', maximo_de_rodadas=2)
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(evento))
    return {'autora': autora, 'chair': chair, 'submissao_id': submissao_id}


def _enviar_versao(fabrica, cenario):
    return fabrica.cliente(cenario['autora']).post(
        f"/api/submissoes/{cenario['submissao_id']}/versoes",
        data={'arquivo': (io.BytesIO(b'%PDF v2'), 'v2.pdf'), 'nomeArquivo': 'v2.pdf'},
        content_type='multipart/form-data',
    )


def _retirar(fabrica, cenario):
    return fabrica.cliente(cenario['autora']).post(f"/api/submissoes/{cenario['submissao_id']}/retirar")


def _resposta(resposta):
    corpo = resposta.get_json()
    return resposta.status_code, corpo.get('codigo'), corpo.get('mensagem')


@pytest.mark.parametrize('resultado', RESULTADOS)
def test_enviar_versao_com_decisao_nao_comunicada_e_sempre_versao_bloqueada(fabrica, resultado):
    cenario = _cenario(fabrica)
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], resultado)

    status, codigo, _ = _resposta(_enviar_versao(fabrica, cenario))

    assert (status, codigo) == (409, 'versao_bloqueada')
    assert VersaoDeArquivo.query.filter_by(submissao_id=cenario['submissao_id']).count() == 1


@pytest.mark.parametrize('resultado', RESULTADOS)
def test_retirar_com_decisao_nao_comunicada_e_sempre_retirada_bloqueada(fabrica, resultado):
    cenario = _cenario(fabrica)
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], resultado)

    assert _resposta(_retirar(fabrica, cenario)) == (
        409, 'retirada_bloqueada', 'A submissão está aguardando decisão e não pode ser retirada agora.')
    assert Submissao.query.get(cenario['submissao_id']).situacao != 'retirada'


def test_respostas_identicas_para_os_quatro_resultados(fabrica):
    vistas = set()
    for resultado in RESULTADOS:
        cenario = _cenario(fabrica)
        fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], resultado)
        vistas.add((_resposta(_enviar_versao(fabrica, cenario)), _resposta(_retirar(fabrica, cenario))))
    assert len(vistas) == 1


@pytest.mark.parametrize('resultado', ['aceita', 'aceita_com_correcoes', 'rejeitada'])
def test_retirar_depois_de_decisao_final_comunicada_e_decisao_ja_emitida(fabrica, resultado):
    cenario = _cenario(fabrica)
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], resultado, comunicar=True)

    status, codigo, _ = _resposta(_retirar(fabrica, cenario))

    assert (status, codigo) == (409, 'decisao_ja_emitida')


def test_versao_corrigida_validada_tambem_nao_pode_ser_retirada(fabrica):
    cenario = _cenario(fabrica)
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], 'aceita_com_correcoes', comunicar=True)
    versao = _enviar_versao(fabrica, cenario).get_json()
    fabrica.cliente(cenario['autora']).post(f"/api/submissoes/{cenario['submissao_id']}/versao-corrigida",
                                            json={'versaoId': int(versao['id']), 'descricaoDasAlteracoes': 'C.'})
    fabrica.cliente(cenario['chair']).post(f"/api/submissoes/{cenario['submissao_id']}/versao-corrigida/validar")

    assert _resposta(_retirar(fabrica, cenario))[:2] == (409, 'decisao_ja_emitida')


def test_nova_rodada_comunicada_volta_a_permitir_retirar(fabrica):
    cenario = _cenario(fabrica)
    fabrica.encerrar_e_decidir(cenario['chair'], cenario['submissao_id'], 'nova_rodada')
    aberta = fabrica.cliente(cenario['chair']).post(f"/api/submissoes/{cenario['submissao_id']}/rodadas", json={})
    assert aberta.status_code == 201

    resposta = _retirar(fabrica, cenario)

    assert resposta.status_code == 200 and resposta.get_json()['situacao'] == 'retirada'


def test_sem_decisao_retirar_continua_permitido(fabrica):
    cenario = _cenario(fabrica)
    assert _retirar(fabrica, cenario).status_code == 200


def test_chair_autor_nao_e_mascarado(fabrica):
    # Quem é chair vê a situação real; a guarda de sigilo não se aplica a ele.
    chair = fabrica.usuario('Chair autora')
    evento = fabrica.evento(chair=chair, maximo_de_rodadas=2)
    cenario = {'autora': chair, 'chair': chair,
               'submissao_id': fabrica.submissao_confirmada(chair, fabrica.chamada(evento))}
    fabrica.encerrar_e_decidir(chair, cenario['submissao_id'], 'aceita_com_correcoes')

    assert _enviar_versao(fabrica, cenario).status_code == 201
