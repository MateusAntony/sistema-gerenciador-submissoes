import io

from app import create_app
from app.extensions import db
from app.models.evento import Autoria, Chamada, Evento, Submissao, Trilha, VersaoDeArquivo

# Inicializa o aplicativo Flask e o cliente de testes da API
app = create_app()

# 1. CRIAÇÃO DE DADOS DE SUPORTE NO BANCO
# Abre o contexto do Flask para inserir diretamente uma nova chamada de testes no banco de dados.
with app.app_context():
    evento = Evento.query.filter_by(identificador_pagina='cbsoft-2026').first()
    chamada = Chamada(
        evento_id=evento.id,
        titulo='Chamada completa de teste',
        data_abertura='2026-01-01',
        data_limite='2099-12-31',
        formatos_aceitos='["pdf"]',  # Restringe os formatos aceitos apenas para arquivos PDF
        tamanho_maximo_mb=10,
    )
    db.session.add(chamada)
    db.session.commit()
    chamada_id = chamada.id

# 2. AUTENTICAÇÃO
client = app.test_client()
# Faz login com o usuário administrador para obter a sessão ativa no cliente de testes.
assert client.post('/api/auth/login', json={'email': 'admin@local.test', 'senha': '123456'}).status_code == 200

# 3. CRIAÇÃO DA SUBMISSÃO EM RASCUNHO
# Cria uma nova submissão vazia vinculada à chamada recém-criada.
criado = client.post(f'/api/chamadas/{chamada_id}/submissoes', json={})
assert criado.status_code == 201, criado.get_json()
submissao_id = criado.get_json()['id']
print('CRIAR', criado.status_code, submissao_id)

# 4. GERENCIAMENTO DE AUTORIAS (COAUTORES)
# Testa a listagem inicial de autorias (o autor logado é adicionado automaticamente como responsável).
print('AUTORIAS_INICIAIS', client.get(f'/api/submissoes/{submissao_id}/autorias').status_code)

# Adiciona um coautor à submissão informando nome, e-mail e instituição.
autor = client.post(f'/api/submissoes/{submissao_id}/autorias', json={
    'nome': 'Coautor Teste', 'email': 'coautor@example.com', 'instituicao': 'Local'
})
assert autor.status_code == 201, autor.get_json()
print('ADICIONAR_AUTOR', autor.status_code)

# 5. PREENCHIMENTO DOS DADOS DO FORMULÁRIO (RESPOSTAS)
# Salva as respostas do formulário da submissão (título e resumo do trabalho).
patch = client.patch(f'/api/submissoes/{submissao_id}', json={
    'respostas': {'titulo': 'Trabalho completo', 'resumo': 'Resumo completo'}
})
assert patch.status_code == 200, patch.get_json()
print('SALVAR_RESPOSTAS', patch.status_code)

# 6. UPLOAD DE ARQUIVO (VERSÃO DO TRABALHO)
# Simula o envio de um arquivo binário (um PDF simulado usando `io.BytesIO`) através de `multipart/form-data`.
upload = client.post(
    f'/api/submissoes/{submissao_id}/versoes',
    data={
        'arquivo': (io.BytesIO(b'conteudo pdf de teste'), 'trabalho.pdf'),
        'nomeArquivo': 'trabalho.pdf',
        'tamanhoBytes': '21',
        'resumoDasAlteracoes': 'Primeira versão',
    },
    content_type='multipart/form-data',
)
assert upload.status_code == 201, upload.get_json()
print('UPLOAD', upload.status_code, upload.get_json()['numero'])

# Lista e valida se o arquivo foi anexado corretamente como a primeira versão vigente.
versoes = client.get(f'/api/submissoes/{submissao_id}/versoes')
assert versoes.status_code == 200 and len(versoes.get_json()) == 1
print('LISTAR_VERSOES', versoes.status_code)

# 7. CONFIRMAÇÃO DA SUBMISSÃO
# Submete oficialmente o trabalho (muda o status de 'rascunho' para 'submetida' e gera o código oficial ex: SUB-0001).
confirmacao = client.post(f'/api/submissoes/{submissao_id}/confirmar')
assert confirmacao.status_code == 200, confirmacao.get_json()
print('CONFIRMAR', confirmacao.status_code, confirmacao.get_json()['codigo'])

# Testa a idempotência: chamar o endpoint de confirmar novamente não quebra e retorna exatamente o mesmo código gerado.
segunda = client.post(f'/api/submissoes/{submissao_id}/confirmar')
assert segunda.status_code == 200 and segunda.get_json()['codigo'] == confirmacao.get_json()['codigo']
print('CONFIRMAR_IDEMPOTENTE', segunda.status_code)

# 8. LIMPEZA DO BANCO DE DADOS (TEARDOWN)
# Abre novamente o contexto para apagar do banco de dados todos os registros criados durante este teste,
# garantindo que o ambiente permaneça limpo para futuros testes.
with app.app_context():
    submissao = Submissao.query.get(int(submissao_id))
    VersaoDeArquivo.query.filter_by(submissao_id=submissao.id).delete()
    Autoria.query.filter_by(submissao_id=submissao.id).delete()
    db.session.delete(submissao)
    db.session.delete(Chamada.query.get(chamada_id))
    db.session.commit()
    print('LIMPO', submissao_id)