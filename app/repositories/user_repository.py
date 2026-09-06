from app.models.user import Usuario
from app.extensions import db

class UserRepository:
    @staticmethod
    def get_by_email(email: str) -> Usuario:
        return Usuario.query.filter_by(email=email).first()

    @staticmethod
    def get_by_id(user_id: int) -> Usuario:
        return Usuario.query.get(user_id)

    @staticmethod
    def create(nome: str, email: str, senha_hash: str, instituicao: str = None, pais: str = None) -> Usuario:
        user = Usuario(
            nome=nome,
            email=email,
            senha_hash=senha_hash,
            instituicao=instituicao,
            pais=pais
        )
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def update(user: Usuario) -> Usuario:
        db.session.commit()
        return user

    @staticmethod
    def delete(user: Usuario) -> None:
        db.session.delete(user)
        db.session.commit()
