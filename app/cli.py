import click

from app.repositories.user_repository import UserRepository


def registrar_comandos(app):
    @app.cli.command('criar-admin')
    @click.argument('email')
    def criar_admin(email):
        """Promove um usuário já cadastrado a administrador."""
        usuario = UserRepository.get_by_email(email)
        if usuario is None:
            click.echo(f'Nenhum usuário encontrado com o e-mail {email}.')
            raise SystemExit(1)

        usuario.administrador = True
        UserRepository.update(usuario)
        click.echo(f'{email} agora é administrador.')
