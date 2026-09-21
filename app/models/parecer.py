import json

from app.extensions import db


class Parecer(db.Model):
    __tablename__ = 'pareceres'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    atribuicao_id = db.Column(db.Integer, db.ForeignKey('atribuicoes.id'), nullable=False, unique=True)
    situacao = db.Column(db.String(16), nullable=False, default='rascunho')  # 'rascunho' | 'submetido'
    notas = db.Column(db.Text, nullable=False, default='[]')  # JSON: [{criterioId, nota}]
    recomendacao = db.Column(db.String(32), nullable=True)
    comentarios_aos_autores = db.Column(db.Text, nullable=True)
    comentarios_confidenciais = db.Column(db.Text, nullable=True)
    nivel_de_confianca = db.Column(db.Integer, nullable=True)
    arquivo_nome = db.Column(db.String(255), nullable=True)
    arquivo_tamanho_bytes = db.Column(db.Integer, nullable=True)
    pontuacao_ponderada = db.Column(db.Float, nullable=True)
    data_submissao = db.Column(db.DateTime(timezone=True), nullable=True)
    atualizado_em = db.Column(db.DateTime(timezone=True), nullable=True)

    def get_notas(self):
        try:
            return json.loads(self.notas or '[]')
        except (TypeError, ValueError):
            return []

    def set_notas(self, notas: list):
        self.notas = json.dumps(notas, ensure_ascii=False)

    def to_dict(self, incluir_confidenciais=True):
        arquivo = None
        if self.arquivo_nome:
            arquivo = {'nome': self.arquivo_nome, 'tamanhoBytes': self.arquivo_tamanho_bytes}

        dados = {
            'id': self.id,
            'atribuicaoId': self.atribuicao_id,
            'situacao': self.situacao,
            'notas': self.get_notas(),
            'recomendacao': self.recomendacao,
            'comentariosAosAutores': self.comentarios_aos_autores,
            'nivelDeConfianca': self.nivel_de_confianca,
            'arquivo': arquivo,
            'pontuacaoPonderada': self.pontuacao_ponderada,
            'dataSubmissao': self.data_submissao.isoformat() if self.data_submissao else None,
            'atualizadoEm': self.atualizado_em.isoformat() if self.atualizado_em else None,
        }
        if incluir_confidenciais:
            dados['comentariosConfidenciais'] = self.comentarios_confidenciais
        return dados