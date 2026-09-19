from app.extensions import db


class Rodada(db.Model):
    __tablename__ = 'rodadas'
    __table_args__ = (
        db.UniqueConstraint('submissao_id', 'numero', name='uq_rodada_submissao_numero'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submissao_id = db.Column(db.Integer, db.ForeignKey('submissoes.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False, default=1)
    aberta_em = db.Column(db.DateTime(timezone=True))
    encerrada_em = db.Column(db.DateTime(timezone=True), nullable=True)
    encerrada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    data_limite_parecer = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'submissaoId': self.submissao_id,
            'eventoId': self.evento_id,
            'numero': self.numero,
            'abertaEm': self.aberta_em.isoformat() if self.aberta_em else None,
            'encerradaEm': self.encerrada_em.isoformat() if self.encerrada_em else None,
            'dataLimiteParecer': self.data_limite_parecer.isoformat() if self.data_limite_parecer else None,
        }