"""Impedimento de autoria: quem é autor ou coautor da submissão não a avalia."""
from sqlalchemy import func

from app.models.evento import Autoria
from app.models.user import Usuario


def _normalizar_email(email):
    return (email or '').strip().lower()


def conta_ativa_por_email(email):
    email = _normalizar_email(email)
    if not email:
        return None
    return Usuario.query.filter(func.lower(Usuario.email) == email, Usuario.ativo.is_(True)).first()


def impedimento_de_autoria(submissao, usuario_id=None, email=None):
    """'autor', 'coautor' ou None. Confere a conta (pelo id ou, sem id, pela
    conta ativa com o e-mail) e também o e-mail contra as autorias: um convite
    só por e-mail não pode escapar do impedimento."""
    email = _normalizar_email(email)
    if usuario_id is None and email:
        conta = conta_ativa_por_email(email)
        usuario_id = conta.id if conta else None
    if usuario_id is not None:
        if submissao.autor_responsavel_id == usuario_id:
            return 'autor'
        if Autoria.query.filter_by(submissao_id=submissao.id, usuario_id=usuario_id).first():
            return 'coautor'
    if email:
        autoria = Autoria.query.filter(
            Autoria.submissao_id == submissao.id,
            func.lower(func.trim(Autoria.email)) == email,
        ).first()
        if autoria is not None:
            return 'autor' if autoria.eh_responsavel else 'coautor'
    return None
