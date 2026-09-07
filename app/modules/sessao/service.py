"""Regras de sessao: emissao, rotacao com deteccao de reuso e encerramento.

O token de renovacao e um segredo opaco; o banco guarda **so o SHA-256** dele
(AD-017). Toda rotacao de um mesmo login compartilha uma `familia`: reapresentar
um token ja rotacionado e sinal de roubo e derruba a familia inteira (API-04 AC3).
"""

import math
import secrets
import uuid
from datetime import datetime, timedelta

from flask_jwt_extended import create_access_token
from sqlalchemy import func, select

from app.core.erros import ErroDaApi
from app.extensions import bcrypt, db
from app.modules.contas.models import Usuario
from app.modules.contas.repository import ContaRepository

# O relogio e o hash de token de vida longa ja tem uma definicao no projeto
# (AD-017); duas seriam duas verdades sobre o mesmo segredo.
from app.modules.contas.service import agora, hash_do_token
from app.modules.sessao.models import Sessao, TentativaLogin
from app.modules.sessao.repository import SessaoRepository

VALIDADE_DO_TOKEN_DE_ACESSO_EM_MINUTOS = 15
VALIDADE_DA_RENOVACAO_EM_DIAS = 14
TAMANHO_DO_TOKEN_EM_BYTES = 32

JANELA_DE_TENTATIVAS_EM_MINUTOS = 15
MAXIMO_DE_TENTATIVAS_FALHAS = 10

MENSAGEM_DE_CREDENCIAIS_INVALIDAS = "E-mail ou senha inválidos"
MENSAGEM_DE_CONTA_DESATIVADA = (
    "Conta desativada. Procure o administrador do sistema"
)
MENSAGEM_DE_EMAIL_NAO_CONFIRMADO = "Confirme seu e-mail para entrar no sistema."
MENSAGEM_DE_MUITAS_TENTATIVAS = (
    "Muitas tentativas de login para este e-mail. Tente de novo mais tarde."
)

# Hash bcrypt de um valor aleatorio descartado, que nenhuma senha abre. Serve so
# para que o e-mail inexistente pague a mesma verificacao que a senha errada: sem
# ele, a resposta mais rapida diria quais e-mails tem conta, e o 401 unico de
# API-03 AC2 viraria um oraculo de enumeracao medido pelo relogio.
HASH_DE_COMPARACAO_EM_VAZIO = (
    "$2b$12$CqndgsxRNdldMyEEK97jO.uTZAc3RkmrLJwV64JGWmTjQP/Ccb4Je"
)


class MuitasTentativas(ErroDaApi):
    """429 com `Retry-After` em segundos (API-20 AC1)."""

    codigo = "muitas_tentativas"
    status = 429
    mensagem = MENSAGEM_DE_MUITAS_TENTATIVAS

    def __init__(self, segundos: int) -> None:
        super().__init__()
        self.cabecalhos = {"Retry-After": str(segundos)}


class SessaoService:
    @staticmethod
    def autenticar(email: str, senha: str) -> tuple[Usuario | None, ErroDaApi | None]:
        """Confere as credenciais e devolve `(usuario, falha)` (API-03 AC1..AC4, AC6).

        A falha volta como valor em vez de excecao para que o controller possa
        fechar a transacao antes de levanta-la — o registro da tentativa (API-20)
        precisa sobreviver a uma resposta de erro.
        """
        espera = SessaoService._espera_por_excesso_de_tentativas(email)
        if espera is not None:
            return None, MuitasTentativas(espera)

        usuario = ContaRepository.por_email(email)

        # A verificacao acontece mesmo sem conta, contra um hash que nada abre:
        # os dois caminhos de 401 custam o mesmo (API-03 AC2, AC6).
        senha_confere = bcrypt.check_password_hash(
            HASH_DE_COMPARACAO_EM_VAZIO if usuario is None else usuario.senha_hash,
            senha,
        )

        if usuario is None or not senha_confere:
            # A tentativa e registrada para qualquer e-mail, exista ou nao conta:
            # so assim o 429 nao denuncia quais enderecos estao cadastrados.
            SessaoService._registrar_tentativa(email, sucesso=False)
            return None, ErroDaApi(
                MENSAGEM_DE_CREDENCIAIS_INVALIDAS,
                codigo="credenciais_invalidas",
                status=401,
            )
        if not usuario.ativo:
            return None, ErroDaApi(
                MENSAGEM_DE_CONTA_DESATIVADA,
                codigo="conta_desativada",
                status=403,
            )
        if not usuario.email_confirmado:
            return None, ErroDaApi(
                MENSAGEM_DE_EMAIL_NAO_CONFIRMADO,
                codigo="email_nao_confirmado",
                status=403,
            )

        SessaoService._registrar_tentativa(email, sucesso=True)
        return usuario, None

    @staticmethod
    def _registrar_tentativa(email: str, *, sucesso: bool) -> None:
        # O instante vem do relogio da aplicacao, e nao de `now()` do banco, que
        # dentro de uma transacao devolve sempre o inicio dela.
        db.session.add(
            TentativaLogin(email=email, sucesso=sucesso, ocorrido_em=agora())
        )
        db.session.flush()

    @staticmethod
    def _espera_por_excesso_de_tentativas(email: str) -> int | None:
        """Segundos ate a janela liberar, ou `None` se ainda ha folga."""
        falhas = SessaoService._falhas_que_ainda_contam(email)
        if len(falhas) < MAXIMO_DE_TENTATIVAS_FALHAS:
            return None

        # A janela abre quando a falha mais antiga que ainda conta sai dela.
        libera_em = falhas[0] + timedelta(minutes=JANELA_DE_TENTATIVAS_EM_MINUTOS)
        return max(1, math.ceil((libera_em - agora()).total_seconds()))

    @staticmethod
    def _falhas_que_ainda_contam(email: str) -> list[datetime]:
        """Falhas dentro da janela e posteriores ao ultimo sucesso.

        Recortar pelo ultimo sucesso e o que zera o contador quando o login da
        certo (API-20 AC2) sem apagar o historico de tentativas; recortar pela
        janela e o que o zera com o tempo (AC3).
        """
        inicio_da_janela = agora() - timedelta(
            minutes=JANELA_DE_TENTATIVAS_EM_MINUTOS
        )
        ultimo_sucesso = db.session.scalar(
            select(func.max(TentativaLogin.ocorrido_em)).where(
                TentativaLogin.email == email,
                TentativaLogin.sucesso.is_(True),
            )
        )

        condicoes = [
            TentativaLogin.email == email,
            TentativaLogin.sucesso.is_(False),
            TentativaLogin.ocorrido_em >= inicio_da_janela,
        ]
        if ultimo_sucesso is not None:
            condicoes.append(TentativaLogin.ocorrido_em > ultimo_sucesso)

        return list(
            db.session.scalars(
                select(TentativaLogin.ocorrido_em)
                .where(*condicoes)
                .order_by(TentativaLogin.ocorrido_em)
            )
        )

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
