from app.repositories.user_repository import UserRepository
from app.extensions import bcrypt

class AuthService:
    @staticmethod
    def register_user(data: dict):
        if UserRepository.get_by_email(data.get('email')):
            raise ValueError("E-mail já cadastrado.")

        hashed_password = bcrypt.generate_password_hash(data['senha']).decode('utf-8')
        
        user = UserRepository.create(
            nome=data['nome'],
            email=data['email'],
            senha_hash=hashed_password,
            instituicao=data.get('instituicao')
        )
        return user

    @staticmethod
    def authenticate_user(email: str, password: str):
        user = UserRepository.get_by_email(email)
        if not user or not user.ativo:
            return None
        
        if bcrypt.check_password_hash(user.senha_hash, password):
            return user
        return None
