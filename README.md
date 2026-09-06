# Back-End do Sistema Gerenciador de Submissoes (SGS)

## Como Rodar:
1. Na raiz do projeto baixado, execute no terminal:
```
docker-compose down
docker-compose up --build
```

## Rotas:
### 1.1. URL: "/api/auth/register"
<b>Tipo:</b> POST
<br><b>Função associada:</b> app.controllers.auth_controller.register
<br><b>Descrição:</b> usada para registrar um novo usuário
<br><b>Entradas:</b>
```
{
    "nome": "Paulo",
    "email": "paulo@gmail.com",
    "senha": "Abc@123",
    "instituicao": "UEFS",
    "pais": "Brasil"
}
```
<b>Saída de Sucesso (HTTP 201):</b>
```
{
    "message": "Usuário criado com sucesso",
    "user": {
        "administrador": false,
        "ativo": true,
        "email": "paulo@gmail.com",
        "id": 1,
        "instituicao": "UEFS",
        "nome": "Paulo"
    }
}
```
<b>Saída de Falha (HTTP 400):</b>
```
{
    "error": "Descrição de Erro..."
}
```

### 1.2. URL: "/api/auth/login"
<b>Tipo:</b> POST
<br><b>Função associada:</b> app.controllers.auth_controller.login
<br><b>Descrição:</b> usada para autenticar um usuário
<br><b>Entradas:</b>
```
{
    "email": "paulo@gmail.com",
    "senha": "Abc@123"
}
```
<b>Saída de Sucesso (HTTP 200):</b>
```
{
    "message": "Login realizado com sucesso",
    "user": {
        "administrador": false,
        "ativo": true,
        "email": "paulo@gmail.com",
        "id": 1,
        "instituicao": "UEFS",
        "nome": "Paulo"
    }
}
```
<b>Saída de Falha (HTTP 401):</b>
```
{
    "error": "Credenciais inválidas"
}
```

### 1.3. URL: "/api/auth/me"
<b>Tipo:</b> GET
<br><b>Função associada:</b> app.controllers.auth_controller.me
<br><b>Descrição:</b> usada para coletar informações do usuário logado, via Cookies de Sessão
<br><b>Entradas:</b> nenhuma
<b>Saída de Sucesso (HTTP 200):</b>
```
{
    "user": {
        "administrador": false,
        "ativo": true,
        "email": "paulo@gmail.com",
        "id": 1,
        "instituicao": "UEFS",
        "nome": "Paulo"
    }
}
```
<b>Saída de Falha (HTTP 401):</b>
```
{
    "error": "Não autenticado"
}
```

### 1.4. URL: "/api/auth/logout"
<b>Tipo:</b> POST
<br><b>Função associada:</b> app.controllers.auth_controller.logout
<br><b>Descrição:</b> usada para encerrar a sessão do usuário
<br><b>Entradas:</b> nenhuma
<b>Saída de Sucesso (HTTP 200):</b>
```
{
    "message": "Logout realizado com sucesso"
}
```
