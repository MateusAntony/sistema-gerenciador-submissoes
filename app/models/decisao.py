from app.extensions import db


class Decisao(db.Model):
    __tablename__ = 'decisoes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rodada_id = db.Column(db.Integer, db.ForeignKey('rodadas.id'), nullable=False, unique=True)
    resultado = db.Column(db.String(32), nullable=False)
    # 'aceita' | 'aceita_com_correcoes' | 'nova_rodada' | 'rejeitada'
    justificativa = db.Column(db.Text, nullable=False)
    decidido_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    decidido_por_nome = db.Column(db.String(200), nullable=True)
    decidido_em = db.Column(db.DateTime(timezone=True))
    comunicada_em = db.Column(db.DateTime(timezone=True), nullable=True)
    prazo_versao_corrigida = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'rodadaId': self.rodada_id,
            'resultado': self.resultado,
            'justificativa': self.justificativa,
            'decididoPorNome': self.decidido_por_nome,
            'decididoEm': self.decidido_em.isoformat() if self.decidido_em else None,
            'comunicadaEm': self.comunicada_em.isoformat() if self.comunicada_em else None,
            'prazoVersaoCorrigida': self.prazo_versao_corrigida.isoformat() if self.prazo_versao_corrigida else None,
        }