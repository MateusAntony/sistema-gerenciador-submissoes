from app.extensions import db


class VersaoCorrigida(db.Model):
    __tablename__ = 'versoes_corrigidas'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submissao_id = db.Column(db.Integer, db.ForeignKey('submissoes.id'), nullable=False, unique=True)
    versao_id = db.Column(db.Integer, db.ForeignKey('versoes_arquivo.id'), nullable=True)
    descricao_das_alteracoes = db.Column(db.Text, nullable=True)
    enviada_em = db.Column(db.DateTime(timezone=True), nullable=True)
    validada_em = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        devolucoes = (
            DevolucaoDeVersaoCorrigida.query
            .filter_by(versao_corrigida_id=self.id)
            .order_by(DevolucaoDeVersaoCorrigida.devolvida_em)
            .all()
        )
        return {
            'submissaoId': self.submissao_id,
            'versaoId': self.versao_id,
            'descricaoDasAlteracoes': self.descricao_das_alteracoes,
            'enviadaEm': self.enviada_em.isoformat() if self.enviada_em else None,
            'devolucoes': [d.to_dict() for d in devolucoes],
        }


class DevolucaoDeVersaoCorrigida(db.Model):
    __tablename__ = 'versoes_corrigidas_devolucoes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    versao_corrigida_id = db.Column(db.Integer, db.ForeignKey('versoes_corrigidas.id'), nullable=False)
    apontamentos = db.Column(db.Text, nullable=False)
    devolvida_em = db.Column(db.DateTime(timezone=True))
    devolvida_por_nome = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            'apontamentos': self.apontamentos,
            'devolvidaEm': self.devolvida_em.isoformat() if self.devolvida_em else None,
            'devolvidaPorNome': self.devolvida_por_nome,
        }