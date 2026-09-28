"""A7 — GET /api/eventos lista só eventos publicados e expõe situacao;
/me/eventos e /me/participacoes trazem situacao (e papeis por evento)."""
from app.extensions import db
from app.models.evento import ParticipacaoEvento


def test_catalogo_publico_so_lista_publicados_com_situacao(fabrica):
    publicado = fabrica.evento(situacao='publicado', titulo='Publicado')
    fabrica.evento(situacao='aprovado', titulo='Aprovado')
    fabrica.evento(situacao='encerrado', titulo='Encerrado')

    resposta = fabrica.cliente().get('/api/eventos')

    assert resposta.status_code == 200
    assert [(e['id'], e['titulo'], e['situacao']) for e in resposta.get_json()] == [
        (str(publicado.id), 'Publicado', 'publicado'),
    ]


def test_chair_continua_vendo_evento_aprovado_em_me_eventos(fabrica):
    chair = fabrica.usuario('Chair')
    aprovado = fabrica.evento(chair=chair, situacao='aprovado')

    [evento] = fabrica.cliente(chair).get('/api/me/eventos').get_json()

    assert evento['id'] == str(aprovado.id)
    assert evento['situacao'] == 'aprovado'


def test_participacoes_trazem_situacao_e_todos_os_papeis_do_evento(fabrica):
    pessoa = fabrica.usuario('Pessoa')
    evento = fabrica.evento(chair=pessoa, situacao='aprovado')
    db.session.add(ParticipacaoEvento(evento_id=evento.id, usuario_id=pessoa.id, papel='avaliador'))
    db.session.commit()
    outro = fabrica.evento(situacao='publicado')
    db.session.add(ParticipacaoEvento(evento_id=outro.id, usuario_id=pessoa.id, papel='avaliador'))
    db.session.commit()

    itens = fabrica.cliente(pessoa).get('/api/me/participacoes').get_json()

    por_evento = {item['eventoId']: item for item in itens}
    assert len(itens) == 2
    assert sorted(por_evento[evento.id]['papeis']) == ['avaliador', 'chair']
    assert por_evento[evento.id]['situacao'] == 'aprovado'
    assert por_evento[evento.id]['eventoTitulo'] == evento.titulo
    assert por_evento[evento.id]['identificadorPagina'] == evento.identificador_pagina
    assert por_evento[outro.id]['papeis'] == ['avaliador']
    assert por_evento[outro.id]['situacao'] == 'publicado'
