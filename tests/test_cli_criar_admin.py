"""B7: comando `flask criar-admin <email>` promove um usuário existente."""
from app.models.user import Usuario


def test_criar_admin_promove_usuario_existente(app, fabrica):
    usuario = fabrica.usuario(email='futura-admin@teste.br', administrador=False)
    runner = app.test_cli_runner()

    resultado = runner.invoke(args=['criar-admin', usuario.email])

    assert resultado.exit_code == 0
    atualizado = Usuario.query.get(usuario.id)
    assert atualizado.administrador is True


def test_criar_admin_com_email_inexistente_nao_promove_ninguem(app, fabrica):
    fabrica.usuario(email='alguem@teste.br', administrador=False)
    runner = app.test_cli_runner()

    resultado = runner.invoke(args=['criar-admin', 'nao-existe@teste.br'])

    assert resultado.exit_code != 0
    assert Usuario.query.filter_by(administrador=True).count() == 0
