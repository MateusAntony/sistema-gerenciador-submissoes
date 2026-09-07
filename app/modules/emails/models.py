"""Model do dominio de e-mail: registro de toda tentativa de envio (API-10 AC1)."""

from app.extensions import db
from app.modules.colunas import chave_primaria, criado_em
from app.modules.enums import email_situacao_enum


class EmailEnviado(db.Model):
    __tablename__ = "emails_enviados"

    id = chave_primaria()
    destinatario = db.Column(db.String(255), nullable=False)
    assunto = db.Column(db.Text)
    corpo = db.Column(db.Text)
    situacao = db.Column(email_situacao_enum, nullable=False)
    erro = db.Column(db.Text)
    criado_em = criado_em()
