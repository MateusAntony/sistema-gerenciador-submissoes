from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, request

from app.extensions import db
from app.controllers.auth_controller import usuario_autenticado
from app.models.evento import Evento, ParticipacaoEvento
from app.models.notificacao import Notificacao

notificacoes_bp = Blueprint('notificacoes', __name__, url_prefix='/api')


def _json_error(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


def _identificador_pagina(evento_id):
    evento = Evento.query.get(evento_id)
    return evento.identificador_pagina if evento is not None else None


def _eh_chair_ou_admin(usuario, evento_id):
    if usuario.administrador:
        return True
    participacao = ParticipacaoEvento.query.filter_by(
        usuario_id=usuario.id, evento_id=evento_id, papel='chair'
    ).first()
    return participacao is not None


def _enviar_notificacao_por_email(notificacao: Notificacao):
    """Retorna (sucesso, id_provedor_ou_mensagem_de_erro)."""
    api_key = current_app.config.get('BREVO_API_KEY')
    if not api_key:
        current_app.logger.info(
            'Reenviar notificação %s para %s: %s',
            notificacao.id, notificacao.destinatario_email, notificacao.assunto,
        )
        return True, None

    try:
        resposta = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={
                'api-key': api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            json={
                'sender': {
                    'name': current_app.config['BREVO_REMETENTE_NOME'],
                    'email': current_app.config['BREVO_REMETENTE_EMAIL'],
                },
                'to': [{
                    'email': notificacao.destinatario_email,
                    'name': notificacao.destinatario_nome,
                }],
                'subject': notificacao.assunto,
                'htmlContent': f'<p>{notificacao.assunto}</p>',
            },
            timeout=10,
        )
        if resposta.status_code < 300:
            return True, resposta.json().get('messageId')
        return False, resposta.text
    except requests.RequestException as erro:
        return False, str(erro)


@notificacoes_bp.route('/me/notificacoes', methods=['GET'])
def listar_minhas_notificacoes():
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    notificacoes = (
        Notificacao.query
        .filter_by(destinatario_id=usuario.id)
        .order_by(Notificacao.criada_em.desc())
        .all()
    )
    nao_lidas = sum(1 for n in notificacoes if n.lida_em is None)
    itens = [n.to_dict_usuario(_identificador_pagina(n.evento_id)) for n in notificacoes]
    return jsonify({'naoLidas': nao_lidas, 'itens': itens})


@notificacoes_bp.route('/me/notificacoes/<int:notificacao_id>/lida', methods=['POST'])
def marcar_notificacao_lida(notificacao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    notificacao = Notificacao.query.filter_by(id=notificacao_id, destinatario_id=usuario.id).first()
    if notificacao is None:
        return _json_error('notificacao_nao_encontrada', 'Notificação não encontrada.', 404)

    if notificacao.lida_em is None:
        notificacao.lida_em = datetime.utcnow()
        db.session.commit()

    return jsonify(notificacao.to_dict_usuario(_identificador_pagina(notificacao.evento_id)))


@notificacoes_bp.route('/me/notificacoes/ler-todas', methods=['POST'])
def marcar_todas_lidas():
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    agora = datetime.utcnow()
    (
        Notificacao.query
        .filter_by(destinatario_id=usuario.id, lida_em=None)
        .update({'lida_em': agora}, synchronize_session=False)
    )
    db.session.commit()
    return jsonify({'naoLidas': 0})


# --- P1: notificações do chair/admin ---

@notificacoes_bp.route('/eventos/<int:evento_id>/notificacoes', methods=['GET'])
def listar_notificacoes_do_evento(evento_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    evento = Evento.query.get(evento_id)
    if evento is None:
        return _json_error('evento_inexistente', 'Evento não encontrado.', 404)
    if not _eh_chair_ou_admin(usuario, evento_id):
        return _json_error(
            'sem_permissao', 'Você não tem permissão para ver as notificações deste evento.', 403
        )

    query = Notificacao.query.filter_by(evento_id=evento_id)
    status = request.args.get('status')
    if status:
        query = query.filter_by(situacao=status)
    tipo = request.args.get('tipo')
    if tipo:
        query = query.filter_by(tipo=tipo)

    notificacoes = query.order_by(Notificacao.criada_em.desc()).all()
    return jsonify([n.to_dict(evento.identificador_pagina) for n in notificacoes])


@notificacoes_bp.route('/notificacoes/<int:notificacao_id>/reenviar', methods=['POST'])
def reenviar_notificacao(notificacao_id):
    usuario = usuario_autenticado()
    if usuario is None:
        return _json_error('nao_autenticado', 'Sua sessão expirou.', 401)

    notificacao = Notificacao.query.get(notificacao_id)
    if notificacao is None:
        return _json_error('notificacao_nao_encontrada', 'Notificação não encontrada.', 404)
    if not _eh_chair_ou_admin(usuario, notificacao.evento_id):
        return _json_error(
            'sem_permissao', 'Você não tem permissão para reenviar esta notificação.', 403
        )
    if notificacao.tentativas >= notificacao.maximo_de_tentativas:
        return _json_error(
            'limite_atingido', 'O limite de tentativas de reenvio foi atingido.', 409
        )

    notificacao.tentativas += 1

    if notificacao.canal == 'email':
        sucesso, resultado = _enviar_notificacao_por_email(notificacao)
    else:
        sucesso, resultado = True, None

    if sucesso:
        notificacao.situacao = 'enviada'
        notificacao.id_provedor = resultado
        notificacao.erro_do_provedor = None
    else:
        notificacao.situacao = 'falha'
        notificacao.erro_do_provedor = resultado
        if notificacao.tentativas >= notificacao.maximo_de_tentativas:
            notificacao.administrador_avisado = True

    notificacao.atualizada_em = datetime.utcnow()
    db.session.commit()

    return jsonify(notificacao.to_dict(_identificador_pagina(notificacao.evento_id)))