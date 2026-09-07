"""Testes da matriz de permissoes — API-09, riscos R8 e R9 (T21).

Duas frentes. A primeira transcreve a §3.7 numa tabela **independente** da do
codigo e cobre toda combinacao de acao x papel, mais a coluna do autor e a do
administrador. A segunda e o teste de paridade de R9: le `permissoes.ts` do
repositorio do front em tempo de execucao e falha se qualquer par divergir.
"""

import os
import re
from pathlib import Path

import pytest

from app.core.permissoes import (
    DE_ADMINISTRADOR,
    DE_AUTOR,
    POR_PAPEL,
    Acao,
    Papel,
    pode,
)

# A matriz da §3.7 transcrita a mao a partir do documento e de `permissoes.ts`.
# E a expectativa do teste: se o codigo divergir dela, o teste cai.
CONCEDIDO_POR_PAPEL = {
    Papel.CHAIR: {
        Acao.CONFIGURAR_EVENTO,
        Acao.DEFINIR_CRITERIOS_E_ETAPAS,
        Acao.ATRIBUIR_AVALIADORES,
        Acao.EMITIR_DECISAO,
        Acao.EXECUTAR_ETAPA,
    },
    Papel.AVALIADOR: {Acao.RESPONDER_CONVITE, Acao.EMITIR_PARECER},
    Papel.RESPONSAVEL_ETAPA: {Acao.EXECUTAR_ETAPA},
}

CONCEDIDO_AO_AUTOR = {Acao.SUBMETER_TRABALHO, Acao.RESPONDER_REBUTTAL}

CONCEDIDO_AO_ADMINISTRADOR = {
    Acao.APROVAR_SOLICITACAO_EVENTO,
    Acao.GERENCIAR_CONTAS,
    Acao.CONSULTAR_AUDITORIA,
    Acao.CONFIGURAR_EVENTO,
    Acao.DEFINIR_CRITERIOS_E_ETAPAS,
    Acao.ATRIBUIR_AVALIADORES,
    Acao.EMITIR_DECISAO,
}

ACOES_DA_SECAO_3_7 = [
    "aprovar_solicitacao_evento",
    "gerenciar_contas",
    "consultar_auditoria",
    "configurar_evento",
    "definir_criterios_e_etapas",
    "atribuir_avaliadores",
    "emitir_decisao",
    "submeter_trabalho",
    "responder_convite",
    "emitir_parecer",
    "responder_rebuttal",
    "executar_etapa",
]

PAPEIS_DA_SECAO_3_7 = ["chair", "avaliador", "responsavel_etapa"]


# --- Valores da matriz (Done when 1) ---------------------------------------


def test_a_enumeracao_de_acoes_tem_os_doze_valores_da_secao_3_7():
    assert [acao.value for acao in Acao] == ACOES_DA_SECAO_3_7


def test_a_enumeracao_de_papeis_tem_os_tres_papeis_por_evento():
    assert [papel.value for papel in Papel] == PAPEIS_DA_SECAO_3_7


# --- Tabela completa: toda combinacao acao x papel (Done when 4) -----------


@pytest.mark.parametrize("papel", list(Papel))
@pytest.mark.parametrize("acao", list(Acao))
def test_cada_par_de_acao_e_papel_segue_a_matriz(acao: Acao, papel: Papel):
    esperado = acao in CONCEDIDO_POR_PAPEL[papel] or acao in CONCEDIDO_AO_AUTOR

    assert pode(acao, [papel], False) is esperado


@pytest.mark.parametrize("acao", list(Acao))
def test_sessao_sem_papel_algum_so_pode_as_acoes_de_autor(acao: Acao):
    assert pode(acao, [], False) is (acao in CONCEDIDO_AO_AUTOR)


@pytest.mark.parametrize("acao", list(Acao))
def test_o_administrador_soma_a_coluna_dele_a_de_autor(acao: Acao):
    esperado = acao in CONCEDIDO_AO_ADMINISTRADOR or acao in CONCEDIDO_AO_AUTOR

    assert pode(acao, [], True) is esperado


# --- As tres regras de `pode()` (Done when 2) ------------------------------


@pytest.mark.parametrize("acao", sorted(CONCEDIDO_AO_AUTOR, key=lambda a: a.value))
def test_acao_de_autor_vale_para_qualquer_sessao_autenticada(acao: Acao):
    assert pode(acao, [], False) is True
    assert pode(acao, [Papel.AVALIADOR], False) is True
    assert pode(acao, [Papel.CHAIR], True) is True


def test_o_administrador_configura_evento_sem_ser_chair_dele():
    assert pode(Acao.CONFIGURAR_EVENTO, [], False) is False
    assert pode(Acao.CONFIGURAR_EVENTO, [], True) is True


def test_o_administrador_nao_ganha_as_acoes_que_sao_so_de_papel_no_evento():
    # `emitir_parecer` e `responder_convite` sao do avaliador e nao estao na
    # coluna do administrador: ser administrador nao as concede.
    assert pode(Acao.EMITIR_PARECER, [], True) is False
    assert pode(Acao.RESPONDER_CONVITE, [], True) is False


def test_dois_papeis_no_mesmo_evento_acumulam_as_permissoes_dos_dois():
    papeis = [Papel.AVALIADOR, Papel.RESPONSAVEL_ETAPA]

    assert pode(Acao.EMITIR_PARECER, papeis, False) is True
    assert pode(Acao.EXECUTAR_ETAPA, papeis, False) is True
    # E nada alem da uniao das duas colunas.
    assert pode(Acao.CONFIGURAR_EVENTO, papeis, False) is False


# --- Paridade com a matriz do front (Done when 3, risco R9) ----------------

CAMINHO_PADRAO_DO_FRONT = Path(r"C:\Users\lucas\projeto-extensao")
CAMINHO_RELATIVO_DA_MATRIZ = Path("app/src/shared/auth/permissoes.ts")


def caminho_da_matriz_do_front() -> Path:
    raiz = os.environ.get("REPOSITORIO_DO_FRONT") or CAMINHO_PADRAO_DO_FRONT
    return Path(raiz) / CAMINHO_RELATIVO_DA_MATRIZ


def _lista_ts(fonte: str, nome: str) -> list[str]:
    """Os literais de uma lista `const NOME ... = [...]` do arquivo TypeScript."""
    achado = re.search(rf"\b{nome}\b[^=]*=\s*\[(.*?)\]", fonte, re.DOTALL)
    assert achado is not None, (
        f"A lista '{nome}' não foi encontrada em {caminho_da_matriz_do_front()}. "
        "A matriz do front mudou de forma e a paridade não pode ser conferida."
    )
    return re.findall(r"'([^']+)'", achado.group(1))


def _por_papel_ts(fonte: str) -> dict[str, list[str]]:
    achado = re.search(r"POR_PAPEL[^=]*=\s*\{(.*?)\n\}", fonte, re.DOTALL)
    assert achado is not None, (
        f"O objeto 'POR_PAPEL' não foi encontrado em {caminho_da_matriz_do_front()}."
    )
    return {
        papel: re.findall(r"'([^']+)'", acoes)
        for papel, acoes in re.findall(
            r"(\w+):\s*\[(.*?)\]", achado.group(1), re.DOTALL
        )
    }


@pytest.fixture(scope="module")
def matriz_do_front() -> str:
    """O `permissoes.ts` do repositorio do front, lido em tempo de execucao.

    Sem o arquivo o teste **falha**: um teste de paridade que se desliga quando
    nao acha a contraparte nao protege de divergencia nenhuma (risco R9).
    """
    caminho = caminho_da_matriz_do_front()
    if not caminho.is_file():
        pytest.fail(
            f"A matriz de permissões do front não foi encontrada em {caminho}. "
            "O teste de paridade de R9 não pode ser verificado; aponte "
            "REPOSITORIO_DO_FRONT para o repositório do front."
        )
    return caminho.read_text(encoding="utf-8")


def test_as_acoes_do_front_sao_as_mesmas_da_matriz_portada(matriz_do_front):
    assert _lista_ts(matriz_do_front, "ACOES") == [acao.value for acao in Acao]


def test_os_papeis_do_front_sao_os_mesmos_da_matriz_portada(matriz_do_front):
    declaracao = re.search(r"export type Papel\s*=\s*([^\n]+)", matriz_do_front)
    assert declaracao is not None, "A declaração de `Papel` sumiu do front."

    assert re.findall(r"'([^']+)'", declaracao.group(1)) == [
        papel.value for papel in Papel
    ]


def test_a_coluna_de_autor_do_front_e_a_mesma_da_matriz_portada(matriz_do_front):
    assert set(_lista_ts(matriz_do_front, "DE_AUTOR")) == {
        acao.value for acao in DE_AUTOR
    }


def test_a_coluna_do_administrador_do_front_e_a_mesma_da_portada(matriz_do_front):
    assert set(_lista_ts(matriz_do_front, "DE_ADMINISTRADOR")) == {
        acao.value for acao in DE_ADMINISTRADOR
    }


def test_nenhum_par_de_acao_e_papel_diverge_entre_o_front_e_a_api(matriz_do_front):
    do_front = _por_papel_ts(matriz_do_front)

    divergencias = [
        (acao.value, papel.value)
        for papel in Papel
        for acao in Acao
        if (acao.value in do_front.get(papel.value, []))
        is not (acao in POR_PAPEL[papel])
    ]

    assert divergencias == [], (
        "A matriz da API divergiu de permissoes.ts nos pares "
        f"(ação, papel): {divergencias}"
    )
