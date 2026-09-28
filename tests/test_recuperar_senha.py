"""A6: recuperar-senha (sempre 204) e redefinir-senha (token de uso único)."""
import time

from app.extensions import bcrypt
from app.models.user import Usuario
from app.services.auth_service import AuthService


def test_recuperar_senha_sempre_204_mesmo_para_email_inexistente(fabrica):
    cliente = fabrica.cliente()

    resposta = cliente.post('/api/auth/recuperar-senha', json={'email': 'ninguem@teste.br'})

    assert resposta.status_code == 204


def test_recuperar_senha_204_para_email_existente_e_loga_o_link(fabrica, caplog):
    usuario = fabrica.usuario(email='dona@teste.br')
    cliente = fabrica.cliente()

    with caplog.at_level('INFO'):
        resposta = cliente.post('/api/auth/recuperar-senha', json={'email': usuario.email})

    assert resposta.status_code == 204
    assert 'redefinir-senha?token=' in caplog.text


def test_redefinir_senha_com_token_valido_troca_a_senha(app, fabrica):
    usuario = fabrica.usuario(email='dona@teste.br', senha='senha-antiga-1')
    cliente = fabrica.cliente()
    with app.app_context():
        token = AuthService.gerar_token_redefinicao(usuario)

    resposta = cliente.post('/api/auth/redefinir-senha', json={
        'token': token, 'senha': 'senha-nova-2',
    })

    assert resposta.status_code == 204
    atualizado = Usuario.query.get(usuario.id)
    assert bcrypt.check_password_hash(atualizado.senha_hash, 'senha-nova-2')
    assert not bcrypt.check_password_hash(atualizado.senha_hash, 'senha-antiga-1')


def test_redefinir_senha_permite_login_com_a_senha_nova(app, fabrica):
    usuario = fabrica.usuario(email='dona@teste.br', senha='senha-antiga-1')
    cliente = fabrica.cliente()
    with app.app_context():
        token = AuthService.gerar_token_redefinicao(usuario)
    cliente.post('/api/auth/redefinir-senha', json={'token': token, 'senha': 'senha-nova-2'})

    login = cliente.post('/api/auth/login', json={'email': usuario.email, 'senha': 'senha-nova-2'})

    assert login.status_code == 200


def test_redefinir_senha_com_token_invalido_400(fabrica):
    cliente = fabrica.cliente()

    resposta = cliente.post('/api/auth/redefinir-senha', json={
        'token': 'isto-nao-e-um-token', 'senha': 'senha-nova-2',
    })

    assert resposta.status_code == 400
    assert resposta.get_json()['codigo'] == 'token_invalido'


def test_redefinir_senha_sem_token_400(fabrica):
    cliente = fabrica.cliente()

    resposta = cliente.post('/api/auth/redefinir-senha', json={'senha': 'senha-nova-2'})

    assert resposta.status_code == 400
    assert resposta.get_json()['codigo'] == 'token_invalido'


def test_redefinir_senha_com_token_expirado_400(app, fabrica, monkeypatch):
    usuario = fabrica.usuario(email='dona@teste.br')
    cliente = fabrica.cliente()
    tempo_real = time.time()
    with app.app_context():
        with monkeypatch.context() as m:
            m.setattr('itsdangerous.timed.time.time', lambda: tempo_real - 3601)
            token = AuthService.gerar_token_redefinicao(usuario)

    resposta = cliente.post('/api/auth/redefinir-senha', json={
        'token': token, 'senha': 'senha-nova-2',
    })

    assert resposta.status_code == 400
    assert resposta.get_json()['codigo'] == 'token_invalido'


def test_redefinir_senha_e_de_uso_unico(app, fabrica):
    usuario = fabrica.usuario(email='dona@teste.br', senha='senha-antiga-1')
    cliente = fabrica.cliente()
    with app.app_context():
        token = AuthService.gerar_token_redefinicao(usuario)

    primeira = cliente.post('/api/auth/redefinir-senha', json={'token': token, 'senha': 'senha-nova-2'})
    assert primeira.status_code == 204

    segunda = cliente.post('/api/auth/redefinir-senha', json={'token': token, 'senha': 'senha-nova-3'})

    assert segunda.status_code == 400
    assert segunda.get_json()['codigo'] == 'token_invalido'
    # a senha da primeira troca continua valendo — a segunda tentativa não teve efeito.
    atualizado = Usuario.query.get(usuario.id)
    assert bcrypt.check_password_hash(atualizado.senha_hash, 'senha-nova-2')


def test_redefinir_senha_fraca_422_com_campos_senha(app, fabrica):
    usuario = fabrica.usuario(email='dona@teste.br')
    cliente = fabrica.cliente()
    with app.app_context():
        token = AuthService.gerar_token_redefinicao(usuario)

    resposta = cliente.post('/api/auth/redefinir-senha', json={'token': token, 'senha': 'curta1'})

    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo['codigo'] == 'senha_fraca'
    assert 'senha' in corpo['campos']


def test_redefinir_senha_so_letras_tambem_e_fraca(app, fabrica):
    usuario = fabrica.usuario(email='dona@teste.br')
    cliente = fabrica.cliente()
    with app.app_context():
        token = AuthService.gerar_token_redefinicao(usuario)

    resposta = cliente.post('/api/auth/redefinir-senha', json={'token': token, 'senha': 'somenteletras'})

    assert resposta.status_code == 422
    assert resposta.get_json()['codigo'] == 'senha_fraca'
