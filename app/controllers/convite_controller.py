from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.extensions import db, bcrypt
from app.controllers.auth_controller import emitir_token_de_acesso
from app.models.evento import Evento, ParticipacaoEvento, Submissao
from app.models.atribuicao import Atribuicao
from app.models.user import Usuario

convites_bp = Blueprint('convites', __name__, url_prefix='/api')

DIAS_VALIDADE_CONVITE = 30


def _json_error(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


def _decodificar_token(token):
    """Retorna (dados, erro). erro é um dos: 'invalido' | 'expirado' | None."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        dados = serializer.loads(token, salt='convite', max_age=DIAS_VALIDADE_CONVITE * 86400)
    except SignatureExpired:
        return None, 'expirado'
    except BadSignature:
        return None, 'invalido'
    return dados, None


def _resolver_convite(token):
    """Retorna (contexto, erro_http). contexto traz tudo que as duas rotas precisam."""
    dados, erro = _decodificar_token(token)
    if erro == 'expirado':
        return None, _json_error('convite_expirado', 'Este convite expirou.', 410)
    if erro == 'invalido' or not isinstance(dados, dict) or 'tipo' not in dados:
        return None, _json_error('convite_invalido', 'Convite inválido.', 404)

    if dados['tipo'] == 'atribuicao':
        atribuicao = Atribuicao.query.get(dados.get('atribuicaoId'))
        if atribuicao is None:
            return None, _json_error('convite_invalido', 'Convite inválido.', 404)
        if atribuicao.situacao != 'convidado':
            return None, _json_error('convite_ja_usado', 'Este convite já foi utilizado.', 409)

        submissao = Submissao.query.get(atribuicao.submissao_id)
        evento = Evento.query.get(atribuicao.evento_id)
        convidador = Usuario.query.get(atribuicao.convidado_por_id) if atribuicao.convidado_por_id else None
        conta_existente = Usuario.query.filter_by(email=atribuicao.avaliador_email, ativo=True).first()

        return {
            'tipo': 'atribuicao',
            'atribuicao': atribuicao,
            'submissao': submissao,
            'evento': evento,
            'email': atribuicao.avaliador_email,
            'nome_sugerido': atribuicao.avaliador_nome,
            'prazo': atribuicao.prazo_resposta,
            'contato': convidador.email if convidador else current_app.config.get('BREVO_REMETENTE_EMAIL'),
            'precisa_criar_conta': conta_existente is None,
            'conta_existente': conta_existente,
        }, None

    if dados['tipo'] == 'participacao':
        evento = Evento.query.get(dados.get('eventoId'))
        if evento is None:
            return None, _json_error('convite_invalido', 'Convite inválido.', 404)

        email = dados.get('email')
        papel = dados.get('papel')
        conta_existente = Usuario.query.filter_by(email=email, ativo=True).first()
        if conta_existente is not None:
            ja_participa = ParticipacaoEvento.query.filter_by(
                usuario_id=conta_existente.id, evento_id=evento.id, papel=papel
            ).first()
            if ja_participa is not None:
                return None, _json_error('convite_ja_usado', 'Este convite já foi utilizado.', 409)

        return {
            'tipo': 'participacao',
            'evento': evento,
            'papel': papel,
            'email': email,
            'nome_sugerido': email,
            'prazo': None,
            'contato': current_app.config.get('BREVO_REMETENTE_EMAIL'),
            'precisa_criar_conta': conta_existente is None,
            'conta_existente': conta_existente,
        }, None

    return None, _json_error('convite_invalido', 'Convite inválido.', 404)


@convites_bp.route('/convites/<token>', methods=['GET'])
def obter_convite(token):
    contexto, erro = _resolver_convite(token)
    if erro:
        return erro

    return jsonify({
        'email': contexto['email'],
        'eventoTitulo': contexto['evento'].titulo if contexto['evento'] else '',
        'submissaoTitulo': (
            contexto['submissao'].respostas_dict().get('titulo') if contexto.get('submissao') else None
        ),
        'prazo': contexto['prazo'].isoformat() if contexto['prazo'] else None,
        'fuso': contexto['evento'].fuso if contexto['evento'] else '',
        'contatoDaOrganizacao': contexto['contato'],
        'precisaCriarConta': contexto['precisa_criar_conta'],
    })


@convites_bp.route('/convites/<token>/aceitar', methods=['POST'])
def aceitar_convite(token):
    contexto, erro = _resolver_convite(token)
    if erro:
        return erro

    dados = request.get_json(silent=True) or {}

    if contexto['precisa_criar_conta']:
        nome = (dados.get('nome') or '').strip()
        senha = dados.get('senha') or ''
        if not nome or not senha:
            return _json_error(
                'dados_obrigatorios', 'Informe nome e senha para criar sua conta.', 422,
                campos={
                    'nome': None if nome else 'O nome é obrigatório.',
                    'senha': None if senha else 'A senha é obrigatória.',
                },
            )
        usuario_final = Usuario(
            nome=nome,
            email=contexto['email'],
            senha_hash=bcrypt.generate_password_hash(senha).decode('utf-8'),
            email_confirmado=True,  # o próprio link de convite já comprova a posse do e-mail
            ativo=True,
        )
        db.session.add(usuario_final)
        db.session.flush()
    else:
        usuario_final = contexto['conta_existente']

    if contexto['tipo'] == 'atribuicao':
        atribuicao = contexto['atribuicao']
        atribuicao.avaliador_id = usuario_final.id
        atribuicao.situacao = 'aceito'
        atribuicao.respondido_em = datetime.utcnow()
        destino = f'/atribuicoes/{atribuicao.id}'
    else:
        ja_participa = ParticipacaoEvento.query.filter_by(
            usuario_id=usuario_final.id, evento_id=contexto['evento'].id, papel=contexto['papel']
        ).first()
        if ja_participa is None:
            db.session.add(ParticipacaoEvento(
                usuario_id=usuario_final.id, evento_id=contexto['evento'].id, papel=contexto['papel']
            ))
        destino = '/'

    db.session.commit()

    session['user_id'] = usuario_final.id
    return jsonify({
        'tokenDeAcesso': emitir_token_de_acesso(usuario_final.id),
        'usuario': usuario_final.to_dict(),
        'destino': destino,
    })