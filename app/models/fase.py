from app.extensions import db


class DefinicaoFase(db.Model):
    __tablename__ = 'fases_definicao'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    momento = db.Column(db.String(16), nullable=False, default='triagem')  # 'triagem' | 'producao'
    prazo_padrao_dias = db.Column(db.Integer, nullable=False, default=0)
    responsavel_padrao_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    obrigatoria = db.Column(db.Boolean, nullable=False, default=True)
    exige_arquivo = db.Column(db.Boolean, nullable=False, default=False)
    permite_devolucao = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'eventoId': self.evento_id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ordem': self.ordem,
            'momento': self.momento,
            'prazoPadraoDias': self.prazo_padrao_dias,
            'responsavelPadraoId': self.responsavel_padrao_id,
            'obrigatoria': self.obrigatoria,
            'exigeArquivo': self.exige_arquivo,
            'permiteDevolucao': self.permite_devolucao,
            'ativo': self.ativo,
        }