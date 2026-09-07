"""Regras do dominio de contas: cadastro e confirmacao de e-mail."""

from sqlalchemy.exc import IntegrityError

from app.core.erros import Conflito
from app.extensions import bcrypt, db
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository
from app.modules.contas.schemas import CadastroDeConta
from app.modules.emails.service import EmailService

CONSTRAINT_DE_EMAIL = "usuarios_email_key"
MENSAGEM_DE_EMAIL_EXISTENTE = "Já existe uma conta com este e-mail"


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

        EmailService.enviar_confirmacao_de_email(usuario.email, "")
        return usuario
