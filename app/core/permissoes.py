"""A matriz de permissoes da §3.7 e as guardas de autorizacao da borda HTTP.

A matriz e um porte tabela-a-tabela de `app/src/shared/auth/permissoes.ts` do
repositorio do front (risco R8). As duas implementacoes convivem por decisao
consciente, e um teste de paridade le o `.ts` e falha se qualquer par
(acao, papel) divergir (risco R9): a divergencia silenciosa e o unico desfecho
inaceitavel — o front mostraria menu para acao que a API nega.
"""

import uuid
from collections.abc import Callable, Iterable
from enum import Enum
from functools import wraps

from flask import g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt import PyJWTError

from app.core.erros import NaoAutenticado, SemPermissao
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.eventos.repository import ParticipacaoRepository

CHAVE_DO_USUARIO = "usuario_autenticado"

class Acao(str, Enum):
    """As doze acoes governadas pela matriz. A ordem segue a §3.7."""

    APROVAR_SOLICITACAO_EVENTO = "aprovar_solicitacao_evento"
    GERENCIAR_CONTAS = "gerenciar_contas"
    CONSULTAR_AUDITORIA = "consultar_auditoria"
    CONFIGURAR_EVENTO = "configurar_evento"
    DEFINIR_CRITERIOS_E_ETAPAS = "definir_criterios_e_etapas"
    ATRIBUIR_AVALIADORES = "atribuir_avaliadores"
    EMITIR_DECISAO = "emitir_decisao"
    SUBMETER_TRABALHO = "submeter_trabalho"
    RESPONDER_CONVITE = "responder_convite"
    EMITIR_PARECER = "emitir_parecer"
    RESPONDER_REBUTTAL = "responder_rebuttal"
    EXECUTAR_ETAPA = "executar_etapa"


class Papel(str, Enum):
    """Papeis atribuidos **por evento** (RN02); os valores sao os de `papel_enum`."""

    CHAIR = "chair"
    AVALIADOR = "avaliador"
    RESPONSAVEL_ETAPA = "responsavel_etapa"


# Coluna "Autor" da §3.7. Autor nao e papel de evento: e todo usuario cadastrado,
# entao estas duas acoes acompanham qualquer sessao autenticada.
DE_AUTOR: frozenset[Acao] = frozenset(
    {Acao.SUBMETER_TRABALHO, Acao.RESPONDER_REBUTTAL}
)

POR_PAPEL: dict[Papel, frozenset[Acao]] = {
    Papel.CHAIR: frozenset(
        {
            Acao.CONFIGURAR_EVENTO,
            Acao.DEFINIR_CRITERIOS_E_ETAPAS,
            Acao.ATRIBUIR_AVALIADORES,
            Acao.EMITIR_DECISAO,
            Acao.EXECUTAR_ETAPA,
        }
    ),
    Papel.AVALIADOR: frozenset({Acao.RESPONDER_CONVITE, Acao.EMITIR_PARECER}),
    Papel.RESPONSAVEL_ETAPA: frozenset({Acao.EXECUTAR_ETAPA}),
}

# Coluna "Admin" da §3.7 — papel global (RN03), fora de qualquer evento.
DE_ADMINISTRADOR: frozenset[Acao] = frozenset(
    {
        Acao.APROVAR_SOLICITACAO_EVENTO,
        Acao.GERENCIAR_CONTAS,
        Acao.CONSULTAR_AUDITORIA,
        Acao.CONFIGURAR_EVENTO,
        Acao.DEFINIR_CRITERIOS_E_ETAPAS,
        Acao.ATRIBUIR_AVALIADORES,
        Acao.EMITIR_DECISAO,
    }
)


def pode(acao: Acao, papeis: Iterable[Papel], eh_administrador: bool) -> bool:
    """As tres regras da matriz, na ordem em que o front as aplica."""
    if acao in DE_AUTOR:
        return True

    if eh_administrador and acao in DE_ADMINISTRADOR:
        return True

    # Dois papeis no mesmo evento acumulam as permissoes dos dois.
    return any(acao in POR_PAPEL[papel] for papel in papeis)




def exige_autenticacao(rota: Callable) -> Callable:
    """Resolve o `Bearer`, carrega o usuario e deixa 401 para todo o resto."""

    @wraps(rota)
    def _guarda(*args, **kwargs):
        setattr(g, CHAVE_DO_USUARIO, _usuario_do_token())
        return rota(*args, **kwargs)

    return _guarda


def exige_acao(acao: Acao, *, evento_de: str | None = None) -> Callable:
    """403 `sem_permissao` quando o usuario nao pode a acao naquele evento.

    `evento_de` nomeia o parametro de rota que carrega o id do evento; sem ele a
    acao e global e so a coluna do administrador decide (rotas `/admin/*`).

    Autentica antes de autorizar, para que a distincao entre "nao sei quem e
    voce" (401) e "sei, e voce nao pode" (403) nao dependa de a rota lembrar de
    empilhar dois decoradores (API-09 AC3).

    A checagem acontece **antes** de a rota buscar o recurso: quem nao tem
    permissao recebe 403 mesmo para um id inexistente, e a resposta nao revela
    quais eventos existem (API-09 AC5).
    """

    def decorador(rota: Callable) -> Callable:
        @wraps(rota)
        def _guarda(*args, **kwargs):
            usuario = _usuario_do_token()
            setattr(g, CHAVE_DO_USUARIO, usuario)

            evento_id = None if evento_de is None else kwargs.get(evento_de)
            if not pode(
                acao, _papeis_no_evento(usuario, evento_id), bool(usuario.administrador)
            ):
                raise SemPermissao

            return rota(*args, **kwargs)

        return _guarda

    return decorador


def _papeis_no_evento(usuario: Usuario, evento_id: uuid.UUID | None) -> list[Papel]:
    if evento_id is None:
        return []
    return [
        Papel(valor)
        for valor in ParticipacaoRepository.papeis_no_evento(usuario.id, evento_id)
    ]


def usuario_autenticado() -> Usuario:
    """O usuario da requisicao corrente. So existe sob `@exige_autenticacao`."""
    return getattr(g, CHAVE_DO_USUARIO)


def _usuario_do_token() -> Usuario:
    try:
        verify_jwt_in_request()
        identidade = get_jwt_identity()
    except (JWTExtendedException, PyJWTError) as recusa:
        # Ausente, malformado, com assinatura invalida ou expirado: tudo isso e
        # uma unica resposta, e nenhuma delas revela qual foi (API-07 AC2).
        raise NaoAutenticado from recusa

    usuario = _por_identidade(identidade)

    # O token e valido por 15 minutos; a conta pode ter sido desativada ou
    # apagada nesse meio-tempo. A checagem acontece a cada requisicao, e nao so
    # no login: sem ela, um id obsoleto viraria 500 (risco R2, Edge Case).
    if usuario is None or not usuario.ativo:
        raise NaoAutenticado

    return usuario


def _por_identidade(identidade: object) -> Usuario | None:
    try:
        return ContaRepository.por_id(uuid.UUID(str(identidade)))
    except ValueError:
        # Identidade que nao e UUID nao pertence a nenhuma conta desta base.
        return None
