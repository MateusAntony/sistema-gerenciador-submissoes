import json
from datetime import datetime

from app.extensions import db


class FormularioVersao(db.Model):
    __tablename__ = 'formularios_versao'
    __table_args__ = (
        db.UniqueConstraint('chamada_id', 'versao', name='uq_formulario_chamada_versao'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chamada_id = db.Column(db.Integer, db.ForeignKey('chamadas.id'), nullable=False)
    versao = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='rascunho')  # 'rascunho' | 'publicado'
    publicado_em = db.Column(db.DateTime(timezone=True), nullable=True)
    campos = db.Column(db.Text, nullable=False, default='[]')  # JSON: lista de Campo
    criado_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_campos(self):
        try:
            return json.loads(self.campos or '[]')
        except (TypeError, ValueError):
            return []

    def set_campos(self, campos: list):
        self.campos = json.dumps(campos, ensure_ascii=False)

    def to_dict(self):
        return {
            'id': self.id,
            'chamadaId': self.chamada_id,
            'versao': self.versao,
            'status': self.status,
            'publicadoEm': self.publicado_em.isoformat() if self.publicado_em else None,
            'campos': self.get_campos(),
        }