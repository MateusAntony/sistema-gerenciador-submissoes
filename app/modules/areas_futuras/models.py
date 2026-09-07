"""Tabelas minimas das areas futuras (AD-018).

Nascem vazias e nenhum endpoint delas e implementado nesta rodada. Existem para que
`checklist.formularioDefinido`, `checklist.etapasDefinidas`, `trilha.submissoesVinculadas`
e `criterio.temNotas` sejam derivados de verdade, em vez de fixados. As areas donas as
ampliam por migration aditiva.
"""

from app.extensions import db
from app.modules.colunas import chave_estrangeira, chave_primaria


class FormularioChamada(db.Model):
    """Dona: FORM. Alimenta `checklist.formularioDefinido`."""

    __tablename__ = "formularios_chamada"

    id = chave_primaria()
    chamada_id = chave_estrangeira(
        "chamadas.id", ondelete="CASCADE", nullable=False
    )
    versao = db.Column(db.Integer, nullable=False, server_default="1")
    status = db.Column(db.String(20))


class FaseEvento(db.Model):
    """Dona: FASE. Alimenta `checklist.etapasDefinidas`."""

    __tablename__ = "fases_evento"

    id = chave_primaria()
    evento_id = chave_estrangeira(
        "eventos.id", ondelete="CASCADE", nullable=False
    )
    nome = db.Column(db.String(200), nullable=False)
    ordem = db.Column(db.Integer)


class Submissao(db.Model):
    """Dona: SUB. Alimenta `trilha.submissoesVinculadas`."""

    __tablename__ = "submissoes"

    id = chave_primaria()
    chamada_id = chave_estrangeira(
        "chamadas.id", ondelete="CASCADE", nullable=False
    )
    trilha_id = chave_estrangeira("trilhas.id")


class NotaParecer(db.Model):
    """Dona: AVAL. Alimenta `criterio.temNotas` e o 409 de exclusao de criterio."""

    __tablename__ = "notas_parecer"

    id = chave_primaria()
    criterio_id = chave_estrangeira(
        "criterios_avaliacao.id", ondelete="CASCADE", nullable=False
    )
