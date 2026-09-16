import uuid

from app import create_app
from app.extensions import db
from app.models.evento import Chamada, Evento

# Inicializa a aplicação Flask e o cliente de testes da API
app = create_app()
client = app.test_client()

# 1. CRIAÇÃO DE DADOS DE SUPORTE NO BANCO (Via App Context)
# Como este script precisa de um evento e uma chamada pré-existentes para testar as submissões,
# ele abre o contexto do Flask para interagir diretamente com o banco de dados via SQLAlchemy.
with app.app_context():
    # Busca um evento existente no banco pelo seu identificador de página ('cbsoft-2026').
    evento = Evento.query.filter_by(identificador_pagina='cbsoft-2026').first()
    
    # Procura se já existe uma chamada com o título 'Chamada de teste da API'.
    chamada = Chamada.query.filter_by(titulo='Chamada de teste da API').first()
    
    # Se a chamada ainda não existir no banco, cria uma nova e salva preventivamente.
    if chamada is None:
        chamada = Chamada(
            evento_id=evento.id,
            titulo='Chamada de teste da API',
            data_abertura='2026-01-01',
            data_limite='2099-12-31',  # Data futura bem longa para garantir que não expire durante os testes
            formatos_aceitos='[]',
            tamanho_maximo_mb=10,
        )
        db.session.add(chamada)
        db.session.commit()
    
    # Armazena o ID da chamada para usar nas requisições HTTP logo abaixo.
    chamada_id = chamada.id

# 2. AUTENTICAÇÃO
# Realiza o login com o usuário administrador para obter a sessão ativa no test_client.
login = client.post('/api/auth/login', json={'email': 'admin@local.test', 'senha': '123456'})
# Garante através de um assert que o login deu certo (status 200), caso contrário o teste quebra aqui.
assert login.status_code == 200, login.get_json()

# 3. CRIAÇÃO DE UMA RASCUNHO DE SUBMISSÃO
# Faz uma requisição POST para a rota que inicia uma nova submissão em uma chamada específica.
criado = client.post(f'/api/chamadas/{chamada_id}/submissoes', json={})
assert criado.status_code == 201, criado.get_json()
submissao = criado.get_json()
submissao_id = submissao['id']
print('CRIAR', criado.status_code, submissao_id)

# 4. EDIÇÃO / SALVAMENTO DA SUBMISSÃO
# Utiliza o método PATCH para atualizar os dados de rascunho da submissão (título, resumo e ID externo).
salvo = client.patch(f'/api/submissoes/{submissao_id}', json={
    'respostas': {'titulo': 'Trabalho de teste', 'resumo': 'Resumo inicial'},
    'identificadorExterno': 'EXT-001',
})
assert salvo.status_code == 200, salvo.get_json()
print('SALVAR', salvo.status_code, salvo.get_json()['respostas'])

# 5. CONSULTA INDIVIDUAL DA SUBMISSÃO
# Faz um GET para buscar os dados detalhados daquela submissão específica pelo ID.
obtido = client.get(f'/api/submissoes/{submissao_id}')
assert obtido.status_code == 200, obtido.get_json()
print('OBTER', obtido.status_code, obtido.get_json()['identificadorExterno'])

# 6. LISTAGEM E FILTRAGEM DE SUBMISSÕES
# Testa a listagem de submissões do próprio usuário logado utilizando um filtro de busca por termo (?q=trabalho).
lista = client.get('/api/me/submissoes?q=trabalho')
assert lista.status_code == 200, lista.get_json()
assert len(lista.get_json()) >= 1  # Garante que encontrou pelo menos um resultado correspondente
print('LISTAR', lista.status_code, len(lista.get_json()))

# 7. EXCLUSÃO DO RASCUNHO
# Como a submissão ainda está em formato de rascunho, testa a rota de exclusão (DELETE).
apagado = client.delete(f'/api/submissoes/{submissao_id}')
assert apagado.status_code == 204, apagado.status_code  # Status 204 indica sucesso na exclusão sem conteúdo de retorno
print('EXCLUIR', apagado.status_code)