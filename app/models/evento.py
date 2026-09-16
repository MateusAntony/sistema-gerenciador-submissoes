from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.extensions import db


def _json_list(value):
    if value in (None, '', 'None'):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            try:
                return json.loads(value.replace("'", '"'))
            except (TypeError, ValueError):
                return []
    return []


def _json_value(value, fallback):
    if value in (None, '', 'None'):
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback
    return fallback


class SolicitacaoEvento(db.Model):
    __tablename__ = 'solicitacoes_evento'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    solicitante_id = db.Column(db.Uuid, db.ForeignKey('usuarios.id'), nullable=False)
    situacao = db.Column(db.String(32), nullable=False, default='pendente')
    criado_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    decidido_por_id = db.Column(db.Uuid, db.ForeignKey('usuarios.id'), nullable=True)
    decidido_em = db.Column(db.DateTime(timezone=True), nullable=True)
    motivo_recusa = db.Column(db.Text, nullable=True)
    titulo = db.Column(db.String(255), nullable=False)
    sigla = db.Column(db.String(64), nullable=True)
    ano = db.Column(db.Integer, nullable=False)
    identificador_pagina = db.Column(db.String(120), nullable=False, unique=True)
    tipo = db.Column(db.String(64), nullable=False)
    cidade = db.Column(db.String(120), nullable=True)
    estado = db.Column(db.String(120), nullable=True)
    pais = db.Column(db.String(120), nullable=False)
    fuso = db.Column(db.String(80), nullable=False)
    data_inicio = db.Column(db.String(40), nullable=False)
    data_termino = db.Column(db.String(40), nullable=False)
    data_publicacao = db.Column(db.String(40), nullable=True)
    justificativa = db.Column(db.Text, nullable=False)
    evento_pai_id = db.Column(db.Uuid, nullable=True)
    chairs_iniciais = db.Column(db.Text, default='[]')
    versao = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        return {
            'id': self.id,
            'solicitanteId': self.solicitante_id,
            'situacao': self.situacao,
            'criadoEm': self.criado_em.isoformat() if self.criado_em else None,
            'decididoPorId': self.decidido_por_id,
            'decididoEm': self.decidido_em.isoformat() if self.decidido_em else None,
            'motivoRecusa': self.motivo_recusa,
            'titulo': self.titulo,
            'sigla': self.sigla,
            'ano': self.ano,
            'identificadorPagina': self.identificador_pagina,
            'tipo': self.tipo,
            'cidade': self.cidade,
            'estado': self.estado,
            'pais': self.pais,
            'fuso': self.fuso,
            'dataInicio': self.data_inicio,
            'dataTermino': self.data_termino,
            'dataPublicacao': self.data_publicacao,
            'justificativa': self.justificativa,
            'eventoPaiId': self.evento_pai_id,
            'chairsIniciais': _json_list(self.chairs_iniciais),
            'versao': self.versao,
        }


class Evento(db.Model):
    __tablename__ = 'eventos'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    situacao = db.Column(db.String(32), nullable=False, default='aprovado')
    titulo = db.Column(db.String(255), nullable=False)
    sigla = db.Column(db.String(64), nullable=True)
    ano = db.Column(db.Integer, nullable=False)
    identificador_pagina = db.Column(db.String(120), nullable=False, unique=True)
    tipo = db.Column(db.String(64), nullable=False)
    cidade = db.Column(db.String(120), nullable=True)
    estado = db.Column(db.String(120), nullable=True)
    pais = db.Column(db.String(120), nullable=False)
    fuso = db.Column(db.String(80), nullable=False)
    data_inicio = db.Column(db.String(40), nullable=False)
    data_termino = db.Column(db.String(40), nullable=False)
    data_publicacao = db.Column(db.String(40), nullable=True)
    evento_pai_id = db.Column(db.Uuid, nullable=True)
    modelo_de_avaliacao = db.Column(db.String(32), nullable=False, default='aberta')
    avaliadores_por_submissao = db.Column(db.Integer, nullable=False, default=1)
    rebuttal_habilitado = db.Column(db.Boolean, nullable=False, default=False)
    prazo_rebuttal_dias = db.Column(db.Integer, nullable=True)
    maximo_de_rodadas = db.Column(db.Integer, nullable=False, default=1)
    nota_de_corte = db.Column(db.Float, nullable=True)
    limite_submissoes_por_autor = db.Column(db.Integer, nullable=True)
    versao = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        return {
            'id': self.id,
            'situacao': self.situacao,
            'titulo': self.titulo,
            'sigla': self.sigla,
            'ano': self.ano,
            'identificadorPagina': self.identificador_pagina,
            'tipo': self.tipo,
            'cidade': self.cidade,
            'estado': self.estado,
            'pais': self.pais,
            'fuso': self.fuso,
            'dataInicio': self.data_inicio,
            'dataTermino': self.data_termino,
            'dataPublicacao': self.data_publicacao,
            'eventoPaiId': self.evento_pai_id,
            'modeloDeAvaliacao': self.modelo_de_avaliacao,
            'avaliadoresPorSubmissao': self.avaliadores_por_submissao,
            'rebuttalHabilitado': self.rebuttal_habilitado,
            'prazoRebuttalDias': self.prazo_rebuttal_dias,
            'maximoDeRodadas': self.maximo_de_rodadas,
            'notaDeCorte': self.nota_de_corte,
            'limiteSubmissoesPorAutor': self.limite_submissoes_por_autor,
            'versao': self.versao,
        }


class Trilha(db.Model):
    __tablename__ = 'trilhas'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    evento_id = db.Column(db.Uuid, db.ForeignKey('eventos.id'), nullable=False)
    nome = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    ativa = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'eventoId': self.evento_id,
            'nome': self.nome,
            'descricao': self.descricao,
            'ativa': self.ativa,
        }


class Chamada(db.Model):
    __tablename__ = 'chamadas'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    evento_id = db.Column(db.Uuid, db.ForeignKey('eventos.id'), nullable=False)
    trilha_id = db.Column(db.Uuid, db.ForeignKey('trilhas.id'), nullable=True)
    titulo = db.Column(db.String(255), nullable=False)
    data_abertura = db.Column(db.String(40), nullable=False)
    data_limite = db.Column(db.String(40), nullable=False)
    permite_submissao_apos_prazo = db.Column(db.Boolean, nullable=False, default=False)
    formatos_aceitos = db.Column(db.Text, default='[]')
    tamanho_maximo_mb = db.Column(db.Integer, nullable=False, default=0)
    encerrada_manualmente = db.Column(db.Boolean, nullable=False, default=False)
    versao = db.Column(db.Integer, nullable=False, default=1)

    def to_dict(self):
        return {
            'id': self.id,
            'eventoId': self.evento_id,
            'trilhaId': self.trilha_id,
            'titulo': self.titulo,
            'dataAbertura': self.data_abertura,
            'dataLimite': self.data_limite,
            'permiteSubmissaoAposPrazo': self.permite_submissao_apos_prazo,
            'formatosAceitos': _json_list(self.formatos_aceitos),
            'tamanhoMaximoMb': self.tamanho_maximo_mb,
            'encerradaManualmente': self.encerrada_manualmente,
            'versao': self.versao,
        }


class Submissao(db.Model):
    __tablename__ = 'submissoes'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    chamada_id = db.Column(db.Uuid, db.ForeignKey('chamadas.id'), nullable=False)
    evento_id = db.Column(db.Uuid, db.ForeignKey('eventos.id'), nullable=False)
    trilha_id = db.Column(db.Uuid, db.ForeignKey('trilhas.id'), nullable=True)
    autor_responsavel_id = db.Column(db.Uuid, db.ForeignKey('usuarios.id'), nullable=False)
    codigo = db.Column(db.String(32), unique=True, nullable=True)
    numero = db.Column(db.Integer, unique=True, nullable=True)
    situacao = db.Column(db.String(40), nullable=False, default='rascunho')
    fora_do_prazo = db.Column(db.Boolean, nullable=False, default=False)
    identificador_externo = db.Column(db.String(120), nullable=True)
    versao_formulario = db.Column(db.Integer, nullable=False, default=1)
    formulario_versao_id = db.Column(db.String(120), nullable=False, default='formulario-padrao')
    respostas = db.Column(db.Text, nullable=False, default='{}')
    data_ultimo_salvamento = db.Column(db.DateTime(timezone=True), nullable=True)
    data_confirmacao = db.Column(db.DateTime(timezone=True), nullable=True)
    criado_em = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)

    def respostas_dict(self):
        valor = _json_value(self.respostas, {})
        return valor if isinstance(valor, dict) else {}

    def to_dict(self):
        return {
            'id': str(self.id),
            'chamadaId': str(self.chamada_id),
            'eventoId': str(self.evento_id),
            'trilhaId': str(self.trilha_id) if self.trilha_id is not None else None,
            'autorResponsavelId': str(self.autor_responsavel_id),
            'codigo': self.codigo,
            'situacao': self.situacao,
            'foraDoPrazo': self.fora_do_prazo,
            'identificadorExterno': self.identificador_externo,
            'versaoFormulario': self.versao_formulario,
            'dataUltimoSalvamento': self.data_ultimo_salvamento.isoformat() if self.data_ultimo_salvamento else None,
            'dataConfirmacao': self.data_confirmacao.isoformat() if self.data_confirmacao else None,
            'formularioVersaoId': self.formulario_versao_id,
            'respostas': self.respostas_dict(),
        }


class Autoria(db.Model):
    __tablename__ = 'autorias'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    submissao_id = db.Column(db.Uuid, db.ForeignKey('submissoes.id'), nullable=False)
    usuario_id = db.Column(db.Uuid, db.ForeignKey('usuarios.id'), nullable=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    instituicao = db.Column(db.String(200), nullable=False, default='')
    ordem = db.Column(db.Integer, nullable=False, default=1)
    correspondente = db.Column(db.Boolean, nullable=False, default=False)
    eh_responsavel = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'id': str(self.id),
            'submissaoId': str(self.submissao_id),
            'nome': self.nome,
            'email': self.email,
            'instituicao': self.instituicao,
            'ordem': self.ordem,
            'correspondente': self.correspondente,
            'usuarioId': str(self.usuario_id) if self.usuario_id is not None else None,
            'ehResponsavel': self.eh_responsavel,
        }


class VersaoDeArquivo(db.Model):
    __tablename__ = 'versoes_arquivo'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    submissao_id = db.Column(db.Uuid, db.ForeignKey('submissoes.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    nome_original = db.Column(db.String(255), nullable=False)
    tamanho_bytes = db.Column(db.Integer, nullable=False)
    resumo_das_alteracoes = db.Column(db.Text, nullable=True)
    enviado_por = db.Column(db.String(200), nullable=False)
    data_envio = db.Column(db.DateTime(timezone=True), default=datetime.utcnow)
    vigente = db.Column(db.Boolean, nullable=False, default=True)
    caminho_arquivo = db.Column(db.String(500), nullable=True)

    def to_dict(self):
        return {
            'id': str(self.id),
            'submissaoId': str(self.submissao_id),
            'numero': self.numero,
            'nomeOriginal': self.nome_original,
            'tamanhoBytes': self.tamanho_bytes,
            'resumoDasAlteracoes': self.resumo_das_alteracoes,
            'enviadoPor': self.enviado_por,
            'dataEnvio': self.data_envio.isoformat() if self.data_envio else None,
            'vigente': self.vigente,
        }


class Criterio(db.Model):
    __tablename__ = 'criterios'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    evento_id = db.Column(db.Uuid, db.ForeignKey('eventos.id'), nullable=False)
    titulo = db.Column(db.String(255), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    nota_minima = db.Column(db.Float, nullable=False, default=0)
    nota_maxima = db.Column(db.Float, nullable=False, default=0)
    peso = db.Column(db.Float, nullable=False, default=1)
    ordem = db.Column(db.Integer, nullable=False, default=1)
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    tem_notas = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'eventoId': self.evento_id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'notaMinima': self.nota_minima,
            'notaMaxima': self.nota_maxima,
            'peso': self.peso,
            'ordem': self.ordem,
            'ativo': self.ativo,
            'temNotas': self.tem_notas,
        }


class ParticipacaoEvento(db.Model):
    __tablename__ = 'participacoes_evento'

    id = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    evento_id = db.Column(db.Uuid, db.ForeignKey('eventos.id'), nullable=False)
    usuario_id = db.Column(db.Uuid, db.ForeignKey('usuarios.id'), nullable=False)
    papel = db.Column(db.String(32), nullable=False)
    areas_interesse = db.Column(db.Text, default='[]')
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    def to_dict(self):
        return {
            'eventoId': self.evento_id,
            'usuarioId': self.usuario_id,
            'papeis': [self.papel],
        }
