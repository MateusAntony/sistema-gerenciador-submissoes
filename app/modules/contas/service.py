"""Regras do dominio de contas: cadastro e confirmacao de e-mail."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.erros import Conflito, ErroDaApi, NaoEncontrado
from app.extensions import bcrypt, db
from app.modules.contas.models import TokenConfirmacaoEmail, Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.contas.schemas import CadastroDeConta
from app.modules.emails.service import EmailService

CONSTRAINT_DE_EMAIL = "usuarios_email_key"
MENSAGEM_DE_EMAIL_EXISTENTE = "Já existe uma conta com este e-mail"
MENSAGEM_DE_TOKEN_INVALIDO = "Este link de confirmação não é válido."
MENSAGEM_DE_TOKEN_EXPIRADO = "Este link de confirmação expirou."
MENSAGEM_DE_TOKEN_JA_USADO = "Este link de confirmação já foi utilizado."

VALIDADE_DO_TOKEN_EM_HORAS = 24
TAMANHO_DO_TOKEN_EM_BYTES = 32


def agora() -> datetime:
    return datetime.now(timezone.utc)


def hash_do_token(token: str) -> str:
    """SHA-256 do token — a unica forma dele que o banco conhece (AD-017)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _e_colisao_de_email(erro: IntegrityError) -> bool:
    restricao = getattr(getattr(erro.orig, "diag", None), "constraint_name", None)
    return restricao == CONSTRAINT_DE_EMAIL or CONSTRAINT_DE_EMAIL in str(erro.orig)


class ContaService:
    @staticmethod
    def criar(dados: CadastroDeConta) -> Usuario:
        if ContaRepository.por_email(dados.email) is not None:
            raise Conflito("email_existente", MENSAGEM_DE_EMAIL_EXISTENTE)

        try:
            usuario = ContaRepository.criar(
                nome=dados.nome,
                email=dados.email,
                senha_hash=bcrypt.generate_password_hash(dados.senha).decode("utf-8"),
                instituicao=dados.instituicao,
                pais=dados.pais,
            )
        except IntegrityError as colisao:
            # Dois cadastros simultaneos passam pela checagem acima ao mesmo tempo;
            # quem perde a corrida so descobre na constraint unica. Isso e 409, nao
            # 500 (Edge Case da spec).
            db.session.rollback()
            if not _e_colisao_de_email(colisao):
                raise
            raise Conflito(
                "email_existente", MENSAGEM_DE_EMAIL_EXISTENTE
            ) from colisao

        token = ContaService.emitir_token_de_confirmacao(usuario)
        EmailService.enviar_confirmacao_de_email(usuario.email, token)
        return usuario

    @staticmethod
    def emitir_token_de_confirmacao(usuario: Usuario) -> str:
        """Emite um token novo e devolve o valor **cru**, que so viaja no e-mail.

        Emitir de novo nao apaga nem invalida o token anterior: os dois ficam
        registrados e pendentes ate serem usados ou expirarem (API-06 AC7).
        """
        token = secrets.token_urlsafe(TAMANHO_DO_TOKEN_EM_BYTES)
        emitido_em = agora()

        db.session.add(
            TokenConfirmacaoEmail(
                usuario_id=usuario.id,
                token_hash=hash_do_token(token),
                expira_em=emitido_em
                + timedelta(hours=VALIDADE_DO_TOKEN_EM_HORAS),
                criado_em=emitido_em,
            )
        )
        db.session.flush()
        return token

    @staticmethod
    def confirmar_email(token: str) -> str:
        """Confirma a conta e devolve o e-mail confirmado (API-06 AC1..AC4)."""
        registro = db.session.scalars(
            select(TokenConfirmacaoEmail).where(
                TokenConfirmacaoEmail.token_hash == hash_do_token(token)
            )
        ).first()

        if registro is None:
            raise NaoEncontrado("token_invalido", MENSAGEM_DE_TOKEN_INVALIDO)
        if registro.usado_em is not None:
            raise Conflito("token_ja_usado", MENSAGEM_DE_TOKEN_JA_USADO)
        if registro.expira_em <= agora():
            raise ErroDaApi(
                MENSAGEM_DE_TOKEN_EXPIRADO, codigo="token_expirado", status=410
            )

        registro.usado_em = agora()
        usuario = ContaRepository.por_id(registro.usuario_id)
        usuario.email_confirmado = True
        db.session.flush()
        return usuario.email
