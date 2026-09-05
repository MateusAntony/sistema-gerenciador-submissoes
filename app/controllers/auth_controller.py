from flask import Blueprint, request, jsonify, session
from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    required_fields = ['nome', 'email', 'senha']
    
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
