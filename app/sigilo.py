"""Sigilo nos modelos de avaliação cegos."""
from app.models.evento import Chamada, _json_list

MODELOS_CEGOS = {'simples_cega', 'duplo_cega'}

# Depois do último ponto pode estar um pedaço do nome ("Relatorio de
# Maria.Silva"), então só se mantém uma extensão reconhecida: a dos formatos
# da chamada ou uma destas, de documento.
EXTENSOES_CONHECIDAS = {
    'pdf', 'doc', 'docx', 'odt', 'rtf', 'txt', 'tex', 'md', 'html', 'epub',
    'ppt', 'pptx', 'odp', 'xls', 'xlsx', 'ods', 'csv',
    'png', 'jpg', 'jpeg', 'zip', 'gz', 'tar', '7z', 'rar',
}


def _extensao_reconhecida(extensao, submissao):
    chamada = Chamada.query.get(submissao.chamada_id)
    formatos = {str(f).lower().lstrip('.') for f in _json_list(chamada.formatos_aceitos)} if chamada else set()
    return extensao.lower() in formatos | EXTENSOES_CONHECIDAS


def nome_para_avaliador(versao, submissao, evento):
    """Nos modelos cegos o nome original do arquivo pode identificar a autoria
    (ex.: "Silva_Maria_UEFS.pdf"); o avaliador recebe '<codigo>-v<numero>.<ext>'.
    No modelo aberto, o nome real."""
    if evento is None or evento.modelo_de_avaliacao not in MODELOS_CEGOS:
        return versao.nome_original
    codigo = submissao.codigo or f'SUB-{submissao.id:04d}'
    _, ponto, extensao = versao.nome_original.rpartition('.')
    sufixo = f'.{extensao}' if ponto and _extensao_reconhecida(extensao, submissao) else ''
    return f'{codigo}-v{versao.numero}{sufixo}'
