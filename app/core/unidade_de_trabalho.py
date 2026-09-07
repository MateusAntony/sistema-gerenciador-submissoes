"""Uma transacao por requisicao, com commit unico no fim (AD-019, risco R1).

`db.session.commit()` acontece **so aqui**. E o que faz uma operacao composta —
aprovar solicitacao cria evento, participacoes e convites — ser atomica sem esforco
(API-13 AC4): se qualquer etapa falha, nada e gravado.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.extensions import db


@contextmanager
def transacao() -> Iterator[Session]:
    try:
        yield db.session
    except Exception:
        db.session.rollback()
        raise
    db.session.commit()
