"""Models do dominio de eventos e chamadas."""

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db
from app.modules.colunas import chave_estrangeira, chave_primaria, criado_em, momento
from app.modules.enums import (
    evento_situacao_enum,
    evento_tipo_enum,
    modelo_avaliacao_enum,
    papel_enum,
    solicitacao_situacao_enum,
)


class SolicitacaoEvento(db.Model):
    __tablename__ = "solicitacoes_evento"

    id = chave_primaria()
    solicitante_id = chave_estrangeira("usuarios.id", nullable=False)
    situacao = db.Column(
        solicitacao_situacao_enum, nullable=False, server_default="pendente"
    )
    decidido_por_id = chave_estrangeira("usuarios.id")
    decidido_em = momento()
    motivo_recusa = db.Column(db.Text)
    titulo = db.Column(db.String(300), nullable=False)
    sigla = db.Column(db.String(50))
    ano = db.Column(db.Integer, nullable=False)
    identificador_pagina = db.Column(db.String(100), nullable=False, unique=True)
    tipo = db.Column(evento_tipo_enum)
    cidade = db.Column(db.String(120))
    estado = db.Column(db.String(120))
    pais = db.Column(db.String(100))
    fuso = db.Column(db.String(60))
    data_inicio = db.Column(db.Date)
    data_termino = db.Column(db.Date)
    data_publicacao = db.Column(db.Date)
    justificativa = db.Column(db.Text)
    evento_pai_id = chave_estrangeira(
        "eventos.id", use_alter=True, name="fk_solicitacoes_evento_evento_pai_id"
    )
    versao = db.Column(db.Integer, nullable=False, server_default="1")
    criado_em = criado_em()


class SolicitacaoChairInicial(db.Model):
    __tablename__ = "solicitacao_chairs_iniciais"

    id = chave_primaria()
    solicitacao_id = chave_estrangeira(
        "solicitacoes_evento.id", ondelete="CASCADE", nullable=False
    )
    email = db.Column(db.String(255), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "solicitacao_id", "email", name="uq_solicitacao_chairs_iniciais_email"
        ),
    )


class Evento(db.Model):
    __tablename__ = "eventos"

    id = chave_primaria()
    solicitacao_id = chave_estrangeira("solicitacoes_evento.id")
    situacao = db.Column(evento_situacao_enum, nullable=False)
    titulo = db.Column(db.String(300), nullable=False)
    sigla = db.Column(db.String(50))
    ano = db.Column(db.Integer, nullable=False)
    identificador_pagina = db.Column(db.String(100), nullable=False, unique=True)
    tipo = db.Column(evento_tipo_enum)
    cidade = db.Column(db.String(120))
    estado = db.Column(db.String(120))
    pais = db.Column(db.String(100))
    fuso = db.Column(db.String(60))
    data_inicio = db.Column(db.Date)
    data_termino = db.Column(db.Date)
    data_publicacao = db.Column(db.Date)
    site = db.Column(db.String(300))
    evento_pai_id = chave_estrangeira("eventos.id")
    modelo_avaliacao = db.Column(
        modelo_avaliacao_enum, nullable=False, server_default="aberta"
    )
    avaliadores_por_submissao = db.Column(
        db.Integer, nullable=False, server_default="1"
    )
    rebuttal_habilitado = db.Column(
        db.Boolean, nullable=False, server_default=db.false()
    )
    prazo_rebuttal_dias = db.Column(db.Integer)
    maximo_rodadas = db.Column(db.Integer, nullable=False, server_default="1")
    nota_corte = db.Column(db.Numeric(5, 2))
    limite_submissoes_por_autor = db.Column(db.Integer)
    versao = db.Column(db.Integer, nullable=False, server_default="1")
    criado_em = criado_em()
    atualizado_em = momento(nullable=False, server_default=db.func.now())

    __table_args__ = (
        db.CheckConstraint(
            "avaliadores_por_submissao >= 1",
            name="ck_eventos_avaliadores_por_submissao",
        ),
        db.CheckConstraint("maximo_rodadas >= 1", name="ck_eventos_maximo_rodadas"),
        db.CheckConstraint(
            "NOT rebuttal_habilitado OR prazo_rebuttal_dias IS NOT NULL",
            name="ck_eventos_rebuttal_com_prazo",
        ),
    )


class ParticipacaoEvento(db.Model):
    __tablename__ = "participacoes_evento"

    id = chave_primaria()
    evento_id = chave_estrangeira(
        "eventos.id", ondelete="CASCADE", nullable=False
    )
    usuario_id = chave_estrangeira(
        "usuarios.id", ondelete="CASCADE", nullable=False
    )
    papel = db.Column(papel_enum, nullable=False)
    areas_interesse = db.Column(db.Text)
    ativo = db.Column(db.Boolean, nullable=False, server_default=db.true())
    criado_em = criado_em()

    __table_args__ = (
        db.UniqueConstraint(
            "evento_id", "usuario_id", "papel", name="uq_participacao_evento_papel"
        ),
    )


class Trilha(db.Model):
    __tablename__ = "trilhas"

    id = chave_primaria()
    evento_id = chave_estrangeira(
        "eventos.id", ondelete="CASCADE", nullable=False
    )
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    ativa = db.Column(db.Boolean, nullable=False, server_default=db.true())
    criado_em = criado_em()

    __table_args__ = (
        db.UniqueConstraint("evento_id", "nome", name="uq_trilhas_evento_nome"),
    )


class Chamada(db.Model):
    __tablename__ = "chamadas"

    id = chave_primaria()
    evento_id = chave_estrangeira(
        "eventos.id", ondelete="CASCADE", nullable=False
    )
    trilha_id = chave_estrangeira("trilhas.id")
    titulo = db.Column(db.String(300), nullable=False)
    data_abertura = momento(nullable=False)
    data_limite = momento(nullable=False)
    permite_submissao_apos_prazo = db.Column(
        db.Boolean, nullable=False, server_default=db.false()
    )
    formatos_aceitos = db.Column(JSONB, nullable=False, server_default="[]")
    tamanho_maximo_mb = db.Column(db.Integer)
    encerrada_manualmente = db.Column(
        db.Boolean, nullable=False, server_default=db.false()
    )
    versao = db.Column(db.Integer, nullable=False, server_default="1")
    criado_em = criado_em()

    __table_args__ = (
        db.CheckConstraint(
            "data_limite > data_abertura", name="ck_chamadas_data_limite_apos_abertura"
        ),
    )


class CriterioAvaliacao(db.Model):
    __tablename__ = "criterios_avaliacao"

    id = chave_primaria()
    evento_id = chave_estrangeira(
        "eventos.id", ondelete="CASCADE", nullable=False
    )
    titulo = db.Column(db.String(300), nullable=False)
    descricao = db.Column(db.Text)
    nota_minima = db.Column(db.Numeric(5, 2), nullable=False)
    nota_maxima = db.Column(db.Numeric(5, 2), nullable=False)
    peso = db.Column(db.Numeric(5, 2), nullable=False)
    ordem = db.Column(db.Integer, nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, server_default=db.true())
    criado_em = criado_em()

    __table_args__ = (
        db.CheckConstraint("peso > 0", name="ck_criterios_avaliacao_peso"),
        db.CheckConstraint(
            "nota_maxima > nota_minima", name="ck_criterios_avaliacao_faixa_de_nota"
        ),
    )
