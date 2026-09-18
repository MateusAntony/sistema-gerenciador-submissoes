from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.controllers.auth_controller import usuario_autenticado
from app.models.evento import Chamada, ParticipacaoEvento
from app.models.formulario import FormularioVersao

formularios_bp = Blueprint('formularios', __name__, url_prefix='/api')

CAMPOS_OBRIGATORIOS_DO_CAMPO = ['chave', 'tipo', 'rotulo', 'obrigatorio', 'ordem', 'base']


def _json_error(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


def _eh_chair_do_evento(usuario, evento_id):
    if usuario.administrador:
        return True
    participacao = ParticipacaoEvento.query.filter_by(
        usuario_id=usuario.id, evento_id=evento_id, papel='chair'
    ).first()
    return participacao is not None


def _validar_campos(campos):
    """Retorna (campos_normalizados, erros). erros é um dict {indice: mensagem} ou {}."""
    erros = {}
    if not isinstance(campos, list) or len(campos) == 0:
        return None, {'campos': 'É preciso enviar ao menos um campo.'}

    chaves_vistas = set()
    for indice, campo in enumerate(campos):
        chave_erro = str(indice)
        if not isinstance(campo, dict):
            erros[chave_erro] = 'Campo inválido.'
            continue

        faltando = [c for c in CAMPOS_OBRIGATORIOS_DO_CAMPO if c not in campo]
        if faltando:
            erros[chave_erro] = f"Campos obrigatórios ausentes: {', '.join(faltando)}."
            continue

        chave = campo.get('chave')
        if not isinstance(chave, str) or not chave.strip():
            erros[chave_erro] = 'A chave do campo é obrigatória.'
            continue
        if chave in chaves_vistas:
            erros[chave_erro] = f"A chave '{chave}' está duplicada."
            continue
        chaves_vistas.add(chave)

        if not isinstance(campo.get('tipo'), str) or not campo['tipo'].strip():
            erros[chave_erro] = 'O tipo do campo é obrigatório.'
            continue
        if not isinstance(campo.get('rotulo'), str) or not campo['rotulo'].strip():
            erros[chave_erro] = 'O rótulo do campo é obrigatório.'
            continue
        if not isinstance(campo.get('obrigatorio'), bool):
            erros[chave_erro] = "O campo 'obrigatorio' deve ser verdadeiro ou falso."
            continue
        if not isinstance(campo.get('base'), bool):
            erros[chave_erro] = "O campo 'base' deve ser verdadeiro ou falso."
            continue
        if not isinstance(campo.get('ordem'), int):
            erros[chave_erro] = "O campo 'ordem' deve ser um número inteiro."
            continue

    if erros:
        return None, erros
    return campos, {}


@formularios_bp.route('/chamadas/<int:chamada_id>/formulario', methods=['GET'])
def obter_formulario(chamada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    versao_pedida = request.args.get('versao', 'publicada')
    status_alvo = 'publicado' if versao_pedida == 'publicada' else 'rascunho'

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('formulario_inexistente', 'Formulário não encontrado.', 404)

    if status_alvo == 'rascunho' and not _eh_chair_do_evento(usuario, chamada.evento_id):
        # Não revela a existência do rascunho para quem não é chair.
        return _json_error('formulario_inexistente', 'Formulário não encontrado.', 404)

    formulario = (
        FormularioVersao.query
        .filter_by(chamada_id=chamada_id, status=status_alvo)
        .order_by(FormularioVersao.versao.desc())
        .first()
    )
    if formulario is None:
        return _json_error('formulario_inexistente', 'Formulário não encontrado.', 404)

    return jsonify(formulario.to_dict())


@formularios_bp.route('/chamadas/<int:chamada_id>/formulario/rascunho', methods=['PUT'])
def salvar_rascunho_do_formulario(chamada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('formulario_inexistente', 'Formulário não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, chamada.evento_id):
        return _json_error('formulario_inexistente', 'Formulário não encontrado.', 404)

    dados = request.get_json() or {}
    versao_enviada = dados.get('versao')
    campos = dados.get('campos')

    if not isinstance(versao_enviada, int):
        return _json_error(
            'dados_invalidos', 'Dados inválidos.', 422,
            campos={'versao': 'A versão é obrigatória e deve ser um número inteiro.'},
        )

    campos_normalizados, erros = _validar_campos(campos)
    if erros:
        return _json_error('dados_invalidos', 'Dados inválidos.', 422, campos=erros)

    rascunho_atual = FormularioVersao.query.filter_by(
        chamada_id=chamada_id, status='rascunho'
    ).first()

    if rascunho_atual is not None:
        # Editando o rascunho existente: a versão enviada precisa bater com a dele.
        if rascunho_atual.versao != versao_enviada:
            return _json_error('conflito', 'Este rascunho foi alterado por outra pessoa.', 409)
        rascunho_atual.set_campos(campos_normalizados)
        rascunho_atual.atualizado_em = datetime.utcnow()
        db.session.commit()
        return jsonify(rascunho_atual.to_dict())

    # Não há rascunho ativo: a próxima versão é a última publicada + 1 (ou 1, se nunca houve nenhuma).
    ultima_versao = (
        db.session.query(db.func.max(FormularioVersao.versao))
        .filter_by(chamada_id=chamada_id)
        .scalar()
    )
    versao_esperada = (ultima_versao or 0) + 1
    if versao_enviada != versao_esperada:
        return _json_error('conflito', 'A versão informada está desatualizada.', 409)

    novo_rascunho = FormularioVersao(
        chamada_id=chamada_id,
        versao=versao_enviada,
        status='rascunho',
    )
    novo_rascunho.set_campos(campos_normalizados)
    db.session.add(novo_rascunho)
    db.session.commit()
    return jsonify(novo_rascunho.to_dict())


@formularios_bp.route('/chamadas/<int:chamada_id>/formulario/publicar', methods=['POST'])
def publicar_formulario(chamada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return _json_error('rascunho_inexistente', 'Rascunho não encontrado.', 404)
    if not _eh_chair_do_evento(usuario, chamada.evento_id):
        return _json_error('rascunho_inexistente', 'Rascunho não encontrado.', 404)

    dados = request.get_json() or {}
    versao_enviada = dados.get('versao')

    rascunho = FormularioVersao.query.filter_by(chamada_id=chamada_id, status='rascunho').first()
    if rascunho is None:
        return _json_error('rascunho_inexistente', 'Rascunho não encontrado.', 404)
    if rascunho.versao != versao_enviada:
        return _json_error('conflito', 'O rascunho foi alterado por outra pessoa.', 409)

    rascunho.status = 'publicado'
    rascunho.publicado_em = datetime.utcnow()
    rascunho.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(rascunho.to_dict())


@formularios_bp.route('/chamadas/<int:chamada_id>/formulario/versoes', methods=['GET'])
def listar_versoes_do_formulario(chamada_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    chamada = Chamada.query.get(chamada_id)
    if chamada is None:
        return jsonify([])
    if not _eh_chair_do_evento(usuario, chamada.evento_id):
        return jsonify([])

    versoes = (
        FormularioVersao.query
        .filter_by(chamada_id=chamada_id)
        .order_by(FormularioVersao.versao.desc())
        .all()
    )
    return jsonify([v.to_dict() for v in versoes])