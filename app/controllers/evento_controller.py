import json
from datetime import datetime

from flask import Blueprint, request, jsonify

from app.extensions import db
from app.controllers.auth_controller import usuario_autenticado
from app.models.evento import (
    Chamada,
    Criterio,
    Evento,
    ParticipacaoEvento,
    SolicitacaoEvento,
    Trilha,
)
from app.models.user import Usuario


eventos_bp = Blueprint('eventos', __name__, url_prefix='/api')


def _json_error(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


def _usuario_logado():
    return usuario_autenticado()


@eventos_bp.route('/solicitacoes-evento', methods=['POST'])
def criar_solicitacao_evento():
    dados = request.get_json() or {}
    usuario = _usuario_logado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    identificador = (dados.get('identificadorPagina') or '').strip()
    if not dados.get('titulo') or not identificador or not dados.get('dataInicio') or not dados.get('dataTermino'):
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'titulo': 'Este campo é obrigatório.'})

    existente = (
        SolicitacaoEvento.query.filter_by(identificador_pagina=identificador).first()
        or Evento.query.filter_by(identificador_pagina=identificador).first()
    )
    if existente is not None:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'identificadorPagina': 'Este identificador já está em uso.'})

    solicitacao = SolicitacaoEvento(
        solicitante_id=usuario.id,
        situacao='pendente',
        titulo=dados.get('titulo'),
        sigla=dados.get('sigla'),
        ano=dados.get('ano') or datetime.utcnow().year,
        identificador_pagina=identificador,
        tipo=dados.get('tipo') or 'outro',
        cidade=dados.get('cidade'),
        estado=dados.get('estado'),
        pais=dados.get('pais') or '',
        fuso=dados.get('fuso') or '',
        data_inicio=dados.get('dataInicio'),
        data_termino=dados.get('dataTermino'),
        data_publicacao=dados.get('dataPublicacao'),
        justificativa=dados.get('justificativa') or '',
        evento_pai_id=dados.get('eventoPaiId'),
        chairs_iniciais=str(dados.get('chairsIniciais') or []),
        versao=1,
    )
    db.session.add(solicitacao)
    db.session.commit()
    return jsonify(solicitacao.to_dict()), 201


@eventos_bp.route('/solicitacoes-evento/<int:solicitacao_id>', methods=['PATCH'])
def atualizar_solicitacao_evento(solicitacao_id):
    usuario = _usuario_logado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    solicitacao = SolicitacaoEvento.query.get(solicitacao_id)
    if solicitacao is None or solicitacao.solicitante_id != usuario.id:
        return _json_error('solicitacao_inexistente', 'Solicitação não encontrada.', 404)
    if solicitacao.situacao != 'pendente':
        return _json_error('solicitacao_ja_decidida', 'Esta solicitação já foi decidida.', 409,
                           decididoPorId=solicitacao.decidido_por_id,
                           decididoEm=solicitacao.decidido_em.isoformat() if solicitacao.decidido_em else None,
                           situacao=solicitacao.situacao)

    dados = request.get_json() or {}
    identificador = (dados.get('identificadorPagina') or '').strip()
    if not dados.get('titulo') or not identificador or not dados.get('dataInicio') or not dados.get('dataTermino'):
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'titulo': 'Este campo é obrigatório.'})

    existente = (
        SolicitacaoEvento.query.filter(
            SolicitacaoEvento.identificador_pagina == identificador,
            SolicitacaoEvento.id != solicitacao.id,
        ).first()
        or Evento.query.filter_by(identificador_pagina=identificador).first()
    )
    if existente is not None:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'identificadorPagina': 'Este identificador já está em uso.'})

    solicitacao.titulo = dados.get('titulo')
    solicitacao.sigla = dados.get('sigla')
    solicitacao.ano = dados.get('ano') or solicitacao.ano
    solicitacao.identificador_pagina = identificador
    solicitacao.tipo = dados.get('tipo') or 'outro'
    solicitacao.cidade = dados.get('cidade')
    solicitacao.estado = dados.get('estado')
    solicitacao.pais = dados.get('pais') or ''
    solicitacao.fuso = dados.get('fuso') or ''
    solicitacao.data_inicio = dados.get('dataInicio')
    solicitacao.data_termino = dados.get('dataTermino')
    solicitacao.data_publicacao = dados.get('dataPublicacao')
    solicitacao.justificativa = dados.get('justificativa') or ''
    solicitacao.evento_pai_id = dados.get('eventoPaiId')
    solicitacao.chairs_iniciais = str(dados.get('chairsIniciais') or [])
    solicitacao.versao = (solicitacao.versao or 1) + 1

    db.session.commit()
    return jsonify(solicitacao.to_dict())


@eventos_bp.route('/me/solicitacoes-evento', methods=['GET'])
def listar_minhas_solicitacoes():
    usuario = _usuario_logado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)
    solicitacoes = SolicitacaoEvento.query.filter_by(solicitante_id=usuario.id).all()
    return jsonify([item.to_dict() for item in solicitacoes])


@eventos_bp.route('/admin/solicitacoes-evento', methods=['GET'])
def listar_fila_solicitacoes():
    status = request.args.get('status')
    consulta = SolicitacaoEvento.query
    if status:
        consulta = consulta.filter_by(situacao=status)
    items = consulta.order_by(SolicitacaoEvento.criado_em.asc()).all()
    return jsonify([item.to_dict() for item in items])


@eventos_bp.route('/admin/solicitacoes-evento/<int:solicitacao_id>/aprovar', methods=['POST'])
def aprovar_solicitacao_evento(solicitacao_id):
    solicitacao = SolicitacaoEvento.query.get(solicitacao_id)
    if solicitacao is None:
        return _json_error('solicitacao_inexistente', 'Solicitação não encontrada.', 404)
    if solicitacao.situacao != 'pendente':
        return _json_error('solicitacao_ja_decidida', 'Esta solicitação já foi decidida.', 409,
                           decididoPorId=solicitacao.decidido_por_id,
                           decididoEm=solicitacao.decidido_em.isoformat() if solicitacao.decidido_em else None,
                           situacao=solicitacao.situacao)

    solicitacao.situacao = 'aprovada'
    solicitacao.decidido_por_id = 1
    solicitacao.decidido_em = datetime.utcnow()

    evento = Evento(
        situacao='aprovado',
        titulo=solicitacao.titulo,
        sigla=solicitacao.sigla,
        ano=solicitacao.ano,
        identificador_pagina=solicitacao.identificador_pagina,
        tipo=solicitacao.tipo,
        cidade=solicitacao.cidade,
        estado=solicitacao.estado,
        pais=solicitacao.pais,
        fuso=solicitacao.fuso,
        data_inicio=solicitacao.data_inicio,
        data_termino=solicitacao.data_termino,
        data_publicacao=solicitacao.data_publicacao,
        evento_pai_id=solicitacao.evento_pai_id,
        modelo_de_avaliacao='aberta',
        avaliadores_por_submissao=1,
        rebuttal_habilitado=False,
        maximo_de_rodadas=1,
        versao=1,
    )
    db.session.add(evento)
    db.session.commit()
    return jsonify({'solicitacao': solicitacao.to_dict(), 'evento': evento.to_dict()})


@eventos_bp.route('/admin/solicitacoes-evento/<int:solicitacao_id>/recusar', methods=['POST'])
def recusar_solicitacao_evento(solicitacao_id):
    solicitacao = SolicitacaoEvento.query.get(solicitacao_id)
    if solicitacao is None:
        return _json_error('solicitacao_inexistente', 'Solicitação não encontrada.', 404)
    if solicitacao.situacao != 'pendente':
        return _json_error('solicitacao_ja_decidida', 'Esta solicitação já foi decidida.', 409,
                           decididoPorId=solicitacao.decidido_por_id,
                           decididoEm=solicitacao.decidido_em.isoformat() if solicitacao.decidido_em else None,
                           situacao=solicitacao.situacao)

    dados = request.get_json() or {}
    motivo = (dados.get('motivo') or '').strip()
    if not motivo:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'motivo': 'Informe o motivo da recusa.'})

    solicitacao.situacao = 'recusada'
    solicitacao.decidido_por_id = 1
    solicitacao.decidido_em = datetime.utcnow()
    solicitacao.motivo_recusa = motivo
    db.session.commit()
    return jsonify(solicitacao.to_dict())


@eventos_bp.route('/eventos/<int:evento_id>', methods=['GET'])
def obter_evento(evento_id):
    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    return jsonify(evento.to_dict())


@eventos_bp.route('/eventos', methods=['GET'])
def listar_catalogo_publico():
    eventos = Evento.query.order_by(Evento.data_inicio.desc()).all()
    resposta = []
    for evento in eventos:
        sub_eventos = [
            filho.titulo
            for filho in Evento.query.filter_by(evento_pai_id=evento.id).order_by(Evento.titulo).all()
        ]
        local = ', '.join(parte for parte in [evento.cidade, evento.estado] if parte)
        if evento.pais:
            local = f'{local}, {evento.pais}' if local else evento.pais
        resposta.append({
            'id': str(evento.id),
            'titulo': evento.titulo,
            'site': f'/e/{evento.identificador_pagina}',
            'local': local,
            'periodo': f'De {evento.data_inicio} a {evento.data_termino}',
            'encerrado': evento.situacao == 'encerrado',
            'subEventos': sub_eventos,
        })
    return jsonify(resposta)


@eventos_bp.route('/eventos/por-identificador/<identificador_pagina>', methods=['GET'])
def obter_evento_por_identificador(identificador_pagina):
    evento = Evento.query.filter_by(identificador_pagina=identificador_pagina).first()
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    return jsonify(evento.to_dict())


@eventos_bp.route('/eventos/<int:evento_id>', methods=['PATCH'])
def atualizar_evento(evento_id):
    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)

    dados = request.get_json() or {}
    if 'versao' in dados and dados.get('versao') != evento.versao:
        return jsonify(evento.to_dict()), 409

    campos_validos = {
        'situacao': 'situacao',
        'titulo': 'titulo',
        'sigla': 'sigla',
        'ano': 'ano',
        'identificadorPagina': 'identificador_pagina',
        'tipo': 'tipo',
        'cidade': 'cidade',
        'estado': 'estado',
        'pais': 'pais',
        'fuso': 'fuso',
        'dataInicio': 'data_inicio',
        'dataTermino': 'data_termino',
        'dataPublicacao': 'data_publicacao',
        'eventoPaiId': 'evento_pai_id',
        'modeloDeAvaliacao': 'modelo_de_avaliacao',
        'avaliadoresPorSubmissao': 'avaliadores_por_submissao',
        'rebuttalHabilitado': 'rebuttal_habilitado',
        'prazoRebuttalDias': 'prazo_rebuttal_dias',
        'maximoDeRodadas': 'maximo_de_rodadas',
        'notaDeCorte': 'nota_de_corte',
        'limiteSubmissoesPorAutor': 'limite_submissoes_por_autor',
        'versao': 'versao',
    }

    for chave_origem, chave_destino in campos_validos.items():
        if chave_origem in dados:
            setattr(evento, chave_destino, dados[chave_origem])

    if evento.rebuttal_habilitado and (evento.prazo_rebuttal_dias is None or evento.prazo_rebuttal_dias <= 0):
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'prazoRebuttalDias': 'Informe o prazo de rebuttal em dias.'})

    if evento.avaliadores_por_submissao < 1:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'avaliadoresPorSubmissao': 'Informe um inteiro maior ou igual a 1.'})

    if evento.maximo_de_rodadas < 1:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'maximoDeRodadas': 'Informe um inteiro maior ou igual a 1.'})

    evento.versao += 1
    db.session.commit()
    return jsonify(evento.to_dict())


@eventos_bp.route('/eventos/<int:evento_id>/descendentes', methods=['GET'])
def obter_descendentes(evento_id):
    filhos = Evento.query.filter_by(evento_pai_id=str(evento_id)).all()
    descendentes = []
    for filho in filhos:
        descendentes.append(str(filho.id))
        descendentes.extend(obter_descendentes_recursivos(filho.id))
    return jsonify({'descendentes': descendentes})


def obter_descendentes_recursivos(evento_id):
    filhos = Evento.query.filter_by(evento_pai_id=str(evento_id)).all()
    result = []
    for filho in filhos:
        result.append(str(filho.id))
        result.extend(obter_descendentes_recursivos(filho.id))
    return result


@eventos_bp.route('/eventos/<int:evento_id>/trilhas', methods=['GET'])
def listar_trilhas(evento_id):
    trilhas = Trilha.query.filter_by(evento_id=evento_id).all()
    return jsonify([item.to_dict() for item in trilhas])


@eventos_bp.route('/eventos/<int:evento_id>/trilhas', methods=['POST'])
def criar_trilha(evento_id):
    dados = request.get_json() or {}
    trilha = Trilha(
        evento_id=evento_id,
        nome=dados.get('nome') or '',
        descricao=dados.get('descricao'),
        ativa=dados.get('ativa', True),
    )
    db.session.add(trilha)
    db.session.commit()
    return jsonify(trilha.to_dict()), 201


@eventos_bp.route('/trilhas/<int:trilha_id>', methods=['PATCH'])
def atualizar_trilha(trilha_id):
    trilha = Trilha.query.get(trilha_id)
    if trilha is None:
        return _json_error('trilha_inexistente', 'Trilha não encontrada.', 404)
    dados = request.get_json() or {}
    for campo in ['nome', 'descricao', 'ativa']:
        if campo in dados:
            setattr(trilha, campo, dados[campo])
    db.session.commit()
    return jsonify(trilha.to_dict())


@eventos_bp.route('/eventos/<int:evento_id>/chamadas', methods=['GET'])
def listar_chamadas(evento_id):
    chamadas = Chamada.query.filter_by(evento_id=evento_id).all()
    return jsonify([item.to_dict() for item in chamadas])


@eventos_bp.route('/eventos/<int:evento_id>/chamadas', methods=['POST'])
def criar_chamada(evento_id):
    dados = request.get_json() or {}
    data_abertura = dados.get('dataAbertura') or ''
    data_limite = dados.get('dataLimite') or ''
    if data_limite and data_abertura and data_limite <= data_abertura:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'dataLimite': 'A data limite deve ser posterior à data de abertura.'})

    chamada = Chamada(
        evento_id=evento_id,
        trilha_id=dados.get('trilhaId'),
        titulo=dados.get('titulo') or '',
        data_abertura=data_abertura,
        data_limite=data_limite,
        permite_submissao_apos_prazo=dados.get('permiteSubmissaoAposPrazo', False),
        formatos_aceitos=json.dumps(dados.get('formatosAceitos') or []),
        tamanho_maximo_mb=dados.get('tamanhoMaximoMb', 0),
        encerrada_manualmente=False,
        versao=1,
    )
    db.session.add(chamada)
    db.session.commit()
    return jsonify(chamada.to_dict()), 201


@eventos_bp.route('/chamadas/<int:chamada_id>', methods=['PATCH'])
def atualizar_chamada(chamada_id):
    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('chamada_inexistente', 'Chamada não encontrada.', 404)

    dados = request.get_json() or {}
    if 'versao' in dados and dados.get('versao') != chamada.versao:
        return jsonify(chamada.to_dict()), 409

    data_abertura = dados.get('dataAbertura', chamada.data_abertura)
    data_limite = dados.get('dataLimite', chamada.data_limite)
    if data_limite and data_abertura and data_limite <= data_abertura:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'dataLimite': 'A data limite deve ser posterior à data de abertura.'})

    for chave_origem, chave_destino in {
        'trilhaId': 'trilha_id',
        'titulo': 'titulo',
        'dataAbertura': 'data_abertura',
        'dataLimite': 'data_limite',
        'permiteSubmissaoAposPrazo': 'permite_submissao_apos_prazo',
        'formatosAceitos': 'formatos_aceitos',
        'tamanhoMaximoMb': 'tamanho_maximo_mb',
        'encerradaManualmente': 'encerrada_manualmente',
        'versao': 'versao',
    }.items():
        if chave_origem in dados:
            setattr(chamada, chave_destino, dados[chave_origem])
    if 'formatosAceitos' in dados:
        chamada.formatos_aceitos = json.dumps(dados['formatosAceitos'])
    chamada.versao += 1
    db.session.commit()
    return jsonify(chamada.to_dict())


@eventos_bp.route('/chamadas/<int:chamada_id>/prorrogar', methods=['POST'])
def prorrogar_chamada(chamada_id):
    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('chamada_inexistente', 'Chamada não encontrada.', 404)
    dados = request.get_json() or {}
    nova_data = dados.get('dataLimite') or ''
    if not nova_data or nova_data <= chamada.data_limite:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'dataLimite': 'A nova data limite deve ser posterior à vigente.'})
    chamada.data_limite = nova_data
    chamada.versao += 1
    db.session.commit()
    return jsonify(chamada.to_dict())


@eventos_bp.route('/chamadas/<int:chamada_id>/encerrar', methods=['POST'])
def encerrar_chamada(chamada_id):
    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('chamada_inexistente', 'Chamada não encontrada.', 404)
    chamada.encerrada_manualmente = True
    chamada.versao += 1
    db.session.commit()
    return jsonify(chamada.to_dict())


@eventos_bp.route('/eventos/<int:evento_id>/criterios', methods=['GET'])
def listar_criterios(evento_id):
    criterios = Criterio.query.filter_by(evento_id=evento_id).all()
    return jsonify([item.to_dict() for item in criterios])


@eventos_bp.route('/eventos/<int:evento_id>/criterios', methods=['POST'])
def criar_criterio(evento_id):
    dados = request.get_json() or {}
    nota_minima = dados.get('notaMinima', 0)
    nota_maxima = dados.get('notaMaxima', 0)
    if nota_maxima <= nota_minima:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'notaMaxima': 'A nota máxima deve ser maior que a mínima.'})

    peso = dados.get('peso', 0)
    if peso <= 0:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'peso': 'O peso deve ser maior que zero.'})

    criterio = Criterio(
        evento_id=evento_id,
        titulo=dados.get('titulo') or '',
        descricao=dados.get('descricao'),
        nota_minima=nota_minima,
        nota_maxima=nota_maxima,
        peso=peso,
        ordem=dados.get('ordem', 1),
        ativo=dados.get('ativo', True),
        tem_notas=False,
    )
    db.session.add(criterio)
    db.session.commit()
    return jsonify(criterio.to_dict()), 201


@eventos_bp.route('/criterios/<int:criterio_id>', methods=['PATCH'])
def atualizar_criterio(criterio_id):
    criterio = Criterio.query.get(criterio_id)
    if criterio is None:
        return _json_error('criterio_inexistente', 'Critério não encontrado.', 404)
    dados = request.get_json() or {}
    nota_minima = dados.get('notaMinima', criterio.nota_minima)
    nota_maxima = dados.get('notaMaxima', criterio.nota_maxima)
    if nota_maxima <= nota_minima:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'notaMaxima': 'A nota máxima deve ser maior que a mínima.'})

    peso = dados.get('peso', criterio.peso)
    if peso <= 0:
        return _json_error('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'peso': 'O peso deve ser maior que zero.'})

    for campo in ['titulo', 'descricao', 'nota_minima', 'nota_maxima', 'peso', 'ordem', 'ativo']:
        if campo in dados or campo.replace('_', 'Minima') in dados:
            pass

    for chave_origem, chave_destino in {
        'titulo': 'titulo',
        'descricao': 'descricao',
        'notaMinima': 'nota_minima',
        'notaMaxima': 'nota_maxima',
        'peso': 'peso',
        'ordem': 'ordem',
        'ativo': 'ativo',
    }.items():
        if chave_origem in dados:
            setattr(criterio, chave_destino, dados[chave_origem])
    db.session.commit()
    return jsonify(criterio.to_dict())


@eventos_bp.route('/criterios/<int:criterio_id>', methods=['DELETE'])
def excluir_criterio(criterio_id):
    criterio = Criterio.query.get(criterio_id)
    if criterio is None:
        return _json_error('criterio_inexistente', 'Critério não encontrado.', 404)
    if criterio.tem_notas:
        return _json_error('criterio_com_notas', 'Este critério já possui notas registradas e não pode ser excluído.', 409, acaoSugerida='desativar')
    db.session.delete(criterio)
    db.session.commit()
    return '', 204


@eventos_bp.route('/eventos/<int:evento_id>/checklist-publicacao', methods=['GET'])
def checklist_publicacao(evento_id):
    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    checklist = {
        'temChamada': Chamada.query.filter_by(evento_id=evento_id).count() > 0,
        'temCriterioAtivo': Criterio.query.filter_by(evento_id=evento_id, ativo=True).count() > 0,
        'formularioDefinido': False,
        'etapasDefinidas': False,
        'eventoAprovado': evento.situacao in {'aprovado', 'publicado'},
    }
    return jsonify(checklist)


@eventos_bp.route('/eventos/<int:evento_id>/publicar', methods=['POST'])
def publicar_evento(evento_id):
    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    if evento.situacao != 'aprovado':
        return _json_error('evento_nao_aprovado', 'O evento precisa ser aprovado pelo administrador antes de ser publicado.', 409)

    checklist = {
        'temChamada': Chamada.query.filter_by(evento_id=evento_id).count() > 0,
        'temCriterioAtivo': Criterio.query.filter_by(evento_id=evento_id, ativo=True).count() > 0,
        'formularioDefinido': False,
        'etapasDefinidas': False,
        'eventoAprovado': evento.situacao in {'aprovado', 'publicado'},
    }
    faltantes = [item for item, ok in checklist.items() if item != 'eventoAprovado' and not ok]
    if faltantes:
        return _json_error('checklist_incompleto', 'Complete os itens pendentes antes de publicar.', 422, campos={item: 'Este item ainda não foi concluído.' for item in faltantes})

    dados = request.get_json(silent=True) or {}
    if 'versao' in dados and dados.get('versao') != evento.versao:
        return jsonify(evento.to_dict()), 409

    evento.situacao = 'publicado'
    evento.versao += 1
    db.session.commit()
    return jsonify(evento.to_dict())


@eventos_bp.route('/me/participacoes', methods=['GET'])
def listar_participacoes():
    usuario = _usuario_logado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)
    participacoes = ParticipacaoEvento.query.filter_by(usuario_id=usuario.id).all()
    return jsonify([
        {
            'eventoId': item.evento_id,
            'eventoTitulo': Evento.query.get(item.evento_id).titulo if Evento.query.get(item.evento_id) else '',
            'identificadorPagina': Evento.query.get(item.evento_id).identificador_pagina if Evento.query.get(item.evento_id) else '',
            'papeis': [item.papel],
        }
        for item in participacoes
    ])


def _ids_dos_eventos_do_usuario(usuario_id):
    """Ids de eventos em que o usuário participa em qualquer papel:
    chair/avaliador/responsável de etapa (participacoes_evento) OU autor
    (responsável pela submissão ou listado como coautor em autorias)."""
    from app.models.evento import Submissao, Autoria

    ids = set(
        item.evento_id
        for item in ParticipacaoEvento.query.filter_by(usuario_id=usuario_id).all()
    )
    ids.update(
        item.evento_id
        for item in Submissao.query.filter_by(autor_responsavel_id=usuario_id).all()
    )
    autorias = Autoria.query.filter_by(usuario_id=usuario_id).all()
    for autoria in autorias:
        submissao = Submissao.query.get(autoria.submissao_id)
        if submissao is not None:
            ids.add(submissao.evento_id)
    return ids


def _evento_para_vitrine(evento):
    sub_eventos = [
        filho.titulo
        for filho in Evento.query.filter_by(evento_pai_id=evento.id).order_by(Evento.titulo).all()
    ]
    local = ', '.join(parte for parte in [evento.cidade, evento.estado] if parte)
    if evento.pais:
        local = f'{local}, {evento.pais}' if local else evento.pais
    return {
        'id': str(evento.id),
        'titulo': evento.titulo,
        'site': f'/e/{evento.identificador_pagina}',
        'local': local,
        'periodo': f'De {evento.data_inicio} a {evento.data_termino}',
        'encerrado': evento.situacao == 'encerrado',
        'subEventos': sub_eventos,
    }


@eventos_bp.route('/me/eventos', methods=['GET'])
def listar_meus_eventos():
    usuario = _usuario_logado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    ids = _ids_dos_eventos_do_usuario(usuario.id)
    eventos = (
        Evento.query
        .filter(Evento.id.in_(ids))
        .order_by(Evento.data_inicio.desc())
        .all()
        if ids else []
    )
    return jsonify([_evento_para_vitrine(evento) for evento in eventos])