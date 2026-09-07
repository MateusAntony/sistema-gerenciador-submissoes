"""Regras dos convites por token: criacao, consulta e aceite.

O banco guarda **so o SHA-256** do token (AD-017); o valor cru existe apenas na
URL que viaja no e-mail. Perder essa URL e perder o convite — de proposito.
"""

import secrets
from datetime import timedelta

from flask import current_app

from app.core.erros import Conflito, ErroDaApi, NaoEncontrado
from app.modules.contas.repository import ContaRepository
from app.modules.contas.service import agora, hash_do_token
from app.modules.convites.models import Convite
from app.modules.convites.repository import ConviteRepository
from app.modules.convites.schemas import ConviteDaApi
from app.modules.emails.service import EmailService
from app.modules.eventos.models import Evento

TIPO_DE_PARTICIPACAO = "participacao"
TIPO_DE_AVALIACAO = "avaliacao"

SITUACAO_PENDENTE = "pendente"
SITUACAO_ACEITO = "aceito"
SITUACAO_EXPIRADO = "expirado"

VALIDADE_DO_CONVITE_EM_DIAS = 14
TAMANHO_DO_TOKEN_EM_BYTES = 32

MENSAGEM_DE_CONVITE_INVALIDO = "Este convite não é válido."
MENSAGEM_DE_CONVITE_EXPIRADO = "Este convite expirou."
MENSAGEM_DE_CONVITE_JA_USADO = "Este convite já foi utilizado."

# O contato viaja **no corpo do erro**, ao lado de `codigo` e `mensagem`, e nunca
# dentro de `campos` — `campos` significa erro por campo de formulario (D4).
CHAVE_DO_CONTATO = "contatoDaOrganizacao"


def contato_da_organizacao(convite: Convite | None = None) -> str:
    """O contato do convite, ou o da instalacao quando nao ha convite (AC2)."""
    do_convite = None if convite is None else convite.contato_organizacao
    return do_convite or current_app.config["CONTATO_DA_ORGANIZACAO"]


class ConviteService:
    @staticmethod
    def criar_para_participacao(
        evento: Evento, email: str, papel: str
    ) -> tuple[Convite, str]:
        """Convite de `participacao` — **sem** submissao (D3).

        Devolve o convite e o token **cru**, para quem chama poder testar a URL
        que foi enviada; a chamada real da aprovacao de evento (Fase 5) so
        precisa do convite.
        """
        token = secrets.token_urlsafe(TAMANHO_DO_TOKEN_EM_BYTES)

        convite = ConviteRepository.criar(
            token_hash=hash_do_token(token),
            tipo=TIPO_DE_PARTICIPACAO,
            email=email,
            evento_id=evento.id,
            papel=papel,
            prazo=agora() + timedelta(days=VALIDADE_DO_CONVITE_EM_DIAS),
            contato_organizacao=current_app.config["CONTATO_DA_ORGANIZACAO"],
        )

        EmailService.enviar_convite(email, token, evento.titulo)
        return convite, token

    @staticmethod
    def consultar(token: str) -> Convite:
        """O convite pendente do token, ou o erro que explica por que nao ha um.

        `aceito` e conferido antes do prazo: um convite ja usado continua
        respondendo 409 depois de a data passar, e e isso que faz o aceite
        repetido ter sempre o mesmo desfecho (API-08 AC4, AC9).
        """
        convite = ConviteRepository.por_hash(hash_do_token(token))

        if convite is None:
            raise NaoEncontrado(
                "convite_invalido",
                MENSAGEM_DE_CONVITE_INVALIDO,
                **{CHAVE_DO_CONTATO: contato_da_organizacao()},
            )

        if convite.situacao == SITUACAO_ACEITO:
            raise Conflito(
                "convite_ja_usado",
                MENSAGEM_DE_CONVITE_JA_USADO,
                **{CHAVE_DO_CONTATO: contato_da_organizacao(convite)},
            )

        if ConviteService._venceu(convite):
            raise ErroDaApi(
                MENSAGEM_DE_CONVITE_EXPIRADO,
                codigo="convite_expirado",
                status=410,
                **{CHAVE_DO_CONTATO: contato_da_organizacao(convite)},
            )

        return convite

    @staticmethod
    def projetar(convite: Convite) -> ConviteDaApi:
        """O convite como o contrato o expoe, sem exigir sessao (API-08 AC1)."""
        return ConviteDaApi(
            tipo=convite.tipo,
            email=convite.email,
            evento_titulo=convite.evento.titulo,
            submissao_titulo=convite.submissao_titulo,
            prazo=convite.prazo,
            fuso=convite.evento.fuso,
            contato_da_organizacao=contato_da_organizacao(convite),
            precisa_criar_conta=ContaRepository.por_email(convite.email) is None,
        )

    @staticmethod
    def _venceu(convite: Convite) -> bool:
        return convite.situacao == SITUACAO_EXPIRADO or (
            convite.prazo is not None and convite.prazo <= agora()
        )
