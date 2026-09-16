import uuid

from app import create_app

# Inicializa a aplicação Flask usando a fábrica de aplicativos (create_app)
app = create_app()

# Cria um cliente de testes (test_client) para simular requisições HTTP 
# diretamente no Flask sem precisar subir um servidor web real rodando.
client = app.test_client()

# 1. AUTENTICAÇÃO
# Realiza o login com um usuário administrador de testes para obter permissões de gerenciamento.
login = client.post('/api/auth/login', json={'email': 'admin@local.test', 'senha': '123456'})
print('LOGIN', login.status_code, login.get_json()['usuario']['email'])

# 2. CRIAÇÃO DE SOLICITAÇÃO DE EVENTO
# Gera um identificador único aleatório (ex: 'evt-a1b2c3d4') para evitar conflito de URL única.
identificador = f'evt-{uuid.uuid4().hex[:8]}'

# Envia os dados para a rota de criação de solicitação de evento (o evento nasce como 'pendente').
solicitacao = client.post('/api/solicitacoes-evento', json={
    'titulo': 'Evento Teste',
    'identificadorPagina': identificador,
    'dataInicio': '2026-01-10',
    'dataTermino': '2026-01-12',
    'tipo': 'conferencia',
    'pais': 'Brasil',
    'fuso': '-03:00',
    'justificativa': 'teste'
})
print('SOLICITACAO', solicitacao.status_code, solicitacao.get_json())

# Captura o payload (resposta JSON) da solicitação criada para usar nas próximas etapas.
payload = solicitacao.get_json()

# 3. VALIDAÇÃO DE LISTAGENS
# Testa a rota que lista as solicitações feitas pelo próprio usuário logado.
print('MINHAS', client.get('/api/me/solicitacoes-evento').status_code)
# Testa a rota administrativa que lista a fila de solicitações pendentes de aprovação.
print('FILA', client.get('/api/admin/solicitacoes-evento').status_code)

# 4. APROVAÇÃO DA SOLICITAÇÃO PELO ADMINISTRADOR
# Simula o admin aprovando a solicitação pelo ID. É aqui que o evento oficial é gerado na tabela 'eventos'.
aprovacao = client.post(f"/api/admin/solicitacoes-evento/{payload['id']}/aprovar")
print('APROVAR', aprovacao.status_code, aprovacao.get_json())

# Extrai o ID do evento recém-criado a partir da resposta da aprovação.
evento_id = aprovacao.get_json()['evento']['id']

# 5. GERENCIAMENTO E CONFIGURAÇÃO DO EVENTO APROVADO
# Consulta os detalhes do evento oficial criado.
print('GET_EVENTO', client.get(f'/api/eventos/{evento_id}').status_code)
# Verifica o checklist de requisitos necessários para poder publicar o evento.
print('CHECKLIST', client.get(f'/api/eventos/{evento_id}/checklist-publicacao').status_code)

# Adiciona uma Trilha temática ao evento.
trilha = client.post(f'/api/eventos/{evento_id}/trilhas', json={'nome': 'Trilha A'})
print('TRILHA', trilha.status_code, trilha.get_json())

# Cria uma Chamada de Trabalhos (Call for Papers) associada ao evento.
chamada = client.post(f'/api/eventos/{evento_id}/chamadas', json={
    'titulo': 'Chamada A',
    'dataAbertura': '2026-01-01',
    'dataLimite': '2026-02-01',
    'formatosAceitos': ['pdf'],
    'tamanhoMaximoMb': 10,
})
print('CHAMADA', chamada.status_code, chamada.get_json())

# Adiciona um Critério de Avaliação para as submissões do evento.
criterio = client.post(f'/api/eventos/{evento_id}/criterios', json={
    'titulo': 'Critério 1',
    'notaMinima': 0,
    'notaMaxima': 10,
    'peso': 1,
})
print('CRITERIO', criterio.status_code, criterio.get_json())

# Reavalia o checklist para confirmar que todos os itens obrigatórios foram preenchidos.
item_checklist = client.get(f'/api/eventos/{evento_id}/checklist-publicacao')
print('CHECKLIST_FINAL', item_checklist.status_code, item_checklist.get_json())

# 6. PUBLICAÇÃO DO EVENTO
# Envia a requisição para publicar o evento (mudando o status para 'publicado'), informando a versão atual.
publicar = client.post(f'/api/eventos/{evento_id}/publicar', json={'versao': 2})
print('PUBLICAR', publicar.status_code, publicar.get_json())