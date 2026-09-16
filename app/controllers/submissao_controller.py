import json
import os
import uuid
from datetime import datetime

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from app.controllers.auth_controller import usuario_autenticado
from app.controllers.identificadores import parse_uuid
from app.extensions import db
from app.models.evento import Autoria, Chamada, Evento, Submissao, Trilha, VersaoDeArquivo
from app.models.user import Usuario


submissoes_bp = Blueprint('submissoes', __name__, url_prefix='/api')


def _erro(codigo: str, mensagem: str, status: int, **extra):
    payload = {'codigo': codigo, 'mensagem': mensagem, 'correlacao': f'cor-{codigo}'}
    payload.update(extra)
    return jsonify(payload), status


def _usuario():
    return usuario_autenticado()


def _submissao_do_autor(submissao_id: uuid.UUID):
    usuario = _usuario()
    submissao = Submissao.query.get(submissao_id)
    if usuario is None:
        return None, _erro('nao_autenticado', 'Sua sessão expirou.', 401)
    if submissao is None or submissao.autor_responsavel_id != usuario.id:
        return None, _erro('submissao_inexistente', 'Submissão não encontrada.', 404)
    return submissao, None


def _resumo(submissao: Submissao):
    chamada = Chamada.query.get(submissao.chamada_id)
    evento = Evento.query.get(submissao.evento_id)
    trilha = Trilha.query.get(submissao.trilha_id) if submissao.trilha_id else None
    respostas = submissao.respostas_dict()
    titulo = respostas.get('titulo', '')
    return {
        'id': str(submissao.id),
        'codigo': submissao.codigo,
        'titulo': titulo if isinstance(titulo, str) else '',
        'eventoId': str(submissao.evento_id),
        'eventoTitulo': evento.titulo if evento else '',
        'chamadaId': str(submissao.chamada_id),
        'chamadaTitulo': chamada.titulo if chamada else '',
        'trilhaNome': trilha.nome if trilha else None,
        'situacao': submissao.situacao,
        'foraDoPrazo': submissao.fora_do_prazo,
        'dataUltimaAtualizacao': (
            submissao.data_ultimo_salvamento or submissao.data_confirmacao or datetime.utcnow()
        ).isoformat(),
        'dataLimiteChamada': chamada.data_limite if chamada else '',
    }


@submissoes_bp.route('/chamadas/<uuid:chamada_id>/submissoes', methods=['POST'])
def criar_submissao(chamada_id):
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _erro('chamada_inexistente', 'Chamada não encontrada.', 404)

    agora = datetime.utcnow().isoformat()
    if chamada.encerrada_manualmente or (chamada.data_limite and chamada.data_limite <= agora[:10]):
        return _erro('chamada_encerrada', 'Esta chamada está encerrada e não aceita novas submissões.', 409)

    dados = request.get_json(silent=True) or {}
    try:
        trilha_id = parse_uuid(dados.get('trilhaId'))
    except ValueError:
        return _erro('dados_invalidos', 'A trilha selecionada não existe ou está inativa.', 422)
    trilhas_ativas = Trilha.query.filter_by(evento_id=chamada.evento_id, ativa=True).count()
    if trilhas_ativas and not trilha_id:
        return _erro(
            'dados_invalidos',
            'Verifique os campos destacados.',
            422,
            campos={'trilhaId': 'Selecione a trilha desta submissão.'},
        )

    if trilha_id is not None:
        trilha = Trilha.query.filter_by(id=trilha_id, evento_id=chamada.evento_id, ativa=True).first()
        if trilha is None:
            return _erro('dados_invalidos', 'A trilha selecionada não existe ou está inativa.', 422)

    submissao = Submissao(
        chamada_id=chamada.id,
        evento_id=chamada.evento_id,
        trilha_id=trilha_id,
        autor_responsavel_id=usuario.id,
        situacao='rascunho',
        fora_do_prazo=False,
        versao_formulario=1,
        formulario_versao_id=f'formulario-chamada-{chamada.id}-v1',
        respostas=json.dumps({}),
        data_ultimo_salvamento=datetime.utcnow(),
    )
    db.session.add(submissao)
    db.session.flush()
    db.session.add(Autoria(
        submissao_id=submissao.id,
        usuario_id=usuario.id,
        nome=usuario.nome,
        email=usuario.email,
        instituicao=usuario.instituicao or '',
        ordem=1,
        correspondente=True,
        eh_responsavel=True,
    ))
    db.session.commit()
    return jsonify(submissao.to_dict()), 201


@submissoes_bp.route('/submissoes/<uuid:submissao_id>', methods=['GET'])
def obter_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    resposta = submissao.to_dict()
    evento = Evento.query.get(submissao.evento_id)
    resposta['fusoDoEvento'] = evento.fuso if evento else ''
    return jsonify(resposta)


@submissoes_bp.route('/submissoes/<uuid:submissao_id>', methods=['PATCH'])
def atualizar_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao != 'rascunho':
        return _erro('submissao_nao_e_rascunho', 'Esta submissão não pode mais ser editada.', 409)

    dados = request.get_json(silent=True) or {}
    if 'trilhaId' in dados:
        try:
            trilha_id = parse_uuid(dados['trilhaId'])
        except ValueError:
            return _erro('dados_invalidos', 'A trilha selecionada não existe ou está inativa.', 422)
        trilha = Trilha.query.filter_by(id=trilha_id, evento_id=submissao.evento_id, ativa=True).first()
        if trilha is None:
            return _erro('dados_invalidos', 'A trilha selecionada não existe ou está inativa.', 422)
        submissao.trilha_id = trilha_id
    if 'respostas' in dados:
        if not isinstance(dados['respostas'], dict):
            return _erro('dados_invalidos', 'Respostas devem ser um objeto JSON.', 422)
        submissao.respostas = json.dumps(dados['respostas'])
    if 'identificadorExterno' in dados:
        submissao.identificador_externo = dados['identificadorExterno']

    submissao.data_ultimo_salvamento = datetime.utcnow()
    db.session.commit()
    return jsonify(submissao.to_dict())


@submissoes_bp.route('/submissoes/<uuid:submissao_id>', methods=['DELETE'])
def excluir_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao != 'rascunho':
        return _erro('submissao_nao_e_rascunho', 'Só é possível excluir uma submissão em rascunho.', 409)
    db.session.delete(submissao)
    db.session.commit()
    return '', 204


@submissoes_bp.route('/me/submissoes', methods=['GET'])
def listar_minhas_submissoes():
    usuario = _usuario()
    if usuario is None:
        return _erro('nao_autenticado', 'Sua sessão expirou.', 401)

    consulta = Submissao.query.filter_by(autor_responsavel_id=usuario.id)
    evento_id = request.args.get('evento')
    status = request.args.get('status')
    termo = (request.args.get('q') or '').lower()
    if evento_id:
        try:
            consulta = consulta.filter_by(evento_id=parse_uuid(evento_id))
        except ValueError:
            return jsonify([])
    if status:
        consulta = consulta.filter_by(situacao=status)

    resultados = [_resumo(item) for item in consulta.order_by(Submissao.criado_em.desc()).all()]
    if termo:
        resultados = [
            item for item in resultados
            if termo in item['titulo'].lower() or termo in (item['codigo'] or '').lower()
        ]
    return jsonify(resultados)


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/autorias', methods=['GET'])
def listar_autorias(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    autorias = Autoria.query.filter_by(submissao_id=submissao.id).order_by(Autoria.ordem).all()
    if not any(autoria.correspondente for autoria in autorias):
        for autoria in autorias:
            if autoria.eh_responsavel:
                autoria.correspondente = True
    return jsonify([autoria.to_dict() for autoria in autorias])


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/autorias', methods=['POST'])
def adicionar_autoria(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao != 'rascunho':
        return _erro('submissao_nao_e_rascunho', 'Esta submissão não pode mais ser editada.', 409)

    dados = request.get_json(silent=True) or {}
    email = (dados.get('email') or '').strip()
    if not email or not dados.get('nome'):
        return _erro('dados_invalidos', 'Nome e e-mail são obrigatórios.', 422)
    if Autoria.query.filter_by(submissao_id=submissao.id, email=email).first() is not None:
        return _erro('dados_invalidos', 'Este e-mail já foi adicionado a esta submissão.', 422,
                     campos={'email': 'Este e-mail já foi adicionado a esta submissão.'})

    usuario = Usuario.query.filter_by(email=email).first()
    ordem = Autoria.query.filter_by(submissao_id=submissao.id).count() + 1
    autoria = Autoria(
        submissao_id=submissao.id,
        usuario_id=usuario.id if usuario else None,
        nome=dados.get('nome'),
        email=email,
        instituicao=dados.get('instituicao') or '',
        ordem=ordem,
        correspondente=False,
        eh_responsavel=False,
    )
    db.session.add(autoria)
    db.session.commit()
    return jsonify(autoria.to_dict()), 201


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/autorias/<uuid:autor_id>', methods=['PATCH'])
def atualizar_autoria(submissao_id, autor_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    autoria = Autoria.query.filter_by(id=autor_id, submissao_id=submissao.id).first()
    if autoria is None:
        return _erro('autoria_inexistente', 'Autoria não encontrada.', 404)
    dados = request.get_json(silent=True) or {}
    if 'ordem' in dados:
        autoria.ordem = dados['ordem']
    if dados.get('correspondente') is True:
        Autoria.query.filter_by(submissao_id=submissao.id).update({'correspondente': False})
        autoria.correspondente = True
    elif dados.get('correspondente') is False:
        autoria.correspondente = False
    db.session.commit()
    return jsonify(autoria.to_dict())


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/autorias/<uuid:autor_id>', methods=['DELETE'])
def remover_autoria(submissao_id, autor_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    autoria = Autoria.query.filter_by(id=autor_id, submissao_id=submissao.id).first()
    if autoria is None:
        return _erro('autoria_inexistente', 'Autoria não encontrada.', 404)
    if autoria.eh_responsavel:
        return _erro('nao_pode_remover_responsavel', 'O autor responsável não pode ser removido da submissão.', 422)
    db.session.delete(autoria)
    db.session.commit()
    return '', 204


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/versoes', methods=['GET'])
def listar_versoes(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    versoes = VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).order_by(VersaoDeArquivo.numero).all()
    return jsonify([versao.to_dict() for versao in versoes])


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/versoes', methods=['POST'])
def criar_versao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    chamada = Chamada.query.get(submissao.chamada_id)
    if chamada is None:
        return _erro('chamada_inexistente', 'Chamada não encontrada.', 404)
    situacoes_reenvio = {'aguardando_rebuttal', 'aguardando_versao_corrigida'}
    encerrada = chamada.encerrada_manualmente or (chamada.data_limite and chamada.data_limite <= datetime.utcnow().isoformat()[:10])
    if encerrada and submissao.situacao not in situacoes_reenvio:
        return _erro('chamada_encerrada', 'Esta chamada está encerrada e não aceita novos envios.', 409)

    arquivo = request.files.get('arquivo')
    nome = request.form.get('nomeArquivo') or (arquivo.filename if arquivo else '')
    tamanho = int(request.form.get('tamanhoBytes') or (arquivo.content_length if arquivo else 0) or 0)
    if arquivo is None or not nome:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422, campos={'arquivo': 'Anexe um arquivo.'})

    extensao = nome.rsplit('.', 1)[-1].lower() if '.' in nome else ''
    formatos = _formatos_da_chamada(chamada.formatos_aceitos)
    if formatos and extensao not in formatos:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422,
                     campos={'arquivo': f"Formatos aceitos: {', '.join(formatos)}."})
    if chamada.tamanho_maximo_mb and tamanho > chamada.tamanho_maximo_mb * 1024 * 1024:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422,
                     campos={'arquivo': f'O tamanho máximo é {chamada.tamanho_maximo_mb}MB.'})

    anteriores = VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).all()
    for anterior in anteriores:
        anterior.vigente = False
    nome_seguro = secure_filename(nome) or 'arquivo'
    pasta = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
    os.makedirs(pasta, exist_ok=True)
    caminho = os.path.join(pasta, f'{submissao.id}-{len(anteriores) + 1}-{nome_seguro}')
    arquivo.save(caminho)
    usuario = _usuario()
    versao = VersaoDeArquivo(
        submissao_id=submissao.id,
        numero=len(anteriores) + 1,
        nome_original=nome,
        tamanho_bytes=tamanho,
        resumo_das_alteracoes=request.form.get('resumoDasAlteracoes'),
        enviado_por=usuario.nome,
        vigente=True,
        caminho_arquivo=caminho,
    )
    db.session.add(versao)
    db.session.commit()
    return jsonify(versao.to_dict()), 201


def _formatos_da_chamada(valor):
    if isinstance(valor, list):
        return [str(item).lower().lstrip('.') for item in valor]
    try:
        return [str(item).lower().lstrip('.') for item in json.loads(valor or '[]')]
    except (TypeError, ValueError):
        return []


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/confirmar', methods=['POST'])
def confirmar_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    evento = Evento.query.get(submissao.evento_id)
    if submissao.situacao != 'rascunho':
        return jsonify(_confirmacao(submissao, evento))

    respostas = submissao.respostas_dict()
    faltando = {}
    if not respostas.get('titulo'):
        faltando['titulo'] = 'Informe o título.'
    if not respostas.get('resumo'):
        faltando['resumo'] = 'Informe o resumo.'
    if not Autoria.query.filter_by(submissao_id=submissao.id).count():
        faltando['autores'] = 'Adicione ao menos um autor.'
    if not VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).count():
        faltando['arquivo'] = 'Envie o arquivo do trabalho.'
    if faltando:
        return _erro('dados_invalidos', 'Verifique os campos destacados.', 422, campos=faltando)

    chamada = Chamada.query.get(submissao.chamada_id)
    encerrada = chamada and (chamada.encerrada_manualmente or chamada.data_limite <= datetime.utcnow().isoformat()[:10])
    if encerrada and not chamada.permite_submissao_apos_prazo:
        return _erro('prazo_encerrado', 'O prazo desta chamada terminou e não permite envio fora do prazo.', 409)

    ultimo_numero = db.session.query(db.func.max(Submissao.numero)).scalar() or 0
    submissao.numero = ultimo_numero + 1
    submissao.codigo = f'SUB-{submissao.numero:04d}'
    submissao.situacao = 'submetida'
    submissao.fora_do_prazo = bool(encerrada)
    submissao.data_confirmacao = datetime.utcnow()
    db.session.commit()
    return jsonify(_confirmacao(submissao, evento))


def _confirmacao(submissao, evento):
    return {
        'submissaoId': str(submissao.id),
        'codigo': submissao.codigo or '',
        'situacao': submissao.situacao,
        'dataConfirmacao': submissao.data_confirmacao.isoformat() if submissao.data_confirmacao else '',
        'fusoDoEvento': evento.fuso if evento else '',
        'foraDoPrazo': submissao.fora_do_prazo,
    }


@submissoes_bp.route('/submissoes/<uuid:submissao_id>/retirar', methods=['POST'])
def retirar_submissao(submissao_id):
    submissao, erro = _submissao_do_autor(submissao_id)
    if erro:
        return erro
    if submissao.situacao in {'aceita', 'aceita_com_correcoes', 'rejeitada'}:
        return _erro('decisao_ja_emitida', 'Esta submissão já tem decisão emitida e não pode ser retirada.', 409)
    submissao.situacao = 'retirada'
    db.session.commit()
    return jsonify(submissao.to_dict())