import requests
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.repositories.user_repository import UserRepository
from app.extensions import bcrypt

TEMPO_DE_EXPIRACAO_DO_TOKEN_DE_CONFIRMACAO = 60 * 60 * 24  # 24 horas


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
            instituicao=data['instituicao'],
            pais=data['pais']
        )

        token = AuthService.gerar_token_confirmacao(user.id)
        AuthService.enviar_email_confirmacao(user, token)
        return user

    @staticmethod
    def authenticate_user(email: str, password: str):
        user = UserRepository.get_by_email(email)
        if not user or not user.ativo:
            return None

        if bcrypt.check_password_hash(user.senha_hash, password):
            return user
        return None

    @staticmethod
    def gerar_token_confirmacao(user_id: int) -> str:
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps({'user_id': user_id}, salt='confirmacao-email')

    @staticmethod
    def enviar_email_confirmacao(usuario, token: str) -> None:
        link = f"{current_app.config['URL_BASE_FRONTEND']}/confirmar-email?token={token}"
        api_key = current_app.config.get('BREVO_API_KEY')

        if not api_key:
            current_app.logger.info('Enviar e-mail de confirmação para %s: %s', usuario.email, link)
            return

        try:
            resposta = requests.post(
                'https://api.brevo.com/v3/smtp/email',
                headers={
                    'api-key': api_key,
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                json={
                    'sender': {
                        'name': current_app.config['BREVO_REMETENTE_NOME'],
                        'email': current_app.config['BREVO_REMETENTE_EMAIL'],
                    },
                    'to': [{'email': usuario.email, 'name': usuario.nome}],
                    'subject': 'Confirme seu e-mail',
                    'htmlContent': (
                        f'<p>Olá, {usuario.nome}!</p>'
                        f'<p>Confirme seu e-mail clicando no link abaixo:</p>'
                        f'<p><a href="{link}">{link}</a></p>'
                        f'<p>Este link expira em 24 horas.</p>'
                    ),
                },
                timeout=10,
            )
            if resposta.status_code >= 300:
                current_app.logger.error(
                    'Falha ao enviar e-mail via Brevo (%s): %s',
                    resposta.status_code, resposta.text,
                )
        except requests.RequestException as erro:
            current_app.logger.error('Erro de rede ao enviar e-mail via Brevo: %s', erro)

    @staticmethod
    def confirmar_email(token: str):
        """Retorna (usuario, codigo_erro). codigo_erro é None em caso de sucesso."""
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            dados = serializer.loads(
                token,
                salt='confirmacao-email',
                max_age=TEMPO_DE_EXPIRACAO_DO_TOKEN_DE_CONFIRMACAO,
            )
        except SignatureExpired:
            return None, 'token_expirado'
        except BadSignature:
            return None, 'token_invalido'

        usuario = UserRepository.get_by_id(dados.get('user_id'))
        if usuario is None:
            return None, 'token_invalido'
        if usuario.email_confirmado:
            return usuario, 'token_ja_usado'

        usuario.email_confirmado = True
        UserRepository.update(usuario)
        return usuario, None