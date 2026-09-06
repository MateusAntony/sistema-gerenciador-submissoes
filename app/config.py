import os

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
