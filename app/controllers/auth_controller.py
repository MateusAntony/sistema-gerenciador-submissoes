from flask import Blueprint, current_app, request, jsonify, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
public_bp = Blueprint('public', __name__, url_prefix='/api')

TEMPO_DE_EXPIRACAO_DO_TOKEN = 3600


def emitir_token_de_acesso(usuario) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(
        {'user_id': usuario.id, 'fingerprint': AuthService.fingerprint_da_senha(usuario)},
        salt='token-de-acesso',
    )


def usuario_do_token(token: str):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        dados = serializer.loads(
            token,
            salt='token-de-acesso',
            max_age=TEMPO_DE_EXPIRACAO_DO_TOKEN,
        )
    except (BadSignature, SignatureExpired):
        return None
    usuario = UserRepository.get_by_id(dados.get('user_id'))
    if usuario is None or dados.get('fingerprint') != AuthService.fingerprint_da_senha(usuario):
        return None
    return usuario


def usuario_autenticado():
    autorizacao = request.headers.get('Authorization', '')
    if autorizacao.startswith('Bearer '):
        usuario = usuario_do_token(autorizacao[7:])
        if usuario is not None:
            return usuario

    user_id = session.get('user_id')
    if not user_id:
        return None
    usuario = UserRepository.get_by_id(user_id)
    if usuario is None or session.get('senha_fingerprint') != AuthService.fingerprint_da_senha(usuario):
        return None
    return usuario


def iniciar_sessao(usuario) -> None:
    """Sessão permanente (B6) com fingerprint da senha (A6, revisão do
    Lince): PERMANENT_SESSION_LIFETIME é ignorado sem session.permanent, e
    sem o fingerprint uma sessão de 7 dias sobreviveria à própria troca de
    senha."""
    session.permanent = True
    session['user_id'] = usuario.id
    session['senha_fingerprint'] = AuthService.fingerprint_da_senha(usuario)


def _corpo_json() -> dict:
    """`get_json(silent=True)` nunca levanta (corpo ausente, não-JSON ou mal
    formado viram None) e o `isinstance` recusa um corpo que não seja objeto
    (lista, número) — sem isto, e-mail/token/senha de tipo errado geravam 500
    em vez do 204/400/422 que o contrato promete sempre devolver."""
    dados = request.get_json(silent=True)
    return dados if isinstance(dados, dict) else {}


def _texto(dados: dict, campo: str) -> str:
    valor = dados.get(campo)
    return valor if isinstance(valor, str) else ''


def resposta_de_erro(codigo: str, mensagem: str, status: int, **extra):
    payload = {
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }
    payload.update(extra)
    return jsonify(payload), status


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    required_fields = ['nome', 'email', 'senha', 'instituicao', 'pais']

    if not all(field in data for field in required_fields):
        return resposta_de_erro('campos_obrigatorios', 'Campos obrigatórios ausentes.', 400)

    try:
        user = AuthService.register_user(data)
        return jsonify({"message": "Usuário criado com sucesso", "user": user.to_dict()}), 201
    except ValueError as e:
        return resposta_de_erro('cadastro_invalido', str(e), 400)


@public_bp.route('/usuarios', methods=['POST'])
def register_from_frontend():
    return register()


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    senha = data.get('senha')

    user = AuthService.authenticate_user(email, senha)
    if not user:
        return resposta_de_erro('credenciais_invalidas', 'E-mail ou senha inválidos', 401)
    if not user.email_confirmado:
        return resposta_de_erro(
            'email_nao_confirmado',
            'Confirme seu e-mail para entrar no sistema.',
            403,
        )

    iniciar_sessao(user)
    return jsonify({
        'tokenDeAcesso': emitir_token_de_acesso(user),
        'usuario': user.to_dict(),
    }), 200


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return '', 204


@auth_bp.route('/refresh', methods=['POST'])
def refresh():
    user_id = session.get('user_id')
    user = UserRepository.get_by_id(user_id) if user_id else None
    if (
        user is None
        or not user.ativo
        or session.get('senha_fingerprint') != AuthService.fingerprint_da_senha(user)
    ):
        return resposta_de_erro('nao_autenticado', 'Sua sessão expirou.', 401)
    return jsonify({'tokenDeAcesso': emitir_token_de_acesso(user)}), 200


@auth_bp.route('/me', methods=['GET'])
def me():
    user = usuario_autenticado()
    if user is None or not user.ativo:
        return resposta_de_erro('nao_autenticado', 'Sua sessão expirou.', 401)
    return jsonify(user.to_dict()), 200


@public_bp.route('/me', methods=['GET'])
def me_from_frontend():
    return me()



@auth_bp.route('/confirmar-email', methods=['POST'])
def confirmar_email():
    dados = request.get_json() or {}
    token = dados.get('token')
    if not token:
        return resposta_de_erro('token_invalido', 'Token inválido.', 404)

    usuario, codigo_erro = AuthService.confirmar_email(token)
    if codigo_erro == 'token_expirado':
        return resposta_de_erro('token_expirado', 'Este link de confirmação expirou.', 410)
    if codigo_erro == 'token_ja_usado':
        return resposta_de_erro('token_ja_usado', 'Este e-mail já foi confirmado.', 409)
    if codigo_erro == 'token_invalido' or usuario is None:
        return resposta_de_erro('token_invalido', 'Token inválido.', 404)

    return jsonify({'email': usuario.email}), 200


@auth_bp.route('/reenviar-confirmacao', methods=['POST'])
def reenviar_confirmacao():
    dados = request.get_json() or {}
    email = (dados.get('email') or '').strip()
    if email:
        usuario = UserRepository.get_by_email(email)
        if usuario is not None and not usuario.email_confirmado:
            token = AuthService.gerar_token_confirmacao(usuario.id)
            AuthService.enviar_email_confirmacao(usuario, token)
    return jsonify({'esperarSegundos': 60}), 200


@auth_bp.route('/recuperar-senha', methods=['POST'])
def recuperar_senha():
    dados = _corpo_json()
    email = _texto(dados, 'email').strip()
    if email:
        usuario = UserRepository.get_by_email(email)
        if usuario is not None:
            token = AuthService.gerar_token_redefinicao(usuario)
            AuthService.enviar_email_redefinicao(usuario, token)
    # 204 sempre: não revela se o e-mail existe (mesmo comportamento para
    # conta inexistente e conta real, evitando oráculo de enumeração).
    return '', 204


@auth_bp.route('/redefinir-senha', methods=['POST'])
def redefinir_senha():
    dados = _corpo_json()
    token = _texto(dados, 'token')
    senha = _texto(dados, 'senha')

    codigo_erro = AuthService.redefinir_senha(token, senha)
    if codigo_erro == 'token_invalido':
        return resposta_de_erro('token_invalido', 'Token inválido ou expirado.', 400)
    if codigo_erro == 'senha_fraca':
        return resposta_de_erro(
            'senha_fraca',
            'A senha não atende aos requisitos.',
            422,
            campos={'senha': 'A senha precisa ter ao menos 8 caracteres e combinar letras e números.'},
        )
    return '', 204