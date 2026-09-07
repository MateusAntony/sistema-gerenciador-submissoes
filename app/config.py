"""Configuracao derivada de `APP_ENV`, com falha explicita no boot (API-21 AC4, AC5).

Nada aqui e fixado no codigo por ambiente: o que muda entre desenvolvimento, teste e
producao sai de `APP_ENV`, e o que falta e nomeado no erro que derruba o boot — o
oposto do `SESSION_COOKIE_SECURE = False  # mudar em producao` que ninguem lembra de
trocar no deploy (risco R4).
"""

import os
from collections.abc import Mapping

AMBIENTES = ("development", "test", "production")
VARIAVEIS_OBRIGATORIAS = ("APP_ENV", "SECRET_KEY", "DATABASE_URL", "URL_DO_FRONT")
TAMANHO_MAXIMO_DE_CORPO_MB_PADRAO = 10
BACKENDS_DE_EMAIL = ("log", "smtp")
BACKEND_DE_EMAIL_PADRAO = "log"
CONTATO_DA_ORGANIZACAO_PADRAO = "contato@sgs.local"
VARIAVEIS_DE_SMTP = (
    "SMTP_HOST",
    "SMTP_PORTA",
    "SMTP_USUARIO",
    "SMTP_SENHA",
    "SMTP_REMETENTE",
)


def get_required_env(var_name: str, fonte: Mapping[str, str] | None = None) -> str:
    valor = (os.environ if fonte is None else fonte).get(var_name)
    if not valor:
        raise ValueError(
            f"A variável de ambiente obrigatória '{var_name}' não foi definida!"
        )
    return valor


class Config:
    """Conjunto de configuracao do ambiente corrente.

    `fonte` existe para o teste conseguir exercitar cada variavel ausente sem mexer no
    ambiente do processo.
    """

    def __init__(self, fonte: Mapping[str, str] | None = None) -> None:
        fonte = os.environ if fonte is None else fonte

        self.APP_ENV = self._ambiente(fonte)
        self.SECRET_KEY = get_required_env("SECRET_KEY", fonte)
        self.SQLALCHEMY_DATABASE_URI = get_required_env("DATABASE_URL", fonte)
        self.URL_DO_FRONT = get_required_env("URL_DO_FRONT", fonte)
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False

        # Backend de e-mail escolhido no boot (AD-010). SMTP sem configuracao
        # completa derruba o boot; nunca cai em silencio no log (API-10 AC4).
        self.EMAIL_BACKEND = self._backend_de_email(fonte)
        self.SMTP = (
            {nome: get_required_env(nome, fonte) for nome in VARIAVEIS_DE_SMTP}
            if self.EMAIL_BACKEND == "smtp"
            else None
        )

        # Endereco oferecido a quem abre um convite invalido, expirado ou ja
        # usado (API-08 AC2..AC4): nesses tres casos nao ha convite de onde
        # tira-lo, entao ele precisa existir fora deles.
        self.CONTATO_DA_ORGANIZACAO = (
            fonte.get("CONTATO_DA_ORGANIZACAO") or CONTATO_DA_ORGANIZACAO_PADRAO
        )

        producao = self.APP_ENV == "production"
        if producao and not self.URL_DO_FRONT.startswith("https://"):
            raise ValueError(
                "A variável de ambiente 'URL_DO_FRONT' precisa declarar HTTPS "
                "(https://...) quando 'APP_ENV' é 'production'."
            )

        self.DEBUG = self.APP_ENV == "development"
        self.TESTING = self.APP_ENV == "test"

        # Vale para o cookie de sessao do Flask e para o de renovacao (API-03 AC5).
        self.COOKIE_SEGURO = producao
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SAMESITE = "Lax"
        self.SESSION_COOKIE_SECURE = producao

        # Corpo maior que o limite vira 413 no tratador central (risco R10).
        self.TAMANHO_MAXIMO_DE_CORPO_MB = int(
            fonte.get("TAMANHO_MAXIMO_DE_CORPO_MB")
            or TAMANHO_MAXIMO_DE_CORPO_MB_PADRAO
        )
        self.MAX_CONTENT_LENGTH = self.TAMANHO_MAXIMO_DE_CORPO_MB * 1024 * 1024

    @staticmethod
    def _ambiente(fonte: Mapping[str, str]) -> str:
        ambiente = get_required_env("APP_ENV", fonte)
        if ambiente not in AMBIENTES:
            raise ValueError(
                f"A variável de ambiente 'APP_ENV' precisa ser uma de "
                f"{', '.join(AMBIENTES)}; recebido '{ambiente}'."
            )
        return ambiente

    @staticmethod
    def _backend_de_email(fonte: Mapping[str, str]) -> str:
        backend = fonte.get("EMAIL_BACKEND") or BACKEND_DE_EMAIL_PADRAO
        if backend not in BACKENDS_DE_EMAIL:
            raise ValueError(
                f"A variável de ambiente 'EMAIL_BACKEND' precisa ser uma de "
                f"{', '.join(BACKENDS_DE_EMAIL)}; recebido '{backend}'."
            )
        return backend
