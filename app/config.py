import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'chave-secreta-segura')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL', 
        'postgresql://postgres:postgres@db:5432/sgs_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuração de Cookies de Sessão Seguros
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False  # Mudar para True apenas em HTTPS/Produção
