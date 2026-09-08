# API REST — plataforma-base e eventos-e-chamadas · Tasks

## Execution Protocol (MANDATORY — do not skip)

Implemente estas tarefas com a skill `tlc-spec-driven`: **ative-a pelo nome e siga o fluxo de
Execute e as Critical Rules dela.** Não procure os arquivos da skill por caminho de sistema de
arquivos. A skill é a fonte de verdade do fluxo completo (ciclo por tarefa, delegação a
sub-agentes, revisão de adequação, Verificador, sensor de discriminação).

**Se a skill não puder ser ativada, PARE e avise o usuário — não prossiga sem ela.**

---

**Design**: `.specs/features/api-base-e-eventos/design.md`
**Spec**: `.specs/features/api-base-e-eventos/spec.md`
**Status**: In Progress — **Fases 0–6 concluídas e verificadas (T1–T42, mais T14b e T27b).**
Faltam as Fases 7, 8 e 9 (T43–T54). Ver `.specs/STATE.md` § Handoff.

---

## Test Coverage Matrix

> Gerada do código, das diretrizes do projeto e da spec — confirmar antes de Execute.
> **Diretrizes encontradas: nenhuma** (não há `CLAUDE.md`, `CONTRIBUTING.md`, config de teste nem
> workflow de CI neste repositório, e nenhum teste existente). Aplicados os padrões fortes.
> Referência de estilo tomada do repositório do front (`app/src/**/*.test.ts`), que testa
> comportamento observável derivado das ACs, nunca a implementação.

| Camada | Tipo de teste | Expectativa de cobertura | Localização | Comando |
| ------ | ------------- | ------------------------ | ----------- | ------- |
| `app/core/` puro (erros, correlação, permissões, schemas) | unit | Todos os ramos; 1:1 com as ACs; todo caso de borda listado | `tests/unidade/core/test_*.py` | `pytest -q tests/unidade` |
| Service / regra de negócio | integration | Todos os ramos; 1:1 com as ACs da spec; todo caso de borda listado. Postgres real (AD-012) | `tests/integracao/<modulo>/test_*_service.py` | `pytest -q` |
| Repository / acesso a dados | integration | Caminhos de consulta principais + erros de integridade | `tests/integracao/<modulo>/test_*_repository.py` | `pytest -q` |
| Controller / rota HTTP | e2e | **Toda rota da tarefa**: caminho feliz + todo caso de borda + todo caminho de erro (401/403/404/409/422). Exercitada pelo cliente HTTP do Flask, nunca chamando o service direto (API-22 AC3) | `tests/e2e/test_<recurso>.py` | `pytest -q` |
| Models SQLAlchemy / migrations / schemas Pydantic | none | — (gate de build: `flask db upgrade` aplica e `pytest` importa) | — | gate de build |
| Front (repo `projeto-extensao`) | unit + integration | Padrão vigente do front: Vitest + RTL + MSW, derivado das ACs. **Nenhum teste existente enfraquecido, pulado ou removido** (API-23 AC6) | `app/src/**/*.test.ts(x)` | `npm run gate` |

## Gate Check Commands

> Geradas do código — confirmar antes de Execute. Os comandos rodam dentro do contêiner `web`
> (`docker compose exec web <cmd>`) ou num ambiente local com `DATABASE_URL` apontando para o
> Postgres do compose.

| Nível | Quando usar | Comando |
| ----- | ----------- | ------- |
| Quick | Após tarefa que só toca código puro de `app/core/` | `pytest -q tests/unidade` |
| Full | Após qualquer tarefa que toque banco, service ou rota | `pytest -q` |
| Build | Ao fim de cada fase e em tarefas de config/migration | `pytest -q && ruff check app tests && flask db upgrade` |
| Front | Tarefas da Fase 9, no repositório do front | `npm run gate` (em `C:\Users\lucas\projeto-extensao\app`) |

**O gate é o código de saída, não a contagem de testes verdes** — lição registrada em
`.specs/LESSONS.md` do front, incorporada aqui antes de o primeiro defeito acontecer.

---

## Execution Plan

Fases são ordenadas e rodam sequencialmente; tarefas dentro de uma fase rodam em ordem.

### Fase 0: Rede de segurança e fundação (8 tarefas)

Nada do auth é tocado antes de existir suíte de testes (risco R7 do design).

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
```

### Fase 1: Contas e e-mail (6 tarefas)

```
T9 → T10 → T11 → T12 → T13 → T14
```

### Fase 2: Sessão (6 tarefas)

```
T15 → T16 → T17 → T18 → T19 → T20
```

### Fase 3: RBAC e participações (4 tarefas)

```
T21 → T22 → T23 → T24
```

### Fase 4: Convites (3 tarefas)

```
T25 → T26 → T27
```

### Fase 5: Solicitação e decisão de evento (7 tarefas)

```
T28 → T29 → T30 → T31 → T32 → T33 → T34
```

### Fase 6: Configuração do evento (8 tarefas)

```
T35 → T36 → T37 → T38 → T39 → T40 → T41 → T42
```

### Fase 7: Publicação e vitrine (4 tarefas)

```
T43 → T44 → T45 → T46
```

### Fase 8: Adequação do front (5 tarefas)

Outro repositório, outro gate. Isolada de propósito.

```
T47 → T48 → T49 → T50 → T51
```

### Fase 9: Fecho (3 tarefas)

```
T52 → T53 → T54
```

---

## Task Breakdown

### T1: Suíte pytest com Postgres real

**What**: Criar a infraestrutura de teste — `conftest.py` com fixtures de aplicação, banco
`sgs_test` criado e migrado uma vez por sessão, e transação com rollback por teste.
**Where**: `tests/conftest.py`, `pytest.ini`, `requirements-dev.txt`
**Depends on**: None
**Reuses**: `app.create_app` (fábrica já existente em `app/__init__.py:6`)
**Requirement**: API-22 AC1, AC2, AC4

**Done when**:

- [x] Fixture de sessão cria `sgs_test` se não existir e aplica todas as migrations
- [x] Fixture de função abre transação e faz rollback ao fim — dois testes que escrevem o mesmo
      e-mail passam em qualquer ordem
- [x] `pytest -q` sai com código 0 com um teste de fumaça que consulta o banco
- [x] Um teste que falha faz o comando sair com código **diferente de zero** (verificado)

**Tests**: integration · **Gate**: full
**Commit**: `test: suite pytest contra postgres real`

---

### T2: Flask-Migrate e migration inicial

**What**: Adicionar Flask-Migrate e gerar a migration inicial com **todas** as tabelas de BASE+EVT
em UUID, mais as quatro tabelas mínimas de AD-018; remover `init-scripts/01-schema.sql`.
**Where**: `migrations/`, `app/modules/*/models.py`, `app/extensions.py`, `requirements.txt`
**Depends on**: T1
**Reuses**: `init-scripts/01-schema.sql` (colunas de `usuarios` e `participacoes_evento`), seção
"Data Models" do design
**Requirement**: API-02 AC1..AC4, AD-004, AD-005, AD-018

**Done when**:

- [x] Todas as tabelas da seção Data Models do design criadas, com PK `UUID DEFAULT uuid_generate_v4()`
- [x] `participacoes_evento.evento_id` tem chave estrangeira para `eventos` (risco R6)
- [x] Os `CHECK` declarados no design existem no banco (rebuttal, datas, peso, nota, avaliadores)
- [x] `init-scripts/01-schema.sql` removido e o volume do compose não o referencia mais
- [x] `flask db upgrade` duas vezes seguidas não altera nada (idempotente, AC3)
- [x] Teste que verifica, via catálogo do Postgres, que cada tabela esperada existe com PK UUID

**Tests**: integration · **Gate**: build
**Commit**: `feat(db): migrations alembic e schema inicial em uuid`

---

### T3: Configuração por ambiente

**What**: Reescrever `Config` para derivar de `APP_ENV`, falhar no boot nomeando a variável
ausente, e parar de fixar `SESSION_COOKIE_SECURE` no código.
**Where**: `app/config.py`, `.env.example`
**Depends on**: T1
**Reuses**: `get_required_env` (`app/config.py:3`)
**Requirement**: API-21 AC4, AC5, risco R4

**Done when**:

- [x] `APP_ENV` ∈ `development | test | production` seleciona o conjunto de configuração
- [x] Cookie de renovação com `Secure` ligado quando `APP_ENV=production`; boot falha se produção
      não tiver HTTPS declarado
- [x] Faltar variável obrigatória levanta erro **nomeando a variável** — teste por variável
- [x] `.env.example` lista todas as variáveis exigidas, sem valor secreto real
- [x] `MAX_CONTENT_LENGTH` configurado (risco R10)

**Tests**: unit · **Gate**: quick
**Commit**: `feat(config): configuracao por ambiente com falha explicita no boot`

---

### T4: Contêiner sem debugger em produção

**What**: Trocar o `CMD` do Dockerfile por servidor WSGI de produção, condicionar `debug` a
`APP_ENV=development` e aplicar migrations no boot do contêiner.
**Where**: `Dockerfile`, `run.py`, `docker-compose.yml`, `entrypoint.sh`
**Depends on**: T2, T3
**Reuses**: `docker-compose.yml` e `Dockerfile` existentes
**Requirement**: API-21 AC1, risco R5

**Done when**:

- [x] `CMD` usa servidor WSGI de produção; `debug=True` só ocorre sob `APP_ENV=development`
- [x] `entrypoint.sh` aguarda o Postgres e roda `flask db upgrade` antes de servir
- [x] `docker compose up --build` sobe a API respondendo em `http://localhost:5000`
- [x] Teste que afirma que a aplicação criada com `APP_ENV=production` tem `app.debug is False`

**Tests**: unit · **Gate**: build
**Commit**: `fix(docker): remove debugger do comando de producao e aplica migrations no boot`

---

### T5: Envelope de erro e tratadores centrais

**What**: Criar a hierarquia `ErroDaApi` e registrar os tratadores que traduzem tudo o que sobe
para `{ codigo, mensagem, campos?, correlacao }`.
**Where**: `app/core/erros.py`
**Depends on**: T1
**Reuses**: nada — substitui os `jsonify({"error": ...})` de `auth_controller.py`
**Requirement**: API-01 AC1, AC2, AC5, AC6

**Done when**:

- [x] `ErroDaApi` e as subclasses do design existem com `codigo`, `status`, `mensagem`, `extras`
- [x] `ValidationError` do Pydantic vira 422 `dados_invalidos` com `campos` em **camelCase**
- [x] `HTTPException` do Werkzeug vira envelope — 404 e 405 nunca devolvem HTML
- [x] Corpo não-JSON vira 400 `corpo_invalido`; corpo acima do limite vira 413
- [x] `Exception` não prevista vira 500 `erro_interno` **sem stack no corpo**, com a stack no log
- [x] Testes cobrem cada um dos ramos acima

**Tests**: unit · **Gate**: quick
**Commit**: `feat(core): envelope de erro unico e tratadores centrais`

---

### T6: Identificador de correlação

**What**: Gerar um identificador por requisição, expô-lo no header `X-Correlacao`, no log e no
corpo de todo erro.
**Where**: `app/core/correlacao.py`
**Depends on**: T5
**Reuses**: `flask.g`
**Requirement**: API-01 AC3

**Done when**:

- [x] `before_request` gera UUID; `after_request` o devolve em `X-Correlacao`
- [x] O `correlacao` do corpo de erro é **o mesmo valor** do header, na mesma resposta
- [x] Duas requisições consecutivas recebem correlações diferentes
- [x] O log da exceção de 500 carrega a mesma correlação da resposta

**Tests**: unit · **Gate**: quick
**Commit**: `feat(core): identificador de correlacao por requisicao`

---

### T7: Base Pydantic com alias camelCase

**What**: Criar `SchemaDaApi` e `SchemaDeEntrada` com alias camelCase automático, `UUID` como
string e `datetime` em ISO-8601 UTC.
**Where**: `app/core/schemas.py`
**Depends on**: T1
**Reuses**: Pydantic v2 (`to_camel` de `pydantic.alias_generators`)
**Requirement**: API-01 AC4, AD-006

**Done when**:

- [x] Campo `identificador_pagina` serializa como `identificadorPagina` e aceita ambos na entrada
- [x] `UUID` sai como string; `datetime` sai em ISO-8601 UTC terminando em `Z`
- [x] `SchemaDeEntrada` recusa campo desconhecido (`extra='forbid'`) com 422
- [x] Campo opcional ausente é **omitido** da saída, não emitido como `null`

**Tests**: unit · **Gate**: quick
**Commit**: `feat(core): base pydantic com alias camelcase`

---

### T8: Unidade de trabalho — um commit por requisição

**What**: Criar o gerenciador de transação e remover todo `db.session.commit()` dos repositórios
existentes.
**Where**: `app/core/unidade_de_trabalho.py`, `app/repositories/user_repository.py`
**Depends on**: T1, T5
**Reuses**: `db.session` de `app/extensions.py`
**Requirement**: AD-019, risco R1, pré-requisito de API-13 AC4

**Done when**:

- [x] `transacao()` faz commit único no sucesso e rollback em qualquer exceção
- [x] Nenhum repositório chama `commit()` — verificado por teste que varre `app/` procurando a
      chamada fora de `unidade_de_trabalho.py`
- [x] Teste: duas escritas onde a segunda falha deixam **zero** linhas gravadas

**Tests**: integration · **Gate**: full
**Commit**: `refactor(core): commit unico por requisicao`

---

### T9: Modelo de usuário em UUID, sem `to_dict`

**What**: Mover `Usuario` para `app/modules/contas/models.py` com PK UUID, remover `to_dict()` e
reescrever o repositório sem commit e sem API do SQLAlchemy 1.x.
**Where**: `app/modules/contas/models.py`, `app/modules/contas/repository.py`
**Depends on**: T2, T8
**Reuses**: `app/models/user.py`, `app/repositories/user_repository.py`
**Requirement**: AD-016, riscos R1, R3

**Done when**:

- [x] `Usuario` vive no módulo `contas` com PK UUID e as colunas do schema preservadas
- [x] `to_dict()` removido — a serialização passa a ser dos schemas Pydantic
- [x] `Usuario.query.get()` substituído por `db.session.get(Usuario, id)` (risco R3)
- [x] `app/models/`, `app/repositories/`, `app/services/`, `app/controllers/` antigos removidos ao
      fim da migração de conteúdo
- [x] Testes de repositório: busca por e-mail, busca por id inexistente devolve `None`, criação

**Tests**: integration · **Gate**: full
**Commit**: `refactor(contas): usuario em uuid no modulo de dominio`

---

### T10: Serviço de e-mail com backend trocável

**What**: Criar o módulo de e-mail: modelo `emails_enviados`, `EmailService` e os backends de log
e SMTP.
**Where**: `app/modules/emails/`
**Depends on**: T2, T3
**Reuses**: `get_required_env` de `app/config.py`
**Requirement**: API-10 AC1..AC4, AD-010

**Done when**:

- [x] `EMAIL_BACKEND=log` grava em `emails_enviados` e no log, sem tentativa de rede
- [x] Falha do backend **não** propaga: registro fica com `situacao='falha'` e o chamador segue
- [x] Corpo do e-mail contém a URL completa montada a partir da variável de origem do front
- [x] `EMAIL_BACKEND=smtp` sem configuração completa **falha no boot** nomeando a variável — nunca
      cai silenciosamente no backend de log
- [x] Testes cobrem os quatro ramos acima

**Tests**: integration · **Gate**: full
**Commit**: `feat(emails): servico de email com backend trocavel`

---

### T11: `POST /api/usuarios` — autocadastro

**What**: Implementar o cadastro de conta com schema, service, repositório e rota.
**Where**: `app/modules/contas/{controller,service,schemas}.py`
**Depends on**: T5, T7, T9, T10
**Reuses**: `AuthService.register_user` (`app/services/auth_service.py:6`) e o `bcrypt` existente
**Requirement**: API-05 AC1..AC6

**Done when**:

- [x] 201 com **exatamente** `{ id, email }` — nunca o usuário completo (AC6)
- [x] Conta nasce `emailConfirmado: false`, `ativo: true`, senha só como hash bcrypt
- [x] 409 `email_existente` para e-mail repetido, **inclusive** quando a colisão vem da constraint
      única em corrida (Edge Case da spec: `IntegrityError` → 409, nunca 500)
- [x] 422 com `campos.instituicao` quando ausente; `campos.senha` quando menor que 8 caracteres
- [x] E-mail de confirmação disparado
- [x] Testes e2e: feliz, e-mail duplicado, instituição vazia, senha curta

**Tests**: e2e · **Gate**: full
**Commit**: `feat(contas): endpoint de autocadastro`

---

### T12: Token de confirmação de e-mail

**What**: Modelo `tokens_confirmacao_email`, emissão com hash e o e-mail correspondente.
**Where**: `app/modules/contas/{models,service}.py`
**Depends on**: T11
**Reuses**: `EmailService` (T10)
**Requirement**: API-06 AC7, AD-017

**Done when**:

- [x] O banco guarda **apenas** o SHA-256 do token; o valor cru só aparece no corpo do e-mail
- [x] Token expira em 24 horas
- [x] Emitir novo token para o mesmo usuário não invalida silenciosamente o anterior sem registro
- [x] Teste que afirma que o token cru **não** aparece em nenhuma coluna da tabela

**Tests**: integration · **Gate**: full
**Commit**: `feat(contas): token de confirmacao de email`

---

### T13: `POST /api/auth/confirmar-email`

**What**: Implementar a confirmação de e-mail com os quatro desfechos do contrato.
**Where**: `app/modules/contas/{controller,service}.py`
**Depends on**: T12
**Reuses**: schemas de `contas`
**Requirement**: API-06 AC1..AC4

**Done when**:

- [x] 200 `{ email }` marca a conta como confirmada e o token como usado
- [x] 404 `token_invalido` · 410 `token_expirado` · 409 `token_ja_usado`
- [x] Confirmar duas vezes o mesmo token devolve 409 na segunda
- [x] Testes e2e para os quatro desfechos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(contas): endpoint de confirmacao de email`

---

### T14: `POST /api/auth/reenviar-confirmacao`

**What**: Implementar o reenvio com janela mínima de 60 segundos e resposta indistinguível.
**Where**: `app/modules/contas/{controller,service}.py`
**Depends on**: T13
**Reuses**: `EmailService`, índice `(usuario_id, criado_em DESC)` de T2
**Requirement**: API-06 AC5, AC6

**Done when**:

- [x] 200 `{ esperarSegundos: 60 }` **igual** para e-mail existente e inexistente (AC5)
- [x] Segundo pedido dentro da janela devolve o tempo restante e **não** envia novo e-mail —
      verificado contando linhas em `emails_enviados`
- [x] Passada a janela, novo e-mail é enviado
- [x] Testes e2e para os três casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(contas): reenvio de confirmacao com janela minima`

---

### T14b: Fechar o oráculo de enumeração no reenvio

**What**: Registrar a janela de reenvio por e-mail — exista ou não conta — para que a contagem
regressiva seja idêntica nos dois casos.
**Where**: `app/modules/contas/{models,service}.py`, `migrations/versions/`
**Depends on**: T14
**Reuses**: `JANELA_DE_REENVIO_EM_SEGUNDOS` e `ContaService.reenviar_confirmacao` (T14)
**Requirement**: API-06 AC5, AC7, AC8 (redigidas após o achado)

**Origem**: descoberto na verificação do lote 2. Com 3 s entre dois pedidos, a API respondia
`esperarSegundos: 57` para e-mail cadastrado e `60` para não cadastrado — qualquer um descobria
quem tem conta com duas chamadas. As ACs originais se anulavam; a spec foi emendada.

**Done when**:

- [ ] Tabela `pedidos_de_reenvio` (`email_hash` SHA-256, `criado_em`, índice
      `(email_hash, criado_em DESC)`) criada por migration
- [ ] A janela é calculada **antes** de registrar, e o registro só acontece quando a janela está
      aberta — senão o segundo pedido reiniciaria a contagem
- [ ] O e-mail cru **não** aparece em nenhuma coluna — teste que varre a tabela
- [ ] **Teste de indistinguibilidade**: duas sequências de dois pedidos com o mesmo intervalo, uma
      para e-mail cadastrado e outra para não cadastrado, produzem respostas iguais par a par
- [ ] E-mail novo continua saindo só quando há conta e a janela está aberta — provado por contagem
      de linhas em `emails_enviados`
- [ ] Registros com janela vencida são removidos

**Tests**: e2e · **Gate**: full
**Commit**: `fix(contas): fecha oraculo de enumeracao de contas no reenvio`

---

### T15: Sessões — emissão, rotação e família

**What**: Modelo `sessoes` e o service puro de emissão, rotação e invalidação de família.
**Where**: `app/modules/sessao/{models,service,repository}.py`
**Depends on**: T2, T8
**Reuses**: `flask-jwt-extended`
**Requirement**: API-04 AC1, AC3, AD-017

**Done when**:

- [x] Emitir cria linha com `familia`, `token_hash` (SHA-256) e `expira_em` de 14 dias
- [x] Rotacionar marca a linha anterior como `rotacionado_em` e cria a próxima na mesma família
- [x] Apresentar token já rotacionado invalida **toda a família** — teste com 3 rotações
- [x] Token de acesso expira em 15 minutos
- [x] O valor cru do token de renovação não aparece em nenhuma coluna

**Tests**: integration · **Gate**: full
**Commit**: `feat(sessao): emissao e rotacao de token de renovacao`

---

### T16: `POST /api/auth/login`

**What**: Implementar o login com os quatro desfechos e o cookie de renovação.
**Where**: `app/modules/sessao/{controller,service,schemas}.py`
**Depends on**: T15, T11
**Reuses**: `AuthService.authenticate_user` (`app/services/auth_service.py:24`)
**Requirement**: API-03 AC1..AC6

**Done when**:

- [x] 200 `{ tokenDeAcesso, usuario }` com os seis campos do contrato e **sem** senha ou hash
- [x] 401 `credenciais_invalidas` com a **mesma** mensagem para e-mail inexistente e senha errada
- [x] 403 `conta_desativada` · 403 `email_nao_confirmado`
- [x] Cookie `HttpOnly`, `SameSite=Lax`, `Path=/api/auth`, `Secure` conforme `APP_ENV`
- [x] Testes e2e para os quatro desfechos + asserção sobre os atributos do cookie

**Tests**: e2e · **Gate**: full
**Commit**: `feat(sessao): endpoint de login com jwt e cookie de renovacao`

---

### T17: `POST /api/auth/refresh`

**What**: Implementar a renovação com rotação e detecção de reuso.
**Where**: `app/modules/sessao/controller.py`
**Depends on**: T16
**Reuses**: `SessaoService.renovar` (T15)
**Requirement**: API-04 AC1, AC2, AC3

**Done when**:

- [x] 200 `{ tokenDeAcesso }` e cookie novo, invalidando o anterior
- [x] 401 `nao_autenticado` e cookie limpo quando ausente, expirado ou já rotacionado
- [x] Reapresentar cookie já rotacionado invalida a família: a renovação **seguinte** com o token
      corrente também falha
- [x] Testes e2e para os três casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(sessao): renovacao com rotacao e deteccao de reuso`

---

### T18: `POST /api/auth/logout`

**What**: Implementar o logout idempotente.
**Where**: `app/modules/sessao/controller.py`
**Depends on**: T17
**Reuses**: `SessaoService.encerrar`
**Requirement**: API-04 AC4, AC5

**Done when**:

- [x] **204 sem corpo**, token de renovação invalidado e cookie limpo
- [x] Chamar sem sessão válida também devolve 204 (AC5)
- [x] Após o logout, a renovação com o cookie antigo devolve 401
- [x] Testes e2e para os três casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(sessao): endpoint de logout idempotente`

---

### T19: Autenticação de rota e `GET /api/me`

**What**: Criar o decorator `@exige_autenticacao` e a rota de identidade.
**Where**: `app/core/permissoes.py`, `app/modules/contas/controller.py`
**Depends on**: T16, T7
**Reuses**: substitui `auth_controller.me` (`app/controllers/auth_controller.py:39`)
**Requirement**: API-07 AC1, AC2, API-09 AC3, riscos R2, Edge Case de conta desativada

**Done when**:

- [x] 200 com o usuário **na raiz**, não envolto em `{ user: ... }`
- [x] 401 `nao_autenticado` sem token, com token inválido, com token expirado
- [x] Token válido de usuário **desativado depois da emissão** devolve 401 (Edge Case)
- [x] Token válido de usuário **apagado** devolve 401, não 500 (risco R2)
- [x] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(contas): endpoint de identidade e guarda de autenticacao`

---

### T20: Limite de tentativas de login

**What**: Implementar a contagem em `tentativas_login` e o 429.
**Where**: `app/modules/sessao/{models,service}.py`
**Depends on**: T16
**Reuses**: índice `(email, ocorrido_em DESC)` de T2
**Requirement**: API-20 AC1..AC3

**Done when**:

- [x] A 11ª falha do mesmo e-mail em 15 minutos devolve 429 `muitas_tentativas` com `Retry-After`
- [x] Login com sucesso zera o contador
- [x] Passada a janela, o contador zera
- [x] Testes e2e para os três casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(sessao): limite de tentativas de login`

---

### T21: Matriz de permissões portada do front

**What**: Portar `permissoes.ts` para `app/core/permissoes.py`, com teste de paridade que compara
as duas tabelas.
**Where**: `app/core/permissoes.py`, `tests/unidade/core/test_permissoes.py`
**Depends on**: T5
**Reuses**: `C:\Users\lucas\projeto-extensao\app\src\shared\auth\permissoes.ts` — tabela por tabela
**Requirement**: API-09, riscos R8, R9

**Done when**:

- [x] `Acao` e `Papel` com os mesmos valores da matriz do front
- [x] `pode()` reproduz as três regras: ações de autor valem para toda sessão; administrador soma
      a coluna dele; papéis no mesmo evento acumulam
- [x] **Teste de paridade** lê `permissoes.ts` do repositório do front e falha se qualquer par
      (ação, papel) divergir da tabela em Python (mitigação de R9)
- [x] Teste da tabela completa: toda combinação de ação × papel tem asserção explícita

**Tests**: unit · **Gate**: quick
**Commit**: `feat(core): matriz de permissoes com teste de paridade com o front`

---

### T22: Participações de evento

**What**: Modelo `participacoes_evento` e repositório de consulta por usuário e por evento.
**Where**: `app/modules/eventos/{models,repository}.py`
**Depends on**: T2, T9
**Reuses**: tabela `participacoes_evento` do schema existente
**Requirement**: API-07 AC3..AC6

**Done when**:

- [x] Consulta por usuário devolve participações **ativas**, agregando papéis por evento
- [x] Consulta por (usuário, evento) devolve a lista de papéis ativos, vazia se nenhum
- [x] Constraint `UNIQUE (evento_id, usuario_id, papel)` impede duplicata — teste de integridade
- [x] Participação inativa é omitida de ambas as consultas

**Tests**: integration · **Gate**: full
**Commit**: `feat(eventos): modelo e repositorio de participacoes`

---

### T23: Autorização por papel no evento

**What**: Criar `@exige_acao(acao, evento_de=...)` resolvendo o evento pelo parâmetro de rota.
**Where**: `app/core/permissoes.py`
**Depends on**: T21, T22
**Reuses**: `pode()` (T21), repositório de participações (T22)
**Requirement**: API-09 AC1..AC6

**Done when**:

- [x] 403 `sem_permissao` para usuário sem o papel exigido naquele evento
- [x] 403 em `/admin/*` para `administrador: false`
- [x] 401 (**não** 403) quando não há token — a distinção é preservada (AC3)
- [x] `administrador: true` passa em rota de gestão de qualquer evento
- [x] Autorização roda **antes** da busca do recurso: recurso inexistente + sem permissão devolve
      403, não 404 (AC5)
- [x] Testes cobrindo os cinco ramos

**Tests**: integration · **Gate**: full
**Commit**: `feat(core): guarda de autorizacao por papel no evento`

---

### T24: `GET /api/me/participacoes`

**What**: Implementar a rota que alimenta o seletor de evento e o menu do front.
**Where**: `app/modules/eventos/controllers/participacoes.py`
**Depends on**: T22, T19
**Reuses**: repositório de participações (T22)
**Requirement**: API-07 AC3..AC6

**Done when**:

- [x] 200 com `[{ eventoId, eventoTitulo, identificadorPagina, papeis }]`
- [x] Dois papéis no mesmo evento produzem **uma** entrada com dois papéis (AC4)
- [x] Sem participação alguma devolve **lista vazia**, nunca 404 (AC5)
- [x] Participação inativa omitida (AC6); sem token devolve 401
- [x] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): endpoint de participacoes do usuario`

---

### T25: Modelo e criação de convites

**What**: Modelo `convites` com `tipo` (D3) e hash de token, e o service de criação usado pela
aprovação de evento.
**Where**: `app/modules/convites/{models,service,repository}.py`
**Depends on**: T2, T10
**Reuses**: `EmailService` (T10)
**Requirement**: API-08, D3, AD-017

**Done when**:

- [x] `tipo` ∈ `avaliacao | participacao`; `CHECK` garante `submissao_id` presente só em `avaliacao`
- [x] Só o SHA-256 do token é gravado — teste afirma que o valor cru não está em nenhuma coluna
- [x] `criar_para_participacao(evento, email, papel)` cria convite `participacao` **sem** submissão
- [x] E-mail de convite disparado com a URL completa contendo o token cru

**Tests**: integration · **Gate**: full
**Commit**: `feat(convites): modelo de convite com tipo e hash de token`

---

### T26: `GET /api/convites/{token}`

**What**: Implementar a consulta pública de convite, com D3 e D4.
**Where**: `app/modules/convites/controller.py`
**Depends on**: T25
**Reuses**: `ConviteService.consultar`
**Requirement**: API-08 AC1..AC6, D3, D4

**Done when**:

- [x] 200 **sem sessão** com `tipo` presente e os demais campos do contrato
- [x] `tipo: "participacao"` → `submissaoTitulo` **ausente** da resposta; `tipo: "avaliacao"` →
      presente e não vazio (AC6, D3)
- [x] 404 `convite_invalido` · 410 `convite_expirado` · 409 `convite_ja_usado`, os três com
      `contatoDaOrganizacao` **no corpo do erro, fora de `campos`** (D4)
- [x] `precisaCriarConta` verdadeiro só quando o e-mail não tem conta
- [x] Testes e2e para os seis casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(convites): consulta publica de convite`

---

### T27: `POST /api/convites/{token}/aceitar`

**What**: Implementar o aceite, criando conta quando necessário e abrindo sessão.
**Where**: `app/modules/convites/controller.py`
**Depends on**: T26, T16, T22
**Reuses**: `ContaService` (T11), `SessaoService` (T15), repositório de participações (T22)
**Requirement**: API-08 AC7..AC9

**Done when**:

- [x] E-mail sem conta: cria conta com `emailConfirmado: true`, marca convite aceito, cria a
      participação e devolve `{ tokenDeAcesso, usuario }` + cookie
- [x] E-mail com conta: **só** cria participação e abre sessão, sem alterar nome ou senha (AC8)
- [x] Aceite repetido devolve 409 `convite_ja_usado` com `contatoDaOrganizacao`
- [x] Aceito por alguém logado com **outra** conta vincula ao e-mail do convite (Edge Case)
- [x] Tudo numa transação: falha ao criar participação não deixa conta órfã
- [x] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(convites): aceite de convite com criacao de conta`

---

### T28: Modelos de solicitação e evento

**What**: Modelos `solicitacoes_evento`, `solicitacao_chairs_iniciais` e `eventos`, com repositório.
**Where**: `app/modules/eventos/{models,repository}.py`
**Depends on**: T2, T9
**Reuses**: tipos `SolicitacaoEvento` e `Evento` do front como fonte dos campos
**Requirement**: API-11, API-14, AD-004

**Done when**:

- [ ] As três tabelas com todas as colunas da seção Data Models do design
- [ ] `eventos.evento_pai_id` auto-referência; `UNIQUE (solicitacao_id, email)` em chairs iniciais
- [ ] Repositório: busca por id, por `identificador_pagina`, listagem por solicitante, listagem
      administrativa ordenada por `criado_em` crescente
- [ ] Testes de repositório para cada consulta acima

**Tests**: integration · **Gate**: full
**Commit**: `feat(eventos): modelos de solicitacao e evento`

---

### T29: `POST /api/solicitacoes-evento`

**What**: Implementar a criação de solicitação com todas as validações.
**Where**: `app/modules/eventos/controllers/solicitacoes.py`
**Depends on**: T28, T19
**Reuses**: `SchemaDeEntrada` (T7)
**Requirement**: API-11 AC1..AC5

**Done when**:

- [ ] 201 com a solicitação completa: `situacao: "pendente"`, `criadoEm`, `versao: 1`
- [ ] 422 `campos.identificadorPagina` quando já existe em **solicitação ou evento** (AC2)
- [ ] 422 nomeando o campo faltante entre título, identificador, data de início e de término
- [ ] 422 `campos.dataTermino` quando o término é anterior ao início
- [ ] 422 `campos.eventoPaiId` quando o pai é descendente do próprio evento (ciclo, AC5)
- [ ] 401 sem token
- [ ] Testes e2e para os seis casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): criacao de solicitacao de evento`

---

### T30: Edição e listagem das próprias solicitações

**What**: Implementar `PATCH /api/solicitacoes-evento/{id}` e `GET /api/me/solicitacoes-evento`.
**Where**: `app/modules/eventos/controllers/solicitacoes.py`
**Depends on**: T29
**Reuses**: repositório de solicitações (T28)
**Requirement**: API-11 AC6..AC8, API-09 AC6

**Done when**:

- [ ] `PATCH` em solicitação pendente pelo próprio solicitante aplica, incrementa `versao`, 200
- [ ] `PATCH` em solicitação já decidida devolve 409 `solicitacao_ja_decidida`
- [ ] `PATCH` por quem não é o solicitante devolve 403 (API-09 AC6)
- [ ] `GET /me/solicitacoes-evento` devolve **só** as do próprio usuário
- [ ] Testes e2e para os quatro casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): edicao e listagem das proprias solicitacoes`

---

### T31: `GET /api/admin/solicitacoes-evento`

**What**: Implementar a fila do administrador com filtro e ordenação.
**Where**: `app/modules/eventos/controllers/solicitacoes.py`
**Depends on**: T30, T23
**Reuses**: `@exige_acao('aprovar_solicitacao_evento')` (T23)
**Requirement**: API-12 AC1, AC2

**Done when**:

- [ ] 200 ordenado por `criadoEm` **crescente** — teste com três solicitações fora de ordem
- [ ] `?status=pendente` filtra; sem o parâmetro devolve todas
- [ ] 403 para não administrador; 401 sem token
- [ ] Testes e2e para os quatro casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): fila administrativa de solicitacoes`

---

### T32: `POST /api/admin/solicitacoes-evento/{id}/aprovar`

**What**: Implementar a aprovação criando o evento com os padrões do contrato.
**Where**: `app/modules/eventos/{controllers/solicitacoes.py,services/solicitacao.py}`
**Depends on**: T31
**Reuses**: `transacao()` (T8)
**Requirement**: API-12 AC3, AC4, AC7, AC8

**Done when**:

- [ ] 200 `{ solicitacao, evento }`; solicitação `aprovada` com `decididoPorId` e `decididoEm`
- [ ] Evento nasce `aprovado` com `modeloDeAvaliacao: "aberta"`, `avaliadoresPorSubmissao: 1`,
      `rebuttalHabilitado: false`, `maximoDeRodadas: 1`, `versao: 1` (AC4)
- [ ] Aprovar solicitação já decidida devolve 409 carregando `decididoPorId`, `decididoEm` e
      `situacao` no corpo (AC7)
- [ ] 404 `solicitacao_inexistente`; 403 para não administrador
- [ ] Aprovações simultâneas: só uma cria evento, a outra recebe 409 (Edge Case)
- [ ] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): aprovacao de solicitacao`

---

### T33: Efeitos da aprovação — participações e convites

**What**: Estender a aprovação para criar a participação de chair do solicitante, as dos chairs
iniciais com conta e os convites dos sem conta — tudo na mesma transação.
**Where**: `app/modules/eventos/services/solicitacao.py`
**Depends on**: T32, T25, T22
**Reuses**: `ConviteService.criar_para_participacao` (T25), `transacao()` (T8)
**Requirement**: API-13 AC1..AC6, AD-009

**Done when**:

- [ ] Solicitante vira `chair` ativo do evento criado — `GET /me/participacoes` passa a listá-lo
- [ ] Chair inicial **com** conta vira participação; **sem** conta vira convite `participacao`
      com e-mail disparado
- [ ] E-mail repetido em `chairsIniciais` produz **um** efeito só (AC6)
- [ ] Falha em qualquer etapa não persiste nada — teste que força erro no meio e afirma zero linhas
- [ ] Falha no envio de e-mail **não** desfaz a aprovação; registro fica `situacao='falha'` (AC5)
- [ ] Reprocessar aprovação não duplica participação (Edge Case)
- [ ] Testes de integração para os seis casos

**Tests**: integration · **Gate**: full
**Commit**: `feat(eventos): participacoes e convites na aprovacao`

---

### T34: `POST /api/admin/solicitacoes-evento/{id}/recusar`

**What**: Implementar a recusa com motivo obrigatório.
**Where**: `app/modules/eventos/controllers/solicitacoes.py`
**Depends on**: T32
**Reuses**: service de solicitação (T32)
**Requirement**: API-12 AC5..AC8

**Done when**:

- [ ] 200 com `recusada`, `motivoRecusa`, `decididoPorId`, `decididoEm`
- [ ] 422 `campos.motivo` quando ausente ou vazio
- [ ] 409 com `decididoPorId`/`decididoEm`/`situacao` em solicitação já decidida
- [ ] 404 `solicitacao_inexistente`; 403 para não administrador
- [ ] Recusa **não** cria evento nem participação
- [ ] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): recusa de solicitacao com motivo obrigatorio`

---

### T35: Leitura do evento

**What**: Implementar `GET /api/eventos/{id}` e `GET /api/eventos/por-identificador/{slug}`.
**Where**: `app/modules/eventos/controllers/eventos.py`
**Depends on**: T28, T19
**Reuses**: repositório de eventos (T28)
**Requirement**: API-14 AC1, AC2

**Done when**:

- [x] 200 com o evento completo em ambas as rotas
- [x] 404 `evento_inexistente` em ambas
- [x] `por-identificador` resolve **sem exigir participação** (AC2) — teste com usuário sem papel
- [x] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): leitura de evento por id e por identificador`

---

### T36: `PATCH /api/eventos/{id}` com lock otimista

**What**: Implementar a edição do evento com controle de versão (D2) e as validações de parâmetro.
**Where**: `app/modules/eventos/controllers/eventos.py`
**Depends on**: T35, T23
**Reuses**: `ConflitoDeVersao` (T5), `@exige_acao('configurar_evento')` (T23)
**Requirement**: API-14 AC3..AC7, D2

**Done when**:

- [x] `versao` igual: aplica, incrementa `versao` em 1, 200
- [x] `versao` diferente: 409 `conflito_de_versao` com o evento atual em **`atual`** (D2)
- [x] 422 `campos.avaliadoresPorSubmissao` quando não é inteiro ≥ 1
- [x] 422 `campos.prazoRebuttalDias` quando rebuttal ligado sem prazo
- [x] 422 `campos.maximoDeRodadas` quando não é inteiro ≥ 1
- [x] 422 `campos.identificadorPagina` ao alterá-lo em evento já publicado (Edge Case)
- [x] 403 para quem não é chair do evento
- [x] Testes e2e para os sete casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): edicao de evento com lock otimista`

---

### T37: `GET /api/eventos/{id}/descendentes`

**What**: Implementar a travessia da árvore de eventos, à prova de ciclo.
**Where**: `app/modules/eventos/controllers/eventos.py`
**Depends on**: T35
**Reuses**: repositório de eventos (T28)
**Requirement**: API-14 AC8, Edge Case de ciclo

**Done when**:

- [x] 200 `{ descendentes: [...] }` com **toda** a árvore — teste com três níveis (filho, neto,
      bisneto)
- [x] Evento folha devolve lista vazia
- [x] Ciclo em dados legados termina sem recursão infinita, visitando cada evento uma vez
- [x] Testes e2e para os três casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): arvore de descendentes`

---

### T38: Trilhas

**What**: Implementar `GET`/`POST /api/eventos/{id}/trilhas` e `PATCH /api/trilhas/{id}`.
**Where**: `app/modules/eventos/controllers/trilhas.py`, `models.py`
**Depends on**: T36
**Reuses**: `@exige_acao('configurar_evento')`, tabela mínima `submissoes` (T43 fornece a contagem;
até lá a contagem é 0 por ausência de linhas, não por valor fixo)
**Requirement**: API-15 AC1..AC7

**Done when**:

- [x] `GET` devolve as trilhas do evento com `submissoesVinculadas` **derivado por consulta**
- [x] `POST` devolve 201 com `ativa: true` e `submissoesVinculadas: 0`
- [x] 422 `campos.nome` quando vazio, e quando repete nome dentro do mesmo evento (AC7)
- [x] `PATCH` aplica e devolve a trilha; desativar com submissões vinculadas **é permitido** e a
      resposta traz a contagem (AC5)
- [x] 404 `trilha_inexistente`; 403 para não chair
- [x] Testes e2e para os sete casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): trilhas do evento`

---

### T39: Chamadas — leitura, criação e edição

**What**: Implementar `GET`/`POST /api/eventos/{id}/chamadas` e `PATCH /api/chamadas/{id}`.
**Where**: `app/modules/eventos/controllers/chamadas.py`, `models.py`
**Depends on**: T38
**Reuses**: `ConflitoDeVersao` (T5)
**Requirement**: API-16 AC1..AC5, AC9, AC10

**Done when**:

- [x] `GET` devolve as chamadas do evento; `POST` devolve 201 com `encerradaManualmente: false`,
      `versao: 1`
- [x] 422 `campos.dataLimite` quando limite ≤ abertura, **na criação e na edição** (AC3)
- [x] `PATCH` com `versao` divergente devolve 409 `conflito_de_versao` com a chamada em `atual`
- [x] `PATCH` com sucesso incrementa `versao` em 1
- [x] 422 `campos.tamanhoMaximoMb` acima do limite do servidor (AC9)
- [x] 404 `chamada_inexistente`; 403 para não chair
- [x] Testes e2e para os sete casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): chamadas do evento`

---

### T40: Prorrogar e encerrar chamada

**What**: Implementar `POST /api/chamadas/{id}/prorrogar` e `/encerrar`.
**Where**: `app/modules/eventos/controllers/chamadas.py`
**Depends on**: T39
**Reuses**: service de chamadas (T39)
**Requirement**: API-16 AC6..AC8

**Done when**:

- [x] Prorrogar para data posterior atualiza o prazo, incrementa `versao`, 200
- [x] 422 `campos.dataLimite` quando a nova data é anterior, igual ou ausente — **prorrogar nunca
      encurta prazo** (AC7)
- [x] Encerrar marca `encerradaManualmente: true`, incrementa `versao`, 200
- [x] 404 em ambas; 403 para não chair
- [x] Testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): prorrogacao e encerramento de chamada`

---

### T41: Critérios — leitura, criação e edição

**What**: Implementar `GET`/`POST /api/eventos/{id}/criterios` e `PATCH /api/criterios/{id}`.
**Where**: `app/modules/eventos/controllers/criterios.py`, `models.py`
**Depends on**: T39
**Reuses**: `@exige_acao('definir_criterios_e_etapas')`
**Requirement**: API-17 AC1..AC4, AC8

**Done when**:

- [x] `GET` devolve os critérios com `temNotas` **derivado por consulta** a `notas_parecer`
- [x] `POST` devolve 201 com `ativo: true` e `temNotas: false`
- [x] 422 `campos.notaMaxima` quando máxima ≤ mínima, na criação **e** na edição
- [x] 422 `campos.peso` quando peso ≤ 0, na criação **e** na edição
- [x] `ordem` ausente recebe a próxima posição livre **dentro daquele evento** (AC8) — teste com
      dois eventos para provar que a numeração não vaza entre eles
- [x] 403 para quem não é chair
- [x] Testes e2e para os seis casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): criterios de avaliacao`

---

### T42: `DELETE /api/criterios/{id}`

**What**: Implementar a exclusão de critério com bloqueio por notas existentes.
**Where**: `app/modules/eventos/controllers/criterios.py`
**Depends on**: T41
**Reuses**: tabela mínima `notas_parecer` (T2)
**Requirement**: API-17 AC5..AC7

**Done when**:

- [x] Critério sem notas: **204 sem corpo**, linha removida
- [x] Critério com nota (inserida no teste em `notas_parecer`): 409 `criterio_com_notas` com o
      campo extra `acaoSugerida: "desativar"`
- [x] 404 `criterio_inexistente`; 403 para não chair
- [x] Testes e2e para os quatro casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): exclusao de criterio com bloqueio por notas`

---

### T43: Consultas das tabelas mínimas de áreas futuras

**What**: Implementar as quatro consultas derivadas que alimentam campos do contrato, com as
tabelas de AD-018.
**Where**: `app/modules/eventos/repository.py`
**Depends on**: T2, T38, T41
**Reuses**: tabelas `formularios_chamada`, `fases_evento`, `submissoes`, `notas_parecer` (T2)
**Requirement**: AD-018, API-18 AC4, AC5, API-15 AC1, API-17 AC1

**Done when**:

- [ ] `tem_formulario(evento)` por `EXISTS` sobre chamadas do evento
- [ ] `tem_fases(evento)` por `EXISTS`
- [ ] `contar_submissoes_da_trilha(trilha)` por `COUNT`
- [ ] `criterio_tem_notas(criterio)` por `EXISTS`
- [ ] Cada consulta tem teste com a tabela vazia **e** com linha inserida — nenhum valor é fixo

**Tests**: integration · **Gate**: full
**Commit**: `feat(eventos): consultas derivadas das tabelas de areas futuras`

---

### T44: `GET /api/eventos/{id}/checklist-publicacao`

**What**: Implementar o checklist com os cinco sinalizadores.
**Where**: `app/modules/eventos/controllers/publicacao.py`
**Depends on**: T43
**Reuses**: consultas derivadas (T43)
**Requirement**: API-18 AC1..AC6

**Done when**:

- [ ] 200 com os cinco booleanos do contrato
- [ ] `temChamada` reflete existência de chamada; `temCriterioAtivo` **ignora** critério inativo
      (AC3) — teste com só um critério inativo
- [ ] `formularioDefinido` e `etapasDefinidas` vêm de T43, não de valor fixo
- [ ] `eventoAprovado` verdadeiro em `aprovado` **e** em `publicado`
- [ ] 404 e 403; testes e2e para os seis casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): checklist de publicacao`

---

### T45: `POST /api/eventos/{id}/publicar`

**What**: Implementar a publicação com as três barreiras.
**Where**: `app/modules/eventos/controllers/publicacao.py`
**Depends on**: T44
**Reuses**: `ConflitoDeVersao` (T5), checklist (T44)
**Requirement**: API-18 AC7..AC10

**Done when**:

- [ ] Evento não aprovado: 409 `evento_nao_aprovado`
- [ ] Checklist incompleto: 422 `checklist_incompleto` com **uma chave por item faltante**,
      nomeada com o próprio nome do item (AC8) — teste com dois itens faltando
- [ ] `versao` divergente: 409 `conflito_de_versao` com o evento em `atual`
- [ ] Tudo satisfeito: situação vira `publicado`, `versao` incrementa, 200
- [ ] 403 para não chair; testes e2e para os cinco casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): publicacao de evento`

---

### T46: Vitrine pública e meus eventos

**What**: Implementar `GET /api/eventos` (pública) e `GET /api/me/eventos`, com dados
estruturados (D1).
**Where**: `app/modules/eventos/controllers/vitrine.py`
**Depends on**: T45, T22
**Reuses**: repositório de eventos (T28) e de participações (T22)
**Requirement**: API-19 AC1..AC6, D1

**Done when**:

- [ ] `GET /api/eventos` responde 200 **sem header de autorização**
- [ ] Devolve `cidade`, `estado`, `pais`, `dataInicio`, `dataTermino` — e **não** devolve `local`
      nem `periodo` (D1), verificado por asserção de ausência
- [ ] Evento não publicado omitido da vitrine
- [ ] `subEventos` lista os filhos publicados
- [ ] `GET /api/me/eventos` devolve só os de participação ativa; 401 sem sessão
- [ ] Testes e2e para os seis casos

**Tests**: e2e · **Gate**: full
**Commit**: `feat(eventos): vitrine publica e eventos do usuario`

---

### T47: Handlers MSW do front — as quatro divergências

**What**: Atualizar os handlers MSW do repositório do front para refletir D1..D4.
**Where**: `C:\Users\lucas\projeto-extensao\app\src\mocks\handlers\{cascas,convites,eventos-e-chamadas}.ts`
**Depends on**: T46
**Reuses**: os próprios handlers existentes
**Requirement**: API-23 AC1

**Done when**:

- [ ] `cascas.ts`: `/eventos` e `/me/eventos` devolvem dados estruturados (D1)
- [ ] `convites.ts`: convite ganha `tipo`, `submissaoTitulo` opcional (D3) e o contato sai de
      `campos` para `contatoDaOrganizacao` no corpo (D4)
- [ ] `eventos-e-chamadas.ts`: conflito de versão passa a `{ codigo, mensagem, correlacao, atual }` (D2)
- [ ] Dados de mock em `dados/index.ts` ajustados ao formato novo
- [ ] `npm run gate` no front sai 0 ao fim da fase (as tarefas seguintes fecham os testes)

**Tests**: unit + integration (Vitest) · **Gate**: front
**Commit**: `feat(mocks): handlers refletem as 4 divergencias do contrato`

---

### T48: D1 nos componentes de vitrine

**What**: Fazer `EventosPublicos` e `MinhasParticipacoes` formatarem local e período a partir dos
dados estruturados.
**Where**: `app/src/app/paginas/{EventosPublicos,MinhasParticipacoes}.tsx` (repo do front)
**Depends on**: T47
**Reuses**: utilitários de data de `shared/lib/datas.ts`
**Requirement**: API-23 AC2

**Done when**:

- [ ] O texto exibido de local e período é **idêntico** ao de antes — teste compara a string
- [ ] A formatação vive na camada de apresentação, não no tipo de dados
- [ ] Testes existentes dessas telas reescritos para o formato novo, nenhum removido
- [ ] `npm run gate` sai 0

**Tests**: unit + integration (Vitest) · **Gate**: front
**Commit**: `refactor(vitrine): formata local e periodo no front`

---

### T49: D2 no tratamento de conflito

**What**: Fazer as três camadas de API do front lerem o registro atual de `atual` no erro
normalizado.
**Where**: `app/src/features/eventos-e-chamadas/api/{evento,chamadas,publicacao}.ts` (repo do front)
**Depends on**: T47
**Reuses**: `normalizarErro` de `shared/lib/erros.ts`
**Requirement**: API-23 AC3

**Done when**:

- [ ] `ErroApi` carrega `atual` e as três camadas o consomem
- [ ] O comportamento de "recarregar" observável pelo usuário é **idêntico** ao de antes
- [ ] Testes de conflito reescritos para o formato novo, nenhum removido
- [ ] `npm run gate` sai 0

**Tests**: unit + integration (Vitest) · **Gate**: front
**Commit**: `refactor(evt): conflito de versao pelo envelope de erro`

---

### T50: D3 e D4 na tela de convite

**What**: Condicionar a exibição do título de submissão ao `tipo` e ler o contato do campo próprio.
**Where**: `app/src/features/plataforma-base/convites/TelaDeConvite.tsx` (repo do front)
**Depends on**: T47
**Reuses**: a própria tela
**Requirement**: API-23 AC4, AC5

**Done when**:

- [ ] `tipo: "participacao"` **não** exibe linha de título de submissão; `tipo: "avaliacao"` exibe
      como antes
- [ ] Contato lido de `contatoDaOrganizacao`, e o contato exibido é o mesmo de antes
- [ ] Testes da tela reescritos, nenhum removido
- [ ] `npm run gate` sai 0

**Tests**: unit + integration (Vitest) · **Gate**: front
**Commit**: `refactor(convites): tipo de convite e contato em campo proprio`

---

### T51: Proxy do Vite e MSW desligável

**What**: Apontar `/api` para a API real em desenvolvimento e permitir desligar o MSW por variável
de ambiente.
**Where**: `app/vite.config.ts`, `app/src/main.tsx`, `app/.env.example` (repo do front)
**Depends on**: T50
**Reuses**: `worker.start()` já condicionado a `import.meta.env.DEV` em `main.tsx`
**Requirement**: API-21 AC2, AC3, AD-011

**Done when**:

- [ ] `server.proxy['/api'] → http://localhost:5000` no `vite.config.ts`
- [ ] MSW só inicia quando a variável de ambiente o habilita — **sem alteração de código** para
      alternar (AC3)
- [ ] `.env.example` do front documenta a variável
- [ ] `npm run gate` sai 0

**Tests**: unit (Vitest) · **Gate**: front
**Commit**: `feat(dev): proxy para a api real e msw desligavel`

---

### T52: Comando `flask seed`

**What**: Criar o comando de dados de demonstração, equivalente ao seed do MSW.
**Where**: `app/cli.py`
**Depends on**: T46
**Reuses**: `src/mocks/handlers/seedDeDemonstracao.test.ts` do front como referência do conteúdo
**Requirement**: escolha do responsável (2026-09-07), destrava API-21

**Done when**:

- [ ] Cria administrador, usuários de exemplo, e um evento aprovado com trilha, chamada e critérios
- [ ] Recusa executar quando `APP_ENV=production`
- [ ] Rodar duas vezes não duplica dados (idempotente por e-mail e identificador de página)
- [ ] Teste que roda o comando e afirma o estado resultante

**Tests**: integration · **Gate**: full
**Commit**: `feat(cli): comando de dados de demonstracao`

---

### T53: `.env.example` e README

**What**: Documentar todas as variáveis, como rodar, e o fluxo de migration para o time.
**Where**: `.env.example`, `README.md`
**Depends on**: T52
**Reuses**: `README.md` existente (a documentação de rotas dele é substituída)
**Requirement**: API-21 AC5

**Done when**:

- [ ] `.env.example` completo, sem segredo real
- [ ] README documenta subir, rodar migrations, criar migration nova, rodar testes e o seed
- [ ] README avisa que a migração para UUID exige descartar o volume local uma vez (risco R11)
- [ ] A documentação de rotas do README reflete o contrato real desta rodada

**Tests**: none · **Gate**: build
**Commit**: `docs: variaveis de ambiente e fluxo de trabalho do time`

---

### T54: Percurso completo ponta a ponta

**What**: Um teste que exercita o percurso inteiro da spec num único fluxo, contra o banco real.
**Where**: `tests/e2e/test_percurso_completo.py`
**Depends on**: T53, T51
**Reuses**: fixtures de T1
**Requirement**: Success Criteria da spec

**Done when**:

- [ ] Cadastro → confirmação de e-mail (token lido de `emails_enviados`) → login → solicitar
      evento → aprovar como administrador → o solicitante vê o evento em `/me/participacoes` →
      criar trilha, chamada e critério → publicar → o evento aparece em `GET /api/eventos`
- [ ] O percurso roda numa única transação de teste, sem limpeza manual
- [ ] Falha em qualquer etapa faz o comando sair com código diferente de zero

**Tests**: e2e · **Gate**: full
**Commit**: `test: percurso completo de cadastro a publicacao`

---

## Phase Execution Map

```
Fase 0 → Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6 → Fase 7 → Fase 8 → Fase 9

Fase 0:  T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8
Fase 1:  T9 → T10 → T11 → T12 → T13 → T14
Fase 2:  T15 → T16 → T17 → T18 → T19 → T20
Fase 3:  T21 → T22 → T23 → T24
Fase 4:  T25 → T26 → T27
Fase 5:  T28 → T29 → T30 → T31 → T32 → T33 → T34
Fase 6:  T35 → T36 → T37 → T38 → T39 → T40 → T41 → T42
Fase 7:  T43 → T44 → T45 → T46
Fase 8:  T47 → T48 → T49 → T50 → T51
Fase 9:  T52 → T53 → T54
```

Execução estritamente sequencial — não há paralelismo dentro de uma fase.

**Empacotamento em lotes (~7 tarefas por trabalhador, fases inteiras):**

| Lote | Fases | Tarefas | Gate |
| ---- | ----- | ------- | ---- |
| L1 | Fase 0 | T1–T8 (8) | `pytest` + build |
| L2 | Fase 1 | T9–T14 (6) | `pytest` |
| L3 | Fase 2 | T15–T20 (6) | `pytest` |
| L4 | Fases 3+4 | T21–T27 (7) | `pytest` |
| L5 | Fase 5 | T28–T34 (7) | `pytest` |
| L6 | Fase 6 | T35–T42 (8) | `pytest` |
| L7 | Fase 7 | T43–T46 (4) | `pytest` |
| L8 | Fase 8 | T47–T51 (5) | `npm run gate` (repo do front) |
| L9 | Fase 9 | T52–T54 (3) | `pytest` + build |

**54 tarefas, 9 lotes.** A Fase 8 fica isolada de propósito: outro repositório, outro gate.

---

## Task Granularity Check

| Faixa | Escopo típico | Status |
| ----- | ------------- | ------ |
| T1, T3, T5, T6, T7, T8 | 1 arquivo de infraestrutura, 1 conceito | ✅ Granular |
| T2 | 1 migration — grande em linhas, mas **um** artefato indivisível: Alembic não admite meia migration inicial | ⚠️ Aceito |
| T4 | 3 arquivos de contêiner, coesos por uma única mudança (tirar o debugger do caminho de produção) | ⚠️ Aceito |
| T9, T12, T15, T22, T25, T28, T43 | 1 modelo + seu repositório, mesmo módulo | ⚠️ Coeso, OK |
| T11, T13, T14, T16, T17, T18, T19, T20, T24, T26, T27, T29, T31, T32, T34, T35, T36, T37, T42, T44, T45 | 1 endpoint | ✅ Granular |
| T30, T38, T39, T40, T41, T46 | 2–3 endpoints do mesmo recurso, mesmo arquivo | ⚠️ Coeso, OK |
| T21, T23 | 1 módulo puro / 1 decorator | ✅ Granular |
| T33 | 1 comportamento de service (efeitos da aprovação) | ✅ Granular |
| T47–T51 | 1 arquivo ou 1 par de componentes por tarefa | ✅ Granular |
| T52, T53, T54 | 1 comando / 1 documento / 1 teste | ✅ Granular |

Nenhuma tarefa reprovada. As duas marcadas ⚠️ com justificativa (T2, T4) são indivisíveis pela
natureza do artefato, não por conveniência.

---

## Diagram-Definition Cross-Check

| Tarefa | `Depends on` no corpo | Diagrama mostra | Status |
| ------ | --------------------- | --------------- | ------ |
| T1 | None | (início da Fase 0) | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T1 | T2 → T3 (cadeia da fase; T1 é ancestral) | ✅ |
| T4 | T2, T3 | T3 → T4 (T2 ancestral na cadeia) | ✅ |
| T5 | T1 | T4 → T5 (T1 ancestral) | ✅ |
| T6 | T5 | T5 → T6 | ✅ |
| T7 | T1 | T6 → T7 (T1 ancestral) | ✅ |
| T8 | T1, T5 | T7 → T8 (ambos ancestrais) | ✅ |
| T9 | T2, T8 | Fase 0 → Fase 1, T9 primeiro | ✅ |
| T10 | T2, T3 | T9 → T10 (Fase 0 ancestral) | ✅ |
| T11 | T5, T7, T9, T10 | T10 → T11 | ✅ |
| T12 | T11 | T11 → T12 | ✅ |
| T13 | T12 | T12 → T13 | ✅ |
| T14 | T13 | T13 → T14 | ✅ |
| T15 | T2, T8 | Fase 1 → Fase 2, T15 primeiro | ✅ |
| T16 | T15, T11 | T15 → T16 (T11 em fase anterior) | ✅ |
| T17 | T16 | T16 → T17 | ✅ |
| T18 | T17 | T17 → T18 | ✅ |
| T19 | T16, T7 | T18 → T19 (ambos ancestrais) | ✅ |
| T20 | T16 | T19 → T20 (T16 ancestral) | ✅ |
| T21 | T5 | Fase 2 → Fase 3, T21 primeiro | ✅ |
| T22 | T2, T9 | T21 → T22 (fases anteriores) | ✅ |
| T23 | T21, T22 | T22 → T23 | ✅ |
| T24 | T22, T19 | T23 → T24 | ✅ |
| T25 | T2, T10 | Fase 3 → Fase 4, T25 primeiro | ✅ |
| T26 | T25 | T25 → T26 | ✅ |
| T27 | T26, T16, T22 | T26 → T27 | ✅ |
| T28 | T2, T9 | Fase 4 → Fase 5, T28 primeiro | ✅ |
| T29 | T28, T19 | T28 → T29 | ✅ |
| T30 | T29 | T29 → T30 | ✅ |
| T31 | T30, T23 | T30 → T31 | ✅ |
| T32 | T31 | T31 → T32 | ✅ |
| T33 | T32, T25, T22 | T32 → T33 | ✅ |
| T34 | T32 | T33 → T34 (T32 ancestral) | ✅ |
| T35 | T28, T19 | Fase 5 → Fase 6, T35 primeiro | ✅ |
| T36 | T35, T23 | T35 → T36 | ✅ |
| T37 | T35 | T36 → T37 (T35 ancestral) | ✅ |
| T38 | T36 | T37 → T38 (T36 ancestral) | ✅ |
| T39 | T38 | T38 → T39 | ✅ |
| T40 | T39 | T39 → T40 | ✅ |
| T41 | T39 | T40 → T41 (T39 ancestral) | ✅ |
| T42 | T41 | T41 → T42 | ✅ |
| T43 | T2, T38, T41 | Fase 6 → Fase 7, T43 primeiro | ✅ |
| T44 | T43 | T43 → T44 | ✅ |
| T45 | T44 | T44 → T45 | ✅ |
| T46 | T45, T22 | T45 → T46 | ✅ |
| T47 | T46 | Fase 7 → Fase 8, T47 primeiro | ✅ |
| T48 | T47 | T47 → T48 | ✅ |
| T49 | T47 | T48 → T49 (T47 ancestral) | ✅ |
| T50 | T47 | T49 → T50 (T47 ancestral) | ✅ |
| T51 | T50 | T50 → T51 | ✅ |
| T52 | T46 | Fase 8 → Fase 9, T52 primeiro (T46 em fase anterior) | ✅ |
| T53 | T52 | T52 → T53 | ✅ |
| T54 | T53, T51 | T53 → T54 (T51 em fase anterior) | ✅ |

Nenhuma dependência aponta para fase posterior. Todas as setas do diagrama correspondem a
dependências reais ou a ordem sequencial dentro da fase.

---

## Test Co-location Validation

| Tarefa | Camada criada/modificada | Matriz exige | Tarefa declara | Status |
| ------ | ------------------------ | ------------ | -------------- | ------ |
| T1 | Infra de teste + acesso a dados | integration | integration | ✅ |
| T2 | Models + migration | none (gate de build) — mas cria acesso a dados verificável | integration | ✅ (excede a matriz, intencional) |
| T3 | Config | none | unit | ✅ (excede, intencional) |
| T4 | Config/contêiner | none | unit | ✅ (excede, intencional) |
| T5, T6, T7 | `app/core/` puro | unit | unit | ✅ |
| T8 | `app/core/` + repositório | integration | integration | ✅ |
| T9 | Model + repository | integration | integration | ✅ |
| T10 | Service + model | integration | integration | ✅ |
| T11, T13, T14 | Controller / rota | e2e | e2e | ✅ |
| T12 | Model + service | integration | integration | ✅ |
| T15 | Model + service + repository | integration | integration | ✅ |
| T16, T17, T18, T19, T20 | Controller / rota | e2e | e2e | ✅ |
| T21 | `app/core/` puro | unit | unit | ✅ |
| T22 | Model + repository | integration | integration | ✅ |
| T23 | `app/core/` + acesso a dados | integration | integration | ✅ |
| T24, T26, T27 | Controller / rota | e2e | e2e | ✅ |
| T25 | Model + service + repository | integration | integration | ✅ |
| T28 | Model + repository | integration | integration | ✅ |
| T29–T32, T34–T42, T44, T45, T46 | Controller / rota | e2e | e2e | ✅ |
| T33 | Service / regra de negócio | integration | integration | ✅ |
| T43 | Repository | integration | integration | ✅ |
| T47–T51 | Front (mocks, componentes, config) | unit + integration (Vitest) | unit + integration | ✅ |
| T52 | CLI + acesso a dados | integration | integration | ✅ |
| T53 | Documentação | none | none | ✅ |
| T54 | Controller / rota (percurso) | e2e | e2e | ✅ |

Nenhuma violação. Nenhuma tarefa declara `Tests: none` fora do que a matriz permite — **T53 é a
única**, e é documentação pura.
