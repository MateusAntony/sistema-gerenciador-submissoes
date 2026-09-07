"""Modulos por dominio (AD-016).

Importar este pacote registra todos os models no metadata do SQLAlchemy — e o que faz o
Alembic enxergar o schema inteiro ao gerar e aplicar migrations.
"""

from app.models.user import Usuario  # noqa: F401
from app.modules.areas_futuras.models import (  # noqa: F401
    FaseEvento,
    FormularioChamada,
    NotaParecer,
    Submissao,
)
from app.modules.contas.models import TokenConfirmacaoEmail  # noqa: F401
from app.modules.convites.models import Convite  # noqa: F401
from app.modules.emails.models import EmailEnviado  # noqa: F401
from app.modules.eventos.models import (  # noqa: F401
    Chamada,
    CriterioAvaliacao,
    Evento,
    ParticipacaoEvento,
    SolicitacaoChairInicial,
    SolicitacaoEvento,
    Trilha,
)
from app.modules.sessao.models import Sessao, TentativaLogin  # noqa: F401
