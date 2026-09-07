"""Backends de entrega de e-mail, escolhidos no boot (AD-010, API-10).

O backend de log existe para o fluxo de confirmacao fechar sem servidor de e-mail
configurado: a mensagem vai para o log e para `emails_enviados`, sem tocar a rede.
"""

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

CHAVE_DO_BACKEND = "backend_de_email"


class BackendDeLog:
    """Escreve a mensagem inteira no log — inclusive o link e o token."""

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        logger.info(
            "E-mail para %s | assunto: %s\n%s", destinatario, assunto, corpo
        )


class BackendSmtp:
    def __init__(self, smtp: dict[str, str]) -> None:
        self._smtp = smtp

    def enviar(self, destinatario: str, assunto: str, corpo: str) -> None:
        mensagem = EmailMessage()
        mensagem["From"] = self._smtp["SMTP_REMETENTE"]
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        mensagem.set_content(corpo)

        with smtplib.SMTP(
            self._smtp["SMTP_HOST"], int(self._smtp["SMTP_PORTA"])
        ) as servidor:
            servidor.starttls()
            servidor.login(self._smtp["SMTP_USUARIO"], self._smtp["SMTP_SENHA"])
            servidor.send_message(mensagem)


def criar_backend(config) -> BackendDeLog | BackendSmtp:
    """O backend sai da configuracao, que ja falhou no boot se estiver incompleta."""
    if config["EMAIL_BACKEND"] == "smtp":
        return BackendSmtp(config["SMTP"])
    return BackendDeLog()
