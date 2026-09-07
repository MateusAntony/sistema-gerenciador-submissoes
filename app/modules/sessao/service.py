"""Regras de sessao: emissao, rotacao com deteccao de reuso e encerramento.

O token de renovacao e um segredo opaco; o banco guarda **so o SHA-256** dele
(AD-017). Toda rotacao de um mesmo login compartilha uma `familia`: reapresentar
um token ja rotacionado e sinal de roubo e derruba a familia inteira (API-04 AC3).
"""

import secrets
import uuid
from datetime import datetime, timedelta

from flask_jwt_extended import create_access_token

from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository

# O relogio e o hash de token de vida longa ja tem uma definicao no projeto
# (AD-017); duas seriam duas verdades sobre o mesmo segredo.
from app.modules.contas.service import agora, hash_do_token
from app.modules.sessao.models import Sessao
from app.modules.sessao.repository import SessaoRepository

VALIDADE_DO_TOKEN_DE_ACESSO_EM_MINUTOS = 15
VALIDADE_DA_RENOVACAO_EM_DIAS = 14
TAMANHO_DO_TOKEN_EM_BYTES = 32


class SessaoService:
    @staticmethod
    def token_de_acesso(usuario: Usuario) -> str:
        """JWT de acesso curto, devolvido no corpo e guardado em memoria (AD-002)."""
        return create_access_token(
            identity=str(usuario.id),
            expires_delta=timedelta(
                minutes=VALIDADE_DO_TOKEN_DE_ACESSO_EM_MINUTOS
            ),
        )

    @staticmethod
    def emitir(usuario: Usuario) -> str:
        """Abre uma familia nova e devolve o token **cru**, que so vive no cookie."""
        return SessaoService._gravar(usuario.id, uuid.uuid4())

    @staticmethod
    def renovar(token: str | None) -> tuple[str, str] | None:
        """Rotaciona a sessao e devolve `(token de acesso, token de renovacao)`.

        Devolve `None` quando a renovacao nao pode acontecer — ausente, desconhecida,
        expirada, revogada ou ja rotacionada. A falha e um desfecho esperado deste
        fluxo, nao uma excecao: quando ela vem de reuso, a revogacao da familia
        precisa ser **gravada** junto, e uma excecao desfaria a transacao que a
        carrega.
        """
        registro = SessaoService._registro(token)
        if registro is None:
            return None

        if registro.rotacionado_em is not None or registro.revogada_em is not None:
            # Reuso: o dono legitimo ja trocou este token por outro. Quem o
            # apresenta agora tem uma copia — a sessao inteira cai (API-04 AC3).
            SessaoRepository.revogar_familia(registro.familia, agora())
            return None

        if registro.expira_em <= agora():
            return None

        usuario = ContaRepository.por_id(registro.usuario_id)
        if usuario is None or not usuario.ativo:
            return None

        registro.rotacionado_em = agora()
        renovacao = SessaoService._gravar(usuario.id, registro.familia)
        return SessaoService.token_de_acesso(usuario), renovacao

    @staticmethod
    def encerrar(token: str | None) -> None:
        """Derruba a sessao. Idempotente: sem token valido, nao ha o que fazer."""
        registro = SessaoService._registro(token)
        if registro is not None:
            SessaoRepository.revogar_familia(registro.familia, agora())

    @staticmethod
    def _registro(token: str | None) -> Sessao | None:
        if not token:
            return None
        return SessaoRepository.por_hash(hash_do_token(token))

    @staticmethod
    def _gravar(usuario_id: uuid.UUID, familia: uuid.UUID) -> str:
        token = secrets.token_urlsafe(TAMANHO_DO_TOKEN_EM_BYTES)
        SessaoRepository.criar(
            usuario_id=usuario_id,
            familia=familia,
            token_hash=hash_do_token(token),
            expira_em=SessaoService._expiracao_da_renovacao(),
        )
        return token

    @staticmethod
    def _expiracao_da_renovacao() -> datetime:
        return agora() + timedelta(days=VALIDADE_DA_RENOVACAO_EM_DIAS)
