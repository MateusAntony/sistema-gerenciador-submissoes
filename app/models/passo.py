import json

from app.extensions import db


class PassoEnvio(db.Model):
    __tablename__ = 'passos_envio'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    chamada_id = db.Column(db.Integer, db.ForeignKey('chamadas.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    campos = db.Column(db.Text, nullable=False, default='[]')  # JSON: lista de chaves

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
            'nome': self.nome,
            'descricao': self.descricao,
            'ordem': self.ordem,
            'campos': self.get_campos(),
        }