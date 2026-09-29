"""Furo pré-existente apontado pelo Lince: autor avaliando o próprio
trabalho pelo convite só por e-mail (sem avaliadorId) e pelo aceite do
link do convite."""
import pytest

from app.extensions import db
from app.models.atribuicao import Atribuicao
from app.models.evento import Autoria


@pytest.fixture
def cenario(fabrica):
    autora, chair = fabrica.usuario('Autora', email='autora@qa.br'), fabrica.usuario('Chair')
    submissao_id = fabrica.submissao_confirmada(autora, fabrica.chamada(fabrica.evento(chair=chair)))
    return {'autora': autora, 'chair': chair, 'submissao_id': submissao_id,
            'rodada_id': fabrica.rodada_atual(submissao_id).id}


def _convidar_por_email(fabrica, cenario, email, nome='Pessoa', avaliador_id=None):
    item = {'nome': nome, 'email': email}
    if avaliador_id is not None:
        item['avaliadorId'] = avaliador_id
    [resultado] = fabrica.cliente(cenario['chair']).post(
        f"/api/rodadas/{cenario['rodada_id']}/atribuicoes", json=[item]).get_json()
    return resultado


@pytest.mark.parametrize('avaliador_id', [None, ''])
def test_convite_so_por_email_da_autora_e_impedido(fabrica, cenario, avaliador_id):
    resultado = _convidar_por_email(fabrica, cenario, 'AUTORA@qa.br ', avaliador_id=avaliador_id)

    assert resultado['sucesso'] is False and resultado['codigo'] == 'autor'
    assert Atribuicao.query.count() == 0


def test_convite_por_email_de_coautor_com_conta_e_impedido(fabrica, cenario):
    coautor = fabrica.usuario('Coautor', email='coautor@qa.br')
    db.session.add(Autoria(submissao_id=cenario['submissao_id'], usuario_id=coautor.id,
                           nome=coautor.nome, email=coautor.email, ordem=2))
    db.session.commit()

    resultado = _convidar_por_email(fabrica, cenario, 'coautor@qa.br')

    assert resultado['sucesso'] is False and resultado['codigo'] == 'coautor'


def test_convite_por_email_de_coautor_sem_conta_e_impedido(fabrica, cenario):
    db.session.add(Autoria(submissao_id=cenario['submissao_id'], nome='Nina', email='nina@qa.br', ordem=2))
    db.session.commit()

    resultado = _convidar_por_email(fabrica, cenario, 'Nina@qa.br')

    assert resultado['sucesso'] is False and resultado['codigo'] == 'coautor'


def test_convite_por_email_de_pessoa_sem_vinculo_continua_valendo(fabrica, cenario):
    resultado = _convidar_por_email(fabrica, cenario, 'externa@qa.br')
    assert resultado['sucesso'] is True


def _token_do_convite(fabrica, atribuicao_id, email):
    from app.controllers.avaliacao_controller import gerar_token_convite_atribuicao
    return gerar_token_convite_atribuicao(atribuicao_id, email)


def test_aceitar_convite_como_autora_e_recusado(fabrica, cenario):
    # Atribuição sem_cadastro já existente (criada antes da correção do convite,
    # ou com e-mail que depois virou a conta da autora).
    atribuicao = Atribuicao(
        rodada_id=cenario['rodada_id'], submissao_id=cenario['submissao_id'],
        evento_id=fabrica.rodada_atual(cenario['submissao_id']).evento_id,
        situacao='convidado', avaliador_nome='Autora', avaliador_email='autora@qa.br', sem_cadastro=True,
    )
    db.session.add(atribuicao)
    db.session.commit()
    token = _token_do_convite(fabrica, atribuicao.id, 'autora@qa.br')

    resposta = fabrica.cliente().post(f'/api/convites/{token}/aceitar', json={})

    assert resposta.status_code == 409
    assert resposta.get_json()['codigo'] == 'conflito_de_interesse'
    db.session.expire_all()
    atribuicao = Atribuicao.query.get(atribuicao.id)
    assert (atribuicao.situacao, atribuicao.avaliador_id) == ('convidado', None)
    # A autora não vê, não abre e não salva parecer do próprio trabalho.
    autora = fabrica.cliente(cenario['autora'])
    assert autora.get('/api/me/atribuicoes').get_json() == []
    assert autora.get(f'/api/atribuicoes/{atribuicao.id}').status_code == 404
    assert autora.put(f'/api/atribuicoes/{atribuicao.id}/parecer', json={'recomendacao': 'aceitar'}).status_code == 404
    assert autora.post(f'/api/atribuicoes/{atribuicao.id}/aceitar').status_code == 404


def test_aceitar_convite_criando_conta_com_email_de_coautor_e_recusado(fabrica, cenario):
    from app.models.user import Usuario
    db.session.add(Autoria(submissao_id=cenario['submissao_id'], nome='Nina', email='nina@qa.br', ordem=2))
    atribuicao = Atribuicao(
        rodada_id=cenario['rodada_id'], submissao_id=cenario['submissao_id'],
        evento_id=fabrica.rodada_atual(cenario['submissao_id']).evento_id,
        situacao='convidado', avaliador_nome='Nina', avaliador_email='nina@qa.br', sem_cadastro=True,
    )
    db.session.add(atribuicao)
    db.session.commit()
    token = _token_do_convite(fabrica, atribuicao.id, 'nina@qa.br')

    resposta = fabrica.cliente().post(f'/api/convites/{token}/aceitar', json={'nome': 'Nina', 'senha': 'senha-forte-1'})

    assert resposta.status_code == 409 and resposta.get_json()['codigo'] == 'conflito_de_interesse'
    assert Usuario.query.filter_by(email='nina@qa.br').first() is None  # nada é criado


def test_delegar_para_email_da_autora_e_recusado(fabrica, cenario):
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(cenario['chair'], cenario['rodada_id'], avaliador)

    resposta = fabrica.cliente(avaliador).post(f'/api/atribuicoes/{atribuicao_id}/delegar',
                                               json={'nome': 'Autora', 'email': ' Autora@QA.br'})

    assert resposta.status_code == 422 and resposta.get_json()['codigo'] == 'delegado_inelegivel'
    assert Atribuicao.query.count() == 1


def test_aceitar_convite_de_pessoa_sem_vinculo_continua_valendo(fabrica, cenario):
    resultado = _convidar_por_email(fabrica, cenario, 'externa@qa.br')
    token = _token_do_convite(fabrica, resultado['atribuicao']['id'], 'externa@qa.br')

    resposta = fabrica.cliente().post(f'/api/convites/{token}/aceitar', json={'nome': 'Externa', 'senha': 'senha-forte-1'})

    assert resposta.status_code == 200
    assert Atribuicao.query.get(resultado['atribuicao']['id']).situacao == 'aceito'


def test_coautor_com_conta_de_email_diferente_da_autoria_e_impedido(fabrica, cenario):
    # A autoria guarda o e-mail antigo; o convite usa o e-mail da conta.
    coautor = fabrica.usuario('Coautor', email='novo@qa.br')
    db.session.add(Autoria(submissao_id=cenario['submissao_id'], usuario_id=coautor.id,
                           nome=coautor.nome, email='antigo@qa.br', ordem=2))
    db.session.commit()

    assert _convidar_por_email(fabrica, cenario, 'Novo@qa.br')['codigo'] == 'coautor'


def test_email_da_autoria_com_maiusculas_e_espacos_e_impedido(fabrica, cenario):
    db.session.add(Autoria(submissao_id=cenario['submissao_id'], nome='Nina', email=' Nina@QA.br ', ordem=2))
    db.session.commit()

    assert _convidar_por_email(fabrica, cenario, 'nina@qa.br')['codigo'] == 'coautor'
