from app.extensions import db


class Rebuttal(db.Model):
    __tablename__ = 'rebuttals'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rodada_id = db.Column(db.Integer, db.ForeignKey('rodadas.id'), nullable=False, unique=True)
    situacao = db.Column(db.String(16), nullable=False, default='aguardando')
    # 'aguardando' | 'enviado' | 'expirado' | 'cancelado'
    prazo = db.Column(db.DateTime(timezone=True), nullable=True)
    texto = db.Column(db.Text, nullable=True)
    versao_id = db.Column(db.Integer, db.ForeignKey('versoes_arquivo.id'), nullable=True)
    enviado_em = db.Column(db.DateTime(timezone=True), nullable=True)
    enviado_por_nome = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'rodadaId': self.rodada_id,
            'situacao': self.situacao,
            'prazo': self.prazo.isoformat() if self.prazo else None,
            'texto': self.texto,
            'versaoId': self.versao_id,
            'enviadoEm': self.enviado_em.isoformat() if self.enviado_em else None,
            'enviadoPorNome': self.enviado_por_nome,
        }