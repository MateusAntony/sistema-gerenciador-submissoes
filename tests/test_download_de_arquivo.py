"""A1 — GET /api/versoes/<id>/arquivo."""
import pytest

from app.extensions import db
from app.models.evento import Autoria, VersaoDeArquivo

CONTEUDO = b'%PDF-1.4 conteudo do trabalho'


@pytest.fixture
def cenario(fabrica):
    autora = fabrica.usuario('Autora')
    chair = fabrica.usuario('Chair')
    evento = fabrica.evento(chair=chair)
    chamada = fabrica.chamada(evento)
    submissao_id = fabrica.submissao_confirmada(autora, chamada, conteudo=CONTEUDO)
    versao = VersaoDeArquivo.query.filter_by(submissao_id=submissao_id).one()
    return {
        'autora': autora, 'chair': chair, 'evento': evento, 'chamada': chamada,
        'submissao_id': submissao_id, 'versao_id': versao.id,
    }


def _baixar(fabrica, usuario, versao_id):
    return fabrica.cliente(usuario).get(f'/api/versoes/{versao_id}/arquivo')


def test_autora_baixa_o_arquivo_com_nome_original_e_tipo(fabrica, cenario):
    resposta = _baixar(fabrica, cenario['autora'], cenario['versao_id'])

    assert resposta.status_code == 200
    assert resposta.data == CONTEUDO
    assert resposta.mimetype == 'application/pdf'
    assert resposta.headers['Content-Disposition'] == 'attachment; filename="trabalho.pdf"'


def test_nome_original_com_acento_vai_em_filename_estrela(fabrica, cenario):
    cliente = fabrica.cliente(cenario['autora'])
    submissao_id = cenario['submissao_id']
    # Versão nova só é aceita em rascunho ou reenvio; força a situação de reenvio.
    from app.models.evento import Submissao
    Submissao.query.get(submissao_id).situacao = 'aguardando_rebuttal'
    db.session.commit()
    versao = fabrica.enviar_versao(cliente, submissao_id, nome='versão final.pdf')

    resposta = cliente.get(f"/api/versoes/{versao['id']}/arquivo")

    assert resposta.status_code == 200
    disposicao = resposta.headers['Content-Disposition']
    assert disposicao.startswith('attachment; filename="')
    assert "filename*=UTF-8''vers%C3%A3o%20final.pdf" in disposicao


def test_sem_sessao_responde_401(fabrica, cenario):
    resposta = fabrica.cliente().get(f"/api/versoes/{cenario['versao_id']}/arquivo")
    assert resposta.status_code == 401


def test_versao_inexistente_responde_404(fabrica, cenario):
    resposta = _baixar(fabrica, cenario['autora'], 99999)
    assert resposta.status_code == 404


def test_usuario_sem_vinculo_recebe_403(fabrica, cenario):
    resposta = _baixar(fabrica, fabrica.usuario('Estranha'), cenario['versao_id'])
    assert resposta.status_code == 403


def test_coautor_com_conta_baixa(fabrica, cenario):
    coautor = fabrica.usuario('Coautor')
    db.session.add(Autoria(
        submissao_id=cenario['submissao_id'], usuario_id=coautor.id,
        nome=coautor.nome, email=coautor.email, ordem=2,
    ))
    db.session.commit()

    assert _baixar(fabrica, coautor, cenario['versao_id']).status_code == 200


def test_chair_do_evento_baixa(fabrica, cenario):
    assert _baixar(fabrica, cenario['chair'], cenario['versao_id']).status_code == 200


def test_chair_de_outro_evento_recebe_403(fabrica, cenario):
    outro_chair = fabrica.usuario('Outro chair')
    fabrica.evento(chair=outro_chair)
    assert _baixar(fabrica, outro_chair, cenario['versao_id']).status_code == 403


def test_administrador_baixa(fabrica, cenario):
    admin = fabrica.usuario('Admin', administrador=True)
    assert _baixar(fabrica, admin, cenario['versao_id']).status_code == 200


def test_avaliador_so_baixa_depois_de_aceitar(fabrica, cenario):
    avaliador = fabrica.usuario('Avaliador')
    rodada = fabrica.rodada_atual(cenario['submissao_id'])
    atribuicao_id = fabrica.convidar(cenario['chair'], rodada.id, avaliador)

    assert _baixar(fabrica, avaliador, cenario['versao_id']).status_code == 403

    fabrica.aceitar(avaliador, atribuicao_id)
    resposta = _baixar(fabrica, avaliador, cenario['versao_id'])
    assert resposta.status_code == 200
    assert resposta.data == CONTEUDO


def test_avaliador_aceito_em_outra_submissao_recebe_403(fabrica, cenario):
    avaliador = fabrica.usuario('Avaliador')
    outra_id = fabrica.submissao_confirmada(fabrica.usuario('Outra autora'), cenario['chamada'])
    atribuicao_id = fabrica.convidar(cenario['chair'], fabrica.rodada_atual(outra_id).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)

    assert _baixar(fabrica, avaliador, cenario['versao_id']).status_code == 403


def test_avaliador_aceito_nao_baixa_versao_posterior_a_vigente(fabrica, cenario):
    avaliador = fabrica.usuario('Avaliador')
    atribuicao_id = fabrica.convidar(cenario['chair'], fabrica.rodada_atual(cenario['submissao_id']).id, avaliador)
    fabrica.aceitar(avaliador, atribuicao_id)
    # Uma versão de número maior que não é a vigente (ex.: gravada fora de ordem).
    vigente = VersaoDeArquivo.query.get(cenario['versao_id'])
    posterior = VersaoDeArquivo(
        submissao_id=cenario['submissao_id'], numero=vigente.numero + 1, nome_original='rascunho.pdf',
        tamanho_bytes=1, enviado_por='Autora', vigente=False, caminho_arquivo=vigente.caminho_arquivo,
    )
    db.session.add(posterior)
    db.session.commit()

    assert _baixar(fabrica, avaliador, posterior.id).status_code == 403
    assert _baixar(fabrica, cenario['chair'], posterior.id).status_code == 200


def test_arquivo_ausente_no_disco_responde_404(fabrica, cenario):
    VersaoDeArquivo.query.get(cenario['versao_id']).caminho_arquivo = None
    db.session.commit()
    assert _baixar(fabrica, cenario['autora'], cenario['versao_id']).status_code == 404


def test_convidado_nao_baixa_mesmo_com_outro_avaliador_ja_aceito(fabrica, cenario):
    rodada_id = fabrica.rodada_atual(cenario['submissao_id']).id
    aceito = fabrica.usuario('Avaliador aceito')
    fabrica.aceitar(aceito, fabrica.convidar(cenario['chair'], rodada_id, aceito))
    convidado = fabrica.usuario('Avaliador convidado')
    fabrica.convidar(cenario['chair'], rodada_id, convidado)

    assert _baixar(fabrica, convidado, cenario['versao_id']).status_code == 403
