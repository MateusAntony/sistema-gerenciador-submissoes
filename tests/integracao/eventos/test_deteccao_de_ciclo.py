"""Deteccao de ciclo na hierarquia de eventos — API-11 AC5 (T29).

A regra vive no service porque o ciclo so e visivel percorrendo a arvore, e a
constraint do banco nao a exprime. O caso de dados legados com ciclo ja gravado
esta aqui porque e o que impede a travessia de nunca terminar (Edge Case).
"""

import pytest

from app.core.erros import ErroDeValidacao
from app.modules.eventos.repository import EventoRepository
from app.modules.eventos.services.solicitacao import SolicitacaoService


def criar_evento(identificador: str, pai_id=None):
    return EventoRepository.criar(
        situacao="aprovado",
        titulo=identificador,
        ano=2026,
        identificador_pagina=identificador,
        evento_pai_id=pai_id,
    )


def test_o_pai_que_e_filho_do_proprio_evento_e_recusado_em_evento_pai_id(sessao):
    proprio = criar_evento("proprio-2026")
    filho = criar_evento("filho-2026", pai_id=proprio.id)

    with pytest.raises(ErroDeValidacao) as recusa:
        SolicitacaoService.validar_evento_pai(filho.id, evento_proprio=proprio.id)

    assert "eventoPaiId" in recusa.value.extras["campos"]
    assert recusa.value.status == 422


def test_o_pai_que_e_neto_do_proprio_evento_e_recusado_em_evento_pai_id(sessao):
    avo = criar_evento("avo-2026")
    filho = criar_evento("filho-do-avo-2026", pai_id=avo.id)
    neto = criar_evento("neto-2026", pai_id=filho.id)

    with pytest.raises(ErroDeValidacao) as recusa:
        SolicitacaoService.validar_evento_pai(neto.id, evento_proprio=avo.id)

    assert "eventoPaiId" in recusa.value.extras["campos"]


def test_o_proprio_evento_como_pai_de_si_mesmo_e_recusado(sessao):
    proprio = criar_evento("auto-pai-2026")

    with pytest.raises(ErroDeValidacao) as recusa:
        SolicitacaoService.validar_evento_pai(proprio.id, evento_proprio=proprio.id)

    assert "eventoPaiId" in recusa.value.extras["campos"]


def test_um_pai_fora_da_descendencia_e_aceito(sessao):
    proprio = criar_evento("proprio-b-2026")
    criar_evento("filho-b-2026", pai_id=proprio.id)
    irmao = criar_evento("irmao-2026")

    SolicitacaoService.validar_evento_pai(irmao.id, evento_proprio=proprio.id)


def test_um_ciclo_ja_gravado_nao_faz_a_travessia_girar_para_sempre(sessao):
    primeiro = criar_evento("ciclo-a-2026")
    segundo = criar_evento("ciclo-b-2026", pai_id=primeiro.id)
    primeiro.evento_pai_id = segundo.id
    sessao.flush()

    fora = criar_evento("fora-do-ciclo-2026")

    # Termina: cada evento e visitado uma vez so. E nao acusa ciclo, porque
    # `fora` nao aparece na cadeia de ancestrais de `segundo`.
    SolicitacaoService.validar_evento_pai(segundo.id, evento_proprio=fora.id)
