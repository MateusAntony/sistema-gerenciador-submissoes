from datetime import datetime

from app.extensions import db


class Notificacao(db.Model):
    __tablename__ = 'notificacoes'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    evento_id = db.Column(db.Integer, db.ForeignKey('eventos.id'), nullable=False)
    submissao_id = db.Column(db.Integer, db.ForeignKey('submissoes.id'), nullable=True)
    destinatario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)
    destinatario_nome = db.Column(db.String(200), nullable=False)
    destinatario_email = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(64), nullable=False)
    assunto = db.Column(db.String(255), nullable=False)
    objeto_tipo = db.Column(db.String(32), nullable=False)  # 'submissao' | 'atribuicao' | 'execucao_fase'
    objeto_id = db.Column(db.String(64), nullable=False)
    canal = db.Column(db.String(16), nullable=False, default='sistema')  # 'email' | 'sistema'
    situacao = db.Column(db.String(16), nullable=False, default='pendente')  # 'pendente'|'enviada'|'falha'
    tentativas = db.Column(db.Integer, nullable=False, default=0)
    maximo_de_tentativas = db.Column(db.Integer, nullable=False, default=3)
    id_provedor = db.Column(db.String(120), nullable=True)
    erro_do_provedor = db.Column(db.Text, nullable=True)
    administrador_avisado = db.Column(db.Boolean, nullable=False, default=False)
    criada_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    atualizada_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    lida_em = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict_usuario(self, evento_identificador_pagina: str):
        """Forma reduzida: NotificacaoDoUsuario."""
        return {
            'id': str(self.id),
            'tipo': self.tipo,
            'assunto': self.assunto,
            'objeto': {
                'tipo': self.objeto_tipo,
                'id': self.objeto_id,
                'eventoIdentificadorPagina': evento_identificador_pagina,
                'submissaoId': str(self.submissao_id) if self.submissao_id is not None else None,
            },
            'criadaEm': self.criada_em.isoformat() if self.criada_em else None,
            'lidaEm': self.lida_em.isoformat() if self.lida_em else None,
        }

    def to_dict(self, evento_identificador_pagina: str):
        """Forma completa: Notificacao (registro), usada pelo chair/admin."""
        base = self.to_dict_usuario(evento_identificador_pagina)
        base.update({
            'eventoId': str(self.evento_id),
            'submissaoId': str(self.submissao_id) if self.submissao_id is not None else None,
            'destinatarioId': str(self.destinatario_id) if self.destinatario_id is not None else None,
            'destinatarioNome': self.destinatario_nome,
            'destinatarioEmail': self.destinatario_email,
            'canal': self.canal,
            'situacao': self.situacao,
            'tentativas': self.tentativas,
            'maximoDeTentativas': self.maximo_de_tentativas,
            'idProvedor': self.id_provedor,
            'erroDoProvedor': self.erro_do_provedor,
            'administradorAvisado': self.administrador_avisado,
            'atualizadaEm': self.atualizada_em.isoformat() if self.atualizada_em else None,
        })
        return base