"""Acesso a dados do dominio de contas.

Nenhum metodo daqui comita: o commit e da unidade de trabalho (AD-019, risco R1).
O `flush` existe so para o banco atribuir o id antes de a requisicao terminar.
"""

import uuid

from sqlalchemy import select

from app.extensions import db
from app.modules.contas.models import Usuario


class ContaRepository:
    @staticmethod
    def por_email(email: str) -> Usuario | None:
        return db.session.scalars(
            select(Usuario).where(Usuario.email == email)
        ).first()

    @staticmethod
    def por_id(usuario_id: uuid.UUID) -> Usuario | None:
        return db.session.get(Usuario, usuario_id)

    @staticmethod
    def criar(
        nome: str,
        email: str,
        senha_hash: str,
        instituicao: str | None = None,
        pais: str | None = None,
    ) -> Usuario:
        usuario = Usuario(
            nome=nome,
            email=email,
            senha_hash=senha_hash,
            instituicao=instituicao,
            pais=pais,
        )
        db.session.add(usuario)
        db.session.flush()
        return usuario
