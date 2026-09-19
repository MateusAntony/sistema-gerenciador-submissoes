from app.extensions import db


class Atribuicao(db.Model):
    __tablename__ = 'atribuicoes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rodada_id = db.Column(db.Integer, db.ForeignKey('rodadas.id'), nullable=False)
    submissao_id = db.Column(db.Integer, db.ForeignKey('submissoes.id'), nullable=False)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    situacao = db.Column(db.String(20), nullable=False, default='convidado')
    # 'convidado' | 'aceito' | 'recusado' | 'sem_resposta' | 'conflito' | 'cancelado'
    avaliador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    avaliador_nome = db.Column(db.String(200), nullable=False)
    avaliador_email = db.Column(db.String(255), nullable=False)
    sem_cadastro = db.Column(db.Boolean, nullable=False, default=False)
    convidado_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    convidado_por_nome = db.Column(db.String(200), nullable=True)
    convidado_em = db.Column(db.DateTime(timezone=True))
    prazo_resposta = db.Column(db.DateTime(timezone=True), nullable=True)
    respondido_em = db.Column(db.DateTime(timezone=True), nullable=True)
    justificativa_recusa = db.Column(db.Text, nullable=True)
    motivo_conflito = db.Column(db.Text, nullable=True)
    delegada_de_id = db.Column(db.Integer, db.ForeignKey('atribuicoes.id'), nullable=True)
    pode_delegar = db.Column(db.Boolean, nullable=False, default=True)
    lembretes_enviados = db.Column(db.Integer, nullable=False, default=0)
    ultimo_lembrete_em = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        delegada_de_nome = None
        if self.delegada_de_id:
            origem = Atribuicao.query.get(self.delegada_de_id)
            delegada_de_nome = origem.avaliador_nome if origem else None
        return {
            'id': self.id,
            'rodadaId': self.rodada_id,
            'submissaoId': self.submissao_id,
            'eventoId': self.evento_id,
            'situacao': self.situacao,
            'avaliadorId': self.avaliador_id,
            'avaliadorNome': self.avaliador_nome,
            'avaliadorEmail': self.avaliador_email,
            'semCadastro': self.sem_cadastro,
            'convidadoPorNome': self.convidado_por_nome,
            'convidadoEm': self.convidado_em.isoformat() if self.convidado_em else None,
            'prazoResposta': self.prazo_resposta.isoformat() if self.prazo_resposta else None,
            'respondidoEm': self.respondido_em.isoformat() if self.respondido_em else None,
            'justificativaRecusa': self.justificativa_recusa,
            'motivoConflito': self.motivo_conflito,
            'delegadaDeNome': delegada_de_nome,
            'podeDelegar': self.pode_delegar,
            'lembretesEnviados': self.lembretes_enviados,
            'ultimoLembreteEm': self.ultimo_lembrete_em.isoformat() if self.ultimo_lembrete_em else None,
        }