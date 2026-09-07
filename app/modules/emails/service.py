"""Entrega de e-mail com registro de toda tentativa (API-10).

`enviar` nunca levanta excecao para quem chama: falha de entrega vira registro com
situacao `falha` e a operacao de negocio conclui (API-10 AC2).
"""

import logging

from flask import current_app

from app.extensions import db
from app.modules.emails.backends import CHAVE_DO_BACKEND
from app.modules.emails.models import EmailEnviado

logger = logging.getLogger(__name__)

ASSUNTO_DE_CONFIRMACAO = "Confirme seu e-mail"
CAMINHO_DE_CONFIRMACAO = "/confirmar-email"


def url_de_confirmacao(token: str) -> str:
    """URL completa que o e-mail carrega, montada da origem do front (API-10 AC3)."""
    origem = current_app.config["URL_DO_FRONT"].rstrip("/")
    return f"{origem}{CAMINHO_DE_CONFIRMACAO}?token={token}"


def corpo_de_confirmacao(token: str) -> str:
    return (
        "Confirme seu e-mail para concluir o cadastro no SGS.\n\n"
        f"{url_de_confirmacao(token)}\n\n"
        "O link vale por 24 horas. Se não foi você, ignore esta mensagem."
    )


class EmailService:
    @staticmethod
    def enviar(destinatario: str, assunto: str, corpo: str) -> EmailEnviado:
        registro = EmailEnviado(
            destinatario=destinatario,
            assunto=assunto,
            corpo=corpo,
            situacao="enviado",
        )
        try:
            current_app.extensions[CHAVE_DO_BACKEND].enviar(
                destinatario, assunto, corpo
            )
        # API-10 AC2 exige que **nenhuma** falha de entrega chegue ao chamador;
        # restringir os tipos aqui deixaria o cadastro cair por causa do e-mail.
        except Exception as falha:  # noqa: BLE001
            registro.situacao = "falha"
            registro.erro = str(falha)
            logger.warning(
                "Falha ao entregar e-mail para %s: %s", destinatario, falha
            )

        db.session.add(registro)
        db.session.flush()
        return registro

    @staticmethod
    def enviar_confirmacao_de_email(destinatario: str, token: str) -> EmailEnviado:
        return EmailService.enviar(
            destinatario, ASSUNTO_DE_CONFIRMACAO, corpo_de_confirmacao(token)
        )
