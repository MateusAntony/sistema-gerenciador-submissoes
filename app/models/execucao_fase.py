from app.extensions import db


class ExecucaoFase(db.Model):
    __tablename__ = 'execucoes_fase'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    submissao_id = db.Column(db.Integer, db.ForeignKey('submissoes.id'), nullable=False)
    fase_id = db.Column(db.Integer, db.ForeignKey('fases_definicao.id'), nullable=False)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='pendente')
    # 'pendente' | 'em_andamento' | 'aguardando_autor' | 'concluida' | 'dispensada'
    data_inicio = db.Column(db.DateTime(timezone=True), nullable=True)
    prazo = db.Column(db.DateTime(timezone=True), nullable=True)
    data_conclusao = db.Column(db.DateTime(timezone=True), nullable=True)
    arquivo_resultado_id = db.Column(db.Integer, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'submissaoId': self.submissao_id,
            'faseId': self.fase_id,
            'responsavelId': self.responsavel_id,
            'semResponsavel': self.responsavel_id is None,
            'status': self.status,
            'dataInicio': self.data_inicio.isoformat() if self.data_inicio else None,
            'prazo': self.prazo.isoformat() if self.prazo else None,
            'dataConclusao': self.data_conclusao.isoformat() if self.data_conclusao else None,
            'arquivoResultadoId': self.arquivo_resultado_id,
            'observacoes': self.observacoes,
        }