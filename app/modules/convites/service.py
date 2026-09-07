"""Regras dos convites por token: criacao, consulta e aceite.

O banco guarda **so o SHA-256** do token (AD-017); o valor cru existe apenas na
URL que viaja no e-mail. Perder essa URL e perder o convite — de proposito.
"""

import secrets
from datetime import timedelta

from flask import current_app

from app.modules.contas.service import agora, hash_do_token
from app.modules.convites.models import Convite
from app.modules.convites.repository import ConviteRepository
from app.modules.emails.service import EmailService
from app.modules.eventos.models import Evento

TIPO_DE_PARTICIPACAO = "participacao"
TIPO_DE_AVALIACAO = "avaliacao"

VALIDADE_DO_CONVITE_EM_DIAS = 14
TAMANHO_DO_TOKEN_EM_BYTES = 32


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
