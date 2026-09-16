from flask import Blueprint, request, jsonify, session
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    required_fields = ['nome', 'email', 'senha', 'instituicao', 'pais']
    
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Campos obrigatórios ausentes."}), 400

    try:
        user = AuthService.register_user(data)
        return jsonify({"message": "Usuário criado com sucesso", "user": user.to_dict()}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email')
    senha = data.get('senha')

    user = AuthService.authenticate_user(email, senha)
    if not user:
        return jsonify({"error": "Credenciais inválidas"}), 401

    # Armazena o ID na Sessão do Flask (gera Cookie assinado HTTP-Only)
    session['user_id'] = user.id
    return jsonify({"message": "Login realizado com sucesso", "user": user.to_dict()}), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"message": "Logout realizado com sucesso"}), 200

@auth_bp.route('/me', methods=['GET'])
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Não autenticado"}), 401
    
    user = UserRepository.get_by_id(user_id)
    return jsonify({"user": user.to_dict()}), 200


"""

from flask import Blueprint, current_app, request, jsonify, session
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')
public_bp = Blueprint('public', __name__, url_prefix='/api')

TEMPO_DE_EXPIRACAO_DO_TOKEN = 3600


def emitir_token_de_acesso(user_id: int) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps({'user_id': user_id}, salt='token-de-acesso')


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
    return UserRepository.get_by_id(dados.get('user_id'))


def usuario_autenticado():
    autorizacao = request.headers.get('Authorization', '')
    if autorizacao.startswith('Bearer '):
        usuario = usuario_do_token(autorizacao[7:])
        if usuario is not None:
            return usuario

    user_id = session.get('user_id')
    return UserRepository.get_by_id(user_id) if user_id else None


def resposta_de_erro(codigo: str, mensagem: str, status: int):
    return jsonify({
        'codigo': codigo,
        'mensagem': mensagem,
        'correlacao': f'cor-{codigo}',
    }), status

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

    # Armazena o ID na Sessão do Flask (gera Cookie assinado HTTP-Only)
    session['user_id'] = user.id
    return jsonify({
        'tokenDeAcesso': emitir_token_de_acesso(user.id),
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
    if user is None or not user.ativo:
        return resposta_de_erro('nao_autenticado', 'Sua sessão expirou.', 401)
    return jsonify({'tokenDeAcesso': emitir_token_de_acesso(user.id)}), 200

@auth_bp.route('/me', methods=['GET'])
def me():
    user = usuario_autenticado()
    if user is None or not user.ativo:
        return resposta_de_erro('nao_autenticado', 'Sua sessão expirou.', 401)
    return jsonify(user.to_dict()), 200


@public_bp.route('/me', methods=['GET'])
def me_from_frontend():
    return me()
"""