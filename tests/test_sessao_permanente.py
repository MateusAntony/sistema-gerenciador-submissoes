"""B6: sessão permanente, com validade coerente com a renovação do front.

O front só renova o token de acesso (validade de 1h) reagindo a um 401,
usando o cookie de sessão — não há renovação por timer. Por isso
PERMANENT_SESSION_LIFETIME precisa ser maior que a validade do token de
acesso: senão o cookie de sessão já teria expirado junto com o token, e a
renovação nunca teria efeito.
"""
from datetime import timedelta

from app.controllers.auth_controller import TEMPO_DE_EXPIRACAO_DO_TOKEN


def test_permanent_session_lifetime_maior_que_o_token_de_acesso(app):
    lifetime = app.config['PERMANENT_SESSION_LIFETIME']
    assert isinstance(lifetime, timedelta)
    assert lifetime.total_seconds() > TEMPO_DE_EXPIRACAO_DO_TOKEN


def test_login_marca_a_sessao_como_permanente(fabrica):
    usuario = fabrica.usuario(senha='senha-bem-forte-1')
    cliente = fabrica.cliente()

    resposta = cliente.post('/api/auth/login', json={'email': usuario.email, 'senha': 'senha-bem-forte-1'})

    assert resposta.status_code == 200
    with cliente.session_transaction() as sessao:
        assert sessao.permanent is True


def test_cookie_de_sessao_do_login_tem_expiracao_coerente_com_o_lifetime(app, fabrica):
    usuario = fabrica.usuario(senha='senha-bem-forte-1')
    cliente = fabrica.cliente()

    resposta = cliente.post('/api/auth/login', json={'email': usuario.email, 'senha': 'senha-bem-forte-1'})
    assert resposta.status_code == 200

    cookie = cliente.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    assert cookie.expires is not None or cookie.max_age is not None
