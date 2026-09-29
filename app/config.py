import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def get_required_env(var_name: str) -> str:
    value = os.getenv(var_name)
    if not value:
        raise ValueError(f"A variável de ambiente obrigatória '{var_name}' não foi definida!")
    return value

class Config:
    SECRET_KEY = get_required_env('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = get_required_env('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuração de Cookies de Sessão Seguros
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Mudar para True apenas em HTTPS/Produção

    # B6: o front só renova o token de acesso (validade de 1h) reagindo a um
    # 401, usando o cookie de sessão — não há renovação por timer. Por isso a
    # sessão precisa durar bem mais que 1h, senão o cookie já teria expirado
    # junto com o token na primeira renovação e a "renovação" nunca ajudaria.
    PERMANENT_SESSION_LIFETIME = timedelta(
        seconds=int(os.getenv('PERMANENT_SESSION_LIFETIME_SEGUNDOS', str(60 * 60 * 24 * 7)))
    )

    # E-mail transacional (Brevo)
    BREVO_API_KEY = os.getenv('BREVO_API_KEY')
    BREVO_REMETENTE_EMAIL = os.getenv('BREVO_REMETENTE_EMAIL', 'nao-responda@seudominio.com')
    BREVO_REMETENTE_NOME = os.getenv('BREVO_REMETENTE_NOME', 'Sistema de Submissões')
    URL_BASE_FRONTEND = os.getenv('URL_BASE_FRONTEND', 'http://localhost:5173')

    # Arquivos das submissões (versões) enviados pelos autores.
    PASTA_UPLOADS = os.getenv(
        'PASTA_UPLOADS',
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'uploads'),
    )