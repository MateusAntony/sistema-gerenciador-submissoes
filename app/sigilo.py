"""Sigilo nos modelos de avaliação cegos."""

MODELOS_CEGOS = {'simples_cega', 'duplo_cega'}


def nome_para_avaliador(versao, submissao, evento):
    """Nos modelos cegos o nome original do arquivo pode identificar a autoria
    (ex.: "Silva_Maria_UEFS.pdf"); o avaliador recebe '<codigo>-v<numero>.<ext>'.
    No modelo aberto, o nome real."""
    if evento is None or evento.modelo_de_avaliacao not in MODELOS_CEGOS:
        return versao.nome_original
    codigo = submissao.codigo or f'SUB-{submissao.id:04d}'
    _, ponto, extensao = versao.nome_original.rpartition('.')
    return f'{codigo}-v{versao.numero}' + (f'.{extensao}' if ponto else '')
