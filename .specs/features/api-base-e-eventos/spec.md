# API REST — plataforma-base e eventos-e-chamadas

## Problem Statement

O front do SGS (`C:\Users\lucas\projeto-extensao`) tem cinco áreas implementadas e verificadas com
1302 testes, mas não tem servidor: em desenvolvimento ele fala com handlers MSW que simulam a API.
Este repositório contém apenas autenticação por sessão Flask, com rotas, formato de corpo e
envelope de erro que **não coincidem** com o que o front chama. Enquanto essa divergência existir,
nenhuma tela pode ser ligada a dados reais.

O que falta é a API que o front já sabe consumir — mesmas rotas, mesmos corpos, mesmos códigos de
status — para as duas áreas cujas telas estão prontas: **plataforma-base** (sessão, contas,
participações, convites) e **eventos-e-chamadas** (solicitação, aprovação, configuração, trilhas,
chamadas, critérios, publicação).

## Goals

- [ ] Os 34 endpoints de BASE e EVT respondem com o mesmo contrato dos handlers MSW do front —
      verificável trocando o MSW pela API real sem alterar código de tela.
- [ ] Um usuário percorre cadastro → confirmação de e-mail → login → solicitar evento → (admin)
      aprovar → configurar trilhas, chamada e critérios → publicar, contra Postgres real.
- [ ] Toda escrita de gestão é bloqueada com 403 para quem não tem o papel exigido no evento.
- [ ] O schema do banco é versionado por migration e evolui sem derrubar o volume do Postgres.

## Out of Scope

Explicitamente excluído. Documentado para impedir avanço de escopo.

| Feature | Reason |
| ------- | ------ |
| FORM (formulário dinâmico), FASE (etapas), SUB (submissão), AVAL, DEC, ACOMP | AD-003 — rodadas seguintes. Desta rodada saem apenas as duas tabelas vazias que o checklist de publicação consulta (AD-007) |
| Upload e download de arquivos (`/arquivos/{id}/download`, versões de submissão) | Pertence a SUB. Exige decisão de armazenamento (disco, S3, MinIO) e URL assinada — não tomada |
| Envio real por SMTP | AD-010 — backend de log em desenvolvimento; SMTP quando houver credencial institucional |
| `PATCH /me`, `PATCH /me/senha`, recuperação de senha (BASE-06, BASE-07) | P2 no front, sem tela implementada. Nenhum código de front chama essas rotas hoje |
| `GET/PATCH /admin/usuarios` (BASE-12) | P2 no front, sem tela implementada |
| `GET/POST/PATCH /eventos/{id}/participacoes` (EVT-12, equipe do evento) | P2 no front, sem tela implementada. A participação de chair nasce da aprovação (AD-009) |
| `GET /publico/eventos/{identificador_pagina}` completo (EVT-13) | Só a fatia que o front chama hoje: `GET /eventos/por-identificador/{slug}` |
| Trilha de auditoria (`log_auditoria`) | Pertence a ACOMP |
| Deploy, HTTPS, hardening de produção | Rodada de infraestrutura própria |

---

## Assumptions & Open Questions

Toda ambiguidade está resolvida ou registrada aqui — nada fica silenciosamente indefinido.

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Origem do contrato | Handlers MSW do front, não a tabela resumida das specs — como ponto de partida negociável, não como autoridade | O handler é o que o código do front exercita; as tabelas divergem dele em 4 rotas. Onde a API tiver razão, o front se adapta (ver "Divergências propostas") | y (AD-001) |
| Mecanismo de sessão | JWT de acesso + refresh em cookie httpOnly | O cliente do front já o implementa | y (AD-002) |
| Tipo de chave primária | UUID v4, serializado como string | O front tipa todo `id` como `string` | y (AD-004) |
| Evolução do schema | Alembic / Flask-Migrate | O schema cresce por feature; `initdb.d` só roda em banco vazio | y (AD-005) |
| Validação e serialização | Pydantic v2 + handler de erro central | O envelope `campos` é exigido em todo 422 | y (AD-006) |
| Sinalizadores do checklist | Tabelas mínimas de FORM/FASE, `EXISTS` | Não mentir nem travar a publicação | y (AD-007) |
| Autorização | RBAC real por papel no evento | O backend é a autoridade (AD-001 do front) | y (AD-008) |
| Efeitos da aprovação | Chair do solicitante + participações + convites | Sem isso `/me/participacoes` volta vazio | y (AD-009) |
| Entrega de e-mail | Backend trocável, log em dev | Sem credencial SMTP disponível | y (AD-010) |
| Integração front↔API em dev | Proxy `/api` no Vite | Base relativa + cookie `SameSite=Lax` | y (AD-011) |
| Gate de testes | pytest contra Postgres real (`sgs_test`) | UUID/TIMESTAMPTZ/ENUM diferem em SQLite | y (AD-012) |
| Vida do token de acesso | 15 minutos | Curto o bastante para limitar dano de vazamento, longo o bastante para não renovar a cada tela. O front renova sozinho em 401 | n — assumption |
| Vida do token de renovação | 14 dias, rotacionado a cada uso | Rotação detecta reuso de token roubado; 14 dias evita relogin semanal | n — assumption |
| Formato de data/hora nas respostas | ISO-8601 em UTC com sufixo `Z` | O front formata para o fuso do evento na exibição; a API não decide apresentação. O mock usa `-03:00`, mas nenhum teste do front compara a string crua | n — assumption |
| `GET /eventos` e `GET /me/eventos` (cascas herdadas por EVT) | Implementados, derivando `local` de cidade/estado/país e `periodo` de dataInicio–dataTermino | O arquivo de cascas do front nomeia EVT como herdeira e são duas telas reais. Sem isso continuam presas ao MSW | n — assumption |
| `versao` de trilha e critério | Não têm `versao`; só evento e chamada usam lock otimista | É o que o contrato do front mostra: `Trilha` e `Criterio` não têm o campo | n — assumption |
| `correlacao` no envelope de erro | UUID por requisição, também em log e no header `X-Correlacao` | O contrato exige o campo; o valor `cor-{codigo}` do mock é artefato de teste, não requisito | n — assumption |
| Idioma das mensagens de erro | pt-BR, iguais às dos handlers MSW quando existirem | O front exibe a `mensagem` da API diretamente em várias telas | n — assumption |
| `identificadorPagina` | Único entre solicitações **e** eventos, imutável depois de publicado | O handler valida a unicidade cruzada; a imutabilidade fecha uma lacuna que a spec do front declara como caso de borda | n — assumption |

**Open questions:** none — todas resolvidas ou registradas acima.

---

## Divergências propostas ao contrato do front

O contrato é ponto de partida, não autoridade (AD-001). Estes quatro pontos codificam limitações
do mock, não requisitos, e a API tem razão contra eles. **As quatro foram aceitas pelo responsável
em 2026-09-07 (AD-014)** e as ACs abaixo já as refletem. O front é alterado no mesmo ciclo,
handlers, componentes e testes juntos (AD-015, requisito API-23).

| # | Hoje no contrato | Proposto | Por quê | Custo no front | Bloqueia? |
| - | ---------------- | -------- | ------- | -------------- | --------- |
| D1 | `GET /eventos` devolve `local` e `periodo` como **texto já formatado** | Devolver `cidade`, `estado`, `pais`, `dataInicio`, `dataTermino`; o front formata | Formatar apresentação não é trabalho da API — e sem os dados brutos o front não consegue traduzir, ordenar por data nem exibir no fuso do evento. O próprio `cascas.ts` declara que esse tipo "morre junto com o handler" quando EVT assumir a rota | `EventosPublicos.tsx` e `MinhasParticipacoes.tsx` passam a formatar; ~2 componentes e seus testes | Não |
| D2 | Conflito de versão responde **409 com o registro cru** no corpo | 409 com o envelope padrão + o registro em `atual` | É a única resposta de erro do contrato fora do envelope universal, e obriga `normalizarErro` a ter um caminho especial. Com `atual` a tela recebe a mesma informação sem a exceção à regra | `evento.ts`, `chamadas.ts`, `publicacao.ts` leem `erro.atual` em vez do corpo; ~3 arquivos | Não |
| D3 | Convite tem `submissaoTitulo` **obrigatório** | Convite ganha `tipo` (`avaliacao \| participacao`) e `submissaoTitulo` passa a opcional | AD-009 cria convite de **chair**, que não tem submissão alguma. Sem isto, a API teria de inventar um título de submissão inexistente para preencher o campo | `TelaDeConvite.tsx` condiciona a exibição do título ao `tipo`; 1 arquivo | **Sim** — AD-009 não se implementa honestamente sem ela |
| D4 | Contato da organização viaja em `campos.contato` no erro de convite | Campo próprio `contatoDaOrganizacao` no corpo do erro | `campos` significa "erro por campo de formulário"; o comentário do próprio handler admite que foi usado só por ser "o único campo capaz de carregar dado junto de um 404". Usá-lo para outra coisa quebra o significado do envelope | `TelaDeConvite.tsx` lê outro campo; 1 arquivo | Não |

ACs que as incorporam: D1 → API-19 AC1 e AC3 · D2 → API-14 AC4, API-16 AC4, API-18 AC9 ·
D3 → API-08 AC1 e AC6, API-13 AC3 · D4 → API-08 AC2, AC3 e AC4. O trabalho correspondente no
repositório do front é o requisito **API-23**.

---

## Implicit-Requirement Dimensions Sweep

| Dimensão | Resolução |
| -------- | --------- |
| Validação de entrada e limites | API-01, API-06, API-14, API-20, API-21 — Pydantic por endpoint, envelope `campos`, limites de tamanho de corpo |
| Falhas e falhas parciais | API-16 — aprovação é transação única (evento + participações + convites + e-mails); e-mail que falha não desfaz a aprovação, é registrado como pendente |
| Idempotência / repetição / duplicidade | API-05, API-07, API-10, API-15 — renovação concorrente, confirmação repetida (409), aceite de convite repetido (409), decisão repetida de solicitação (409) |
| Fronteiras de autorização e limite de taxa | API-11 (RBAC por papel), API-12 (429 no login) |
| Concorrência e ordenação | API-18 — lock otimista por `versao` em evento e chamada, 409 com o registro atual |
| Ciclo de vida e expiração de dados | API-07, API-10 — tokens de confirmação e de convite expiram (410) e são de uso único (409); token de renovação rotacionado |
| Observabilidade | API-01 — `correlacao` por requisição em toda resposta de erro, no log estruturado e no header `X-Correlacao` |
| Falha de dependência externa | API-13 — o serviço de e-mail falha sem derrubar a requisição de negócio; a mensagem fica registrada para reenvio |
| Integridade de transição de estado | API-15, API-21, API-22 — solicitação só decide se `pendente`; critério com notas não é excluído (409); publicar exige `aprovado` (409) e checklist completo (422) |

---

## User Stories

### P1: Fundação HTTP — envelope, formato e correlação ⭐ MVP

**User Story**: Como desenvolvedor do front, quero que toda resposta da API tenha exatamente a
forma que o cliente HTTP já sabe interpretar, para que nenhuma tela precise de tratamento especial.

**Why P1**: `normalizarErro` do front assume esse envelope em toda chamada. Sem ele, todo erro
vira tela branca.

**Acceptance Criteria**:

1. WHEN qualquer endpoint responde com status ≥ 400 THEN a API SHALL devolver um corpo JSON com as
   chaves `codigo` (string), `mensagem` (string) e `correlacao` (string), e `campos` apenas quando
   houver erro por campo.
2. WHEN uma validação de corpo falha THEN a API SHALL responder 422 com `codigo: "dados_invalidos"`
   e `campos` mapeando o nome do campo **em camelCase** para a mensagem em pt-BR.
3. WHEN qualquer requisição é processada THEN a API SHALL gerar um identificador de correlação
   único, devolvê-lo no header `X-Correlacao` e repeti-lo no campo `correlacao` de resposta de erro.
4. WHEN um recurso é serializado THEN todo campo SHALL sair em camelCase e todo identificador
   SHALL ser uma string, mesmo sendo UUID no banco.
5. WHEN uma exceção não tratada ocorre THEN a API SHALL responder 500 com o mesmo envelope,
   `codigo: "erro_interno"`, sem vazar stack trace no corpo, e registrar a stack no log com a
   mesma correlação.
6. WHEN um endpoint recebe corpo que não é JSON válido THEN a API SHALL responder 400 com
   `codigo: "corpo_invalido"`.

**Independent Test**: chamar um endpoint qualquer com corpo inválido e verificar as quatro chaves
do envelope e o header `X-Correlacao`.

---

### P1: Modelagem versionada em UUID ⭐ MVP

**User Story**: Como desenvolvedor do time, quero que o schema evolua por migration versionada,
para que meu banco local acompanhe as mudanças sem eu perder os dados.

**Why P1**: Toda outra história escreve em tabelas que ainda não existem.

**Acceptance Criteria**:

1. WHEN a aplicação sobe THEN as migrations Alembic SHALL ser aplicadas antes de a API aceitar
   requisição.
2. WHEN uma entidade é criada THEN sua chave primária SHALL ser um UUID v4 gerado pelo banco.
3. WHEN `flask db upgrade` roda num banco já migrado THEN a operação SHALL ser idempotente e não
   alterar dado nenhum.
4. WHEN o schema muda THEN `init-scripts/01-schema.sql` SHALL ter sido removido, para não haver
   duas fontes de verdade sobre a estrutura do banco.

**Independent Test**: subir o compose duas vezes com volume preservado e verificar que os dados
sobrevivem e nenhuma migration é reaplicada.

---

### P1: Login e emissão de sessão ⭐ MVP

**User Story**: Como usuário cadastrado, quero entrar no sistema, para acessar minhas telas.

**Why P1**: Nenhuma outra rota autenticada funciona sem isto.

**Acceptance Criteria**:

1. WHEN `POST /api/auth/login` recebe e-mail e senha corretos de conta ativa e confirmada THEN a
   API SHALL responder 200 com `{ tokenDeAcesso, usuario }`, onde `usuario` tem `id`, `nome`,
   `email`, `emailConfirmado`, `administrador` e `ativo`, e nunca a senha nem seu hash.
2. WHEN o e-mail não existe OU a senha está errada THEN a API SHALL responder 401 com
   `codigo: "credenciais_invalidas"` e a **mesma** mensagem nos dois casos.
3. WHEN a conta existe mas está inativa THEN a API SHALL responder 403 com
   `codigo: "conta_desativada"`.
4. WHEN a conta existe, está ativa, mas o e-mail não foi confirmado THEN a API SHALL responder 403
   com `codigo: "email_nao_confirmado"`.
5. WHEN o login tem sucesso THEN a API SHALL emitir um cookie de renovação `HttpOnly`, `SameSite=Lax`,
   `Path=/api/auth`, com `Secure` ligado quando a variável de ambiente indicar produção.
6. WHEN a senha é verificada THEN a comparação SHALL usar bcrypt sobre o hash armazenado, nunca o
   texto puro.

**Independent Test**: quatro chamadas de login (correta, senha errada, conta inativa, e-mail não
confirmado) conferindo status, `codigo` e presença do cookie.

---

### P1: Renovação silenciosa e logout ⭐ MVP

**User Story**: Como usuário, quero continuar navegando sem ser deslogado a cada 15 minutos.

**Why P1**: O cliente do front renova automaticamente em 401; sem o endpoint, toda sessão morre no
primeiro token expirado.

**Acceptance Criteria**:

1. WHEN `POST /api/auth/refresh` recebe um cookie de renovação válido THEN a API SHALL responder
   200 com `{ tokenDeAcesso }` e emitir um cookie de renovação novo, invalidando o anterior.
2. WHEN o cookie de renovação está ausente, expirado ou já foi rotacionado THEN a API SHALL
   responder 401 com `codigo: "nao_autenticado"` e limpar o cookie.
3. WHEN um token de renovação **já rotacionado** é reapresentado THEN a API SHALL invalidar toda a
   família de tokens daquela sessão e responder 401 — reuso é sinal de roubo.
4. WHEN `POST /api/auth/logout` é chamado THEN a API SHALL responder **204 sem corpo**, invalidar o
   token de renovação e limpar o cookie.
5. WHEN `POST /api/auth/logout` é chamado sem sessão válida THEN a API SHALL ainda responder 204 —
   sair é idempotente.
6. WHEN um token de acesso expirado é usado em rota autenticada THEN a API SHALL responder 401 com
   `codigo: "nao_autenticado"`.

**Independent Test**: renovar, usar o token novo, reapresentar o cookie antigo e verificar o 401 de
reuso.

---

### P1: Autocadastro ⭐ MVP

**User Story**: Como pesquisador sem conta, quero me cadastrar, para poder submeter e participar.

**Why P1**: Porta de entrada de todo autor externo.

**Acceptance Criteria**:

1. WHEN `POST /api/usuarios` recebe `nome`, `email`, `senha`, `instituicao` e `pais` válidos THEN a
   API SHALL responder **201** com `{ id, email }`, criar a conta com `emailConfirmado: false` e
   `ativo: true`, e disparar o e-mail de confirmação.
2. WHEN o e-mail já pertence a uma conta THEN a API SHALL responder 409 com
   `codigo: "email_existente"`.
3. WHEN `instituicao` vem vazia ou ausente THEN a API SHALL responder 422 com `campos.instituicao`
   preenchido.
4. WHEN a senha tem menos de 8 caracteres THEN a API SHALL responder 422 com `campos.senha`
   preenchido.
5. WHEN a conta é criada THEN a senha SHALL ser gravada apenas como hash bcrypt.
6. WHEN a resposta de criação é montada THEN ela SHALL conter **somente** `id` e `email` — nunca o
   objeto de usuário completo, porque a conta ainda não está confirmada.

**Independent Test**: cadastrar, conferir 201 com duas chaves, e verificar que o login subsequente
falha com 403 `email_nao_confirmado`.

---

### P1: Confirmação de e-mail e reenvio ⭐ MVP

**User Story**: Como pessoa que acabou de se cadastrar, quero confirmar meu e-mail pelo link
recebido, para conseguir entrar.

**Why P1**: Sem confirmar, o login é bloqueado por API-04 AC4.

**Acceptance Criteria**:

1. WHEN `POST /api/auth/confirmar-email` recebe um token pendente e não expirado THEN a API SHALL
   responder 200 com `{ email }`, marcar a conta como `emailConfirmado: true` e o token como usado.
2. WHEN o token não existe THEN a API SHALL responder 404 com `codigo: "token_invalido"`.
3. WHEN o token está expirado THEN a API SHALL responder 410 com `codigo: "token_expirado"`.
4. WHEN o token já foi usado THEN a API SHALL responder 409 com `codigo: "token_ja_usado"`.
5. WHEN `POST /api/auth/reenviar-confirmacao` é chamado THEN a API SHALL responder 200 com
   `{ esperarSegundos }` cujo valor **não depende de a conta existir** — a janela de reenvio é
   registrada **por e-mail**, exista ou não conta para ele, para o endpoint não virar um
   verificador de e-mails cadastrados.
6. WHEN um reenvio ocorre menos de 60 segundos após o anterior para o mesmo e-mail THEN a API SHALL
   responder 200 com `{ esperarSegundos }` refletindo o tempo restante e **não** enviar novo e-mail.
7. WHEN dois pedidos são feitos para um e-mail **cadastrado** e dois para um **não cadastrado**,
   com o mesmo intervalo entre eles THEN as duas sequências de resposta SHALL ser idênticas par a
   par — status, corpo e valor de `esperarSegundos`. Esta AC existe porque AC5 e AC6, na redação
   anterior, se anulavam: registrar a janela só para contas existentes fazia a contagem regressiva
   decrescer apenas para elas, entregando um oráculo de enumeração de contas.
8. WHEN um pedido de reenvio é registrado THEN o banco SHALL guardar **apenas o SHA-256** do
   e-mail normalizado, e registros com janela vencida SHALL ser removidos.
9. WHEN um token de confirmação é emitido THEN ele SHALL expirar em 24 horas.

**Independent Test**: confirmar com token válido, repetir a chamada e obter 409.

---

### P1: Identidade e participações do usuário autenticado ⭐ MVP

**User Story**: Como usuário logado, quero que o sistema saiba quem eu sou e em quais eventos atuo,
para me mostrar o menu e o seletor de evento corretos.

**Why P1**: `SessaoProvider` e `EventoProvider` do front chamam essas duas rotas no boot; sem elas
o app não passa da tela de carregamento.

**Acceptance Criteria**:

1. WHEN `GET /api/me` recebe token de acesso válido THEN a API SHALL responder 200 com o objeto de
   usuário **diretamente na raiz** (não envolto em `{ user: ... }`), com `id`, `nome`, `email`,
   `emailConfirmado`, `administrador` e `ativo`.
2. WHEN `GET /api/me` é chamado sem token ou com token inválido THEN a API SHALL responder 401 com
   `codigo: "nao_autenticado"`.
3. WHEN `GET /api/me/participacoes` recebe token válido THEN a API SHALL responder 200 com uma lista
   de objetos `{ eventoId, eventoTitulo, identificadorPagina, papeis }`, onde `papeis` é uma lista
   com valores em `chair | avaliador | responsavel_etapa`.
4. WHEN o usuário tem mais de um papel no mesmo evento THEN a API SHALL devolver **uma única
   entrada** para o evento, com os papéis agregados na lista.
5. WHEN o usuário não participa de evento nenhum THEN a API SHALL responder 200 com lista vazia,
   nunca 404.
6. WHEN uma participação está inativa THEN ela SHALL ser omitida da lista.

**Independent Test**: criar usuário com dois papéis no mesmo evento e verificar uma entrada com
dois papéis.

---

### P1: Convite por token, sem sessão ⭐ MVP

**User Story**: Como pessoa convidada por e-mail sem ter conta, quero abrir o link do convite e
aceitar, para participar sem cadastro prévio.

**Why P1**: É como o chair inicial de um evento aprovado entra no sistema (AD-009).

**Acceptance Criteria**:

1. WHEN `GET /api/convites/{token}` recebe um token pendente THEN a API SHALL responder 200 com
   `{ tipo, email, eventoTitulo, submissaoTitulo?, prazo, fuso, contatoDaOrganizacao, precisaCriarConta }`,
   **sem exigir sessão**, onde `tipo` é `avaliacao` ou `participacao` (D3).
2. WHEN o token não existe THEN a API SHALL responder 404 com `codigo: "convite_invalido"` e o
   campo **`contatoDaOrganizacao`** no corpo do erro, ao lado de `codigo`/`mensagem`/`correlacao`
   — nunca dentro de `campos`, que significa erro por campo de formulário (D4).
3. WHEN o convite expirou THEN a API SHALL responder 410 com `codigo: "convite_expirado"` e
   `contatoDaOrganizacao` no corpo (D4).
4. WHEN o convite já foi aceito THEN a API SHALL responder 409 com `codigo: "convite_ja_usado"` e
   `contatoDaOrganizacao` no corpo (D4).
5. WHEN o e-mail do convite ainda não tem conta THEN `precisaCriarConta` SHALL ser `true`.
6. WHEN o convite é de `tipo: "participacao"` THEN `submissaoTitulo` SHALL estar **ausente** da
   resposta — convite de chair não tem submissão associada; e WHEN é de `tipo: "avaliacao"` THEN
   `submissaoTitulo` SHALL estar presente e não vazio (D3).
7. WHEN `POST /api/convites/{token}/aceitar` recebe `nome` e `senha` para um convite pendente cujo
   e-mail não tem conta THEN a API SHALL criar a conta com `emailConfirmado: true` — quem abriu o
   link provou o endereço — marcar o convite como aceito, criar a participação correspondente e
   responder 200 com `{ tokenDeAcesso, usuario }` mais o cookie de renovação.
8. WHEN o e-mail do convite já tem conta THEN o aceite SHALL apenas criar a participação e abrir a
   sessão, sem alterar nome ou senha da conta existente.
9. WHEN um convite já aceito é aceito de novo THEN a API SHALL responder 409 com
   `codigo: "convite_ja_usado"` e `contatoDaOrganizacao` no corpo.

**Independent Test**: aceitar um convite de e-mail sem conta e verificar que o login direto passa a
funcionar com a senha informada.

---

### P1: Autorização por papel no evento ⭐ MVP

**User Story**: Como organizador, quero que ninguém de fora consiga editar meu evento, mesmo tendo
uma conta no sistema.

**Why P1**: Sem isto, todo endpoint de gestão é público para qualquer usuário logado (AD-008).

**Acceptance Criteria**:

1. WHEN uma rota de gestão de evento (`PATCH /eventos/{id}`, trilhas, chamadas, critérios,
   publicar) é chamada por usuário **sem** participação de `chair` ativa naquele evento THEN a API
   SHALL responder 403 com `codigo: "sem_permissao"`.
2. WHEN uma rota `/api/admin/*` é chamada por usuário com `administrador: false` THEN a API SHALL
   responder 403 com `codigo: "sem_permissao"`.
3. WHEN uma rota autenticada é chamada sem token THEN a API SHALL responder 401 — **não** 403; a
   distinção entre "não sei quem é você" e "sei, e você não pode" SHALL ser preservada.
4. WHEN um usuário com `administrador: true` chama uma rota de gestão de qualquer evento THEN a API
   SHALL permitir.
5. WHEN uma rota é chamada para um recurso que não existe por um usuário que também não teria
   permissão THEN a API SHALL responder 403 antes de 404, para não revelar a existência do recurso.
6. WHEN `PATCH /solicitacoes-evento/{id}` é chamado por usuário que não é o solicitante THEN a API
   SHALL responder 403.

**Independent Test**: dois usuários, um chair e um estranho; o estranho recebe 403 em cada rota de
gestão.

---

### P1: Serviço de e-mail com backend trocável ⭐ MVP

**User Story**: Como desenvolvedor, quero ver o link de confirmação sem servidor de e-mail
configurado, para conseguir testar o fluxo completo localmente.

**Why P1**: Confirmação de e-mail e convite de chair só fecham se o token chegar a alguém.

**Acceptance Criteria**:

1. WHEN a variável de ambiente seleciona o backend de log THEN todo e-mail SHALL ser gravado em
   `emails_enviados` (destinatário, assunto, corpo, situação, criado em) e emitido no log da
   aplicação, sem tentativa de rede.
2. WHEN o backend de e-mail falha THEN a requisição de negócio SHALL concluir normalmente e a
   mensagem SHALL ficar registrada com situação `falha`, sem desfazer o cadastro nem a aprovação.
3. WHEN um e-mail de confirmação é gerado THEN o corpo SHALL conter a URL completa de confirmação
   com o token, montada a partir da variável de ambiente da origem do front.
4. WHEN a variável de ambiente seleciona SMTP mas falta configuração obrigatória THEN a aplicação
   SHALL falhar no boot com mensagem explícita, nunca silenciosamente cair no backend de log.

**Independent Test**: cadastrar um usuário e ler o token direto de `emails_enviados`.

---

### P1: Solicitação de criação de evento ⭐ MVP

**User Story**: Como organizador, quero solicitar a criação de um evento, para que o administrador
aprove.

**Why P1**: É a entrada de todo evento no sistema.

**Acceptance Criteria**:

1. WHEN `POST /api/solicitacoes-evento` recebe corpo válido de usuário autenticado THEN a API SHALL
   responder **201** com a solicitação completa, incluindo `id`, `solicitanteId`,
   `situacao: "pendente"`, `criadoEm` e `versao: 1`.
2. WHEN o `identificadorPagina` enviado já existe em outra solicitação **ou** em um evento THEN a
   API SHALL responder 422 com `campos.identificadorPagina` preenchido.
3. WHEN `titulo`, `identificadorPagina`, `dataInicio` ou `dataTermino` estão ausentes ou vazios
   THEN a API SHALL responder 422 com o campo faltante em `campos`.
4. WHEN `dataTermino` é anterior a `dataInicio` THEN a API SHALL responder 422 com
   `campos.dataTermino` preenchido.
5. WHEN `eventoPaiId` aponta para um evento que é descendente do evento sendo criado THEN a API
   SHALL responder 422 com `campos.eventoPaiId` preenchido — hierarquia não admite ciclo.
6. WHEN `PATCH /api/solicitacoes-evento/{id}` é chamado numa solicitação `pendente` pelo próprio
   solicitante THEN a API SHALL aplicar as alterações, incrementar `versao` e responder 200.
7. WHEN `PATCH /api/solicitacoes-evento/{id}` é chamado numa solicitação já decidida THEN a API
   SHALL responder 409 com `codigo: "solicitacao_ja_decidida"`.
8. WHEN `GET /api/me/solicitacoes-evento` é chamado THEN a API SHALL responder 200 com apenas as
   solicitações do próprio usuário.

**Independent Test**: criar duas solicitações com o mesmo identificador e ver a segunda falhar em
422.

---

### P1: Fila e decisão do administrador ⭐ MVP

**User Story**: Como administrador, quero ver as solicitações pendentes e aprovar ou recusar, para
controlar o que entra no sistema.

**Why P1**: Nenhum evento existe sem passar por aqui.

**Acceptance Criteria**:

1. WHEN `GET /api/admin/solicitacoes-evento` é chamado por administrador THEN a API SHALL responder
   200 com todas as solicitações **ordenadas por `criadoEm` crescente**.
2. WHEN o parâmetro `status` é informado THEN a lista SHALL conter apenas solicitações naquela
   situação; sem o parâmetro, SHALL conter todas.
3. WHEN `POST /api/admin/solicitacoes-evento/{id}/aprovar` é chamado numa solicitação pendente THEN
   a API SHALL responder 200 com `{ solicitacao, evento }`, marcando a solicitação como `aprovada`
   com `decididoPorId` e `decididoEm`, e criando o evento com `situacao: "aprovado"`.
4. WHEN um evento nasce da aprovação THEN seus parâmetros de avaliação SHALL ter os padrões
   `modeloDeAvaliacao: "aberta"`, `avaliadoresPorSubmissao: 1`, `rebuttalHabilitado: false`,
   `maximoDeRodadas: 1` e `versao: 1`.
5. WHEN `POST .../recusar` recebe `motivo` não vazio numa solicitação pendente THEN a API SHALL
   responder 200 com a solicitação `recusada`, `motivoRecusa`, `decididoPorId` e `decididoEm`.
6. WHEN `POST .../recusar` recebe `motivo` ausente ou vazio THEN a API SHALL responder 422 com
   `campos.motivo` preenchido.
7. WHEN aprovar ou recusar é chamado numa solicitação **já decidida** THEN a API SHALL responder
   409 com um corpo que, além de `codigo`, `mensagem` e `correlacao`, carrega `decididoPorId`,
   `decididoEm` e `situacao` — para a tela dizer quem decidiu e quando.
8. WHEN a solicitação não existe THEN a API SHALL responder 404 com
   `codigo: "solicitacao_inexistente"`.

**Independent Test**: aprovar duas vezes a mesma solicitação e conferir que o segundo 409 traz
`decididoPorId`.

---

### P1: Efeitos da aprovação — participações e convites ⭐ MVP

**User Story**: Como organizador cuja solicitação foi aprovada, quero já poder gerir o evento e ver
minha equipe convidada, sem pedir nada ao administrador.

**Why P1**: Sem isto `GET /me/participacoes` volta vazio e a navegação do app não fecha (AD-009).

**Acceptance Criteria**:

1. WHEN uma solicitação é aprovada THEN a API SHALL criar uma participação ativa de papel `chair`
   para o **solicitante** no evento criado.
2. WHEN a solicitação tem `chairsIniciais` cujo e-mail já pertence a uma conta THEN a API SHALL
   criar participação ativa de papel `chair` para cada uma dessas contas.
3. WHEN a solicitação tem `chairsIniciais` cujo e-mail **não** pertence a nenhuma conta THEN a API
   SHALL criar um convite pendente com token e `tipo: "participacao"` — sem `submissaoTitulo`
   (D3) — para cada um, e disparar o e-mail correspondente.
4. WHEN a aprovação falha em qualquer etapa THEN nenhum efeito SHALL persistir — solicitação,
   evento, participações e convites são gravados na **mesma transação**.
5. WHEN o envio de um e-mail de convite falha THEN a aprovação SHALL permanecer válida e o e-mail
   SHALL ficar registrado com situação `falha` (API-13 AC2).
6. WHEN o mesmo e-mail aparece duas vezes em `chairsIniciais` THEN apenas uma participação ou
   convite SHALL ser criado.

**Independent Test**: aprovar solicitação com um chair com conta e um sem, e conferir uma
participação e um convite.

---

### P1: Leitura, edição e concorrência do evento ⭐ MVP

**User Story**: Como chair, quero configurar identidade e parâmetros de avaliação do meu evento,
sem sobrescrever a edição de outro chair.

**Why P1**: É a tela central da área de gestão.

**Acceptance Criteria**:

1. WHEN `GET /api/eventos/{id}` é chamado THEN a API SHALL responder 200 com o evento completo, ou
   404 com `codigo: "evento_inexistente"`.
2. WHEN `GET /api/eventos/por-identificador/{identificadorPagina}` é chamado THEN a API SHALL
   resolver o evento pelo identificador de página **sem exigir participação**, ou 404.
3. WHEN `PATCH /api/eventos/{id}` recebe `versao` **igual** à versão atual THEN a API SHALL aplicar
   as alterações, incrementar `versao` em 1 e responder 200 com o evento atualizado.
4. WHEN `PATCH /api/eventos/{id}` recebe `versao` **diferente** da atual THEN a API SHALL responder
   409 com `codigo: "conflito_de_versao"` no envelope padrão e o registro atual completo no campo
   **`atual`**, para a tela oferecer recarregar (D2).
5. WHEN `avaliadoresPorSubmissao` não é inteiro ≥ 1 THEN a API SHALL responder 422 com
   `campos.avaliadoresPorSubmissao` preenchido.
6. WHEN `rebuttalHabilitado` é verdadeiro e `prazoRebuttalDias` está ausente THEN a API SHALL
   responder 422 com `campos.prazoRebuttalDias` preenchido.
7. WHEN `maximoDeRodadas` não é inteiro ≥ 1 THEN a API SHALL responder 422 com
   `campos.maximoDeRodadas` preenchido.
8. WHEN `GET /api/eventos/{id}/descendentes` é chamado THEN a API SHALL responder 200 com
   `{ descendentes: [...] }` contendo os ids de **toda a árvore** abaixo do evento — filhos, netos
   e além.

**Independent Test**: dois PATCH com a mesma `versao`; o segundo devolve 409 com o evento atual.

---

### P1: Trilhas ⭐ MVP

**User Story**: Como chair, quero organizar meu evento em trilhas.

**Why P1**: A chamada referencia trilha; sem trilhas a configuração não fecha.

**Acceptance Criteria**:

1. WHEN `GET /api/eventos/{id}/trilhas` é chamado THEN a API SHALL responder 200 com as trilhas do
   evento, cada uma com `id`, `eventoId`, `nome`, `descricao`, `ativa` e `submissoesVinculadas`.
2. WHEN `POST /api/eventos/{id}/trilhas` recebe `nome` não vazio THEN a API SHALL responder 201 com
   a trilha criada, `ativa: true` por padrão e `submissoesVinculadas: 0`.
3. WHEN `nome` vem vazio THEN a API SHALL responder 422 com `campos.nome` preenchido.
4. WHEN `PATCH /api/trilhas/{id}` é chamado THEN a API SHALL aplicar as alterações e responder 200
   com a trilha, incluindo `submissoesVinculadas` atualizado.
5. WHEN uma trilha com submissões vinculadas é desativada THEN a API SHALL **permitir** e devolver
   a contagem — o aviso é responsabilidade da tela, não um bloqueio.
6. WHEN a trilha não existe THEN a API SHALL responder 404 com `codigo: "trilha_inexistente"`.
7. WHEN duas trilhas do mesmo evento recebem o mesmo `nome` THEN a API SHALL responder 422 com
   `campos.nome` preenchido.

**Independent Test**: criar trilha, desativá-la e verificar 200 com a contagem.

---

### P1: Chamadas, prorrogação e encerramento ⭐ MVP

**User Story**: Como chair, quero abrir uma chamada com prazo e poder prorrogá-la ou encerrá-la.

**Why P1**: A submissão inteira depende de uma chamada com prazo.

**Acceptance Criteria**:

1. WHEN `GET /api/eventos/{id}/chamadas` é chamado THEN a API SHALL responder 200 com as chamadas
   do evento.
2. WHEN `POST /api/eventos/{id}/chamadas` recebe corpo válido THEN a API SHALL responder 201 com a
   chamada criada, `encerradaManualmente: false` e `versao: 1`.
3. WHEN `dataLimite` é menor ou igual a `dataAbertura` THEN a API SHALL responder 422 com
   `campos.dataLimite` preenchido — na criação e na edição.
4. WHEN `PATCH /api/chamadas/{id}` recebe `versao` diferente da atual THEN a API SHALL responder
   409 com `codigo: "conflito_de_versao"` e a chamada atual completa em `atual` (D2).
5. WHEN `PATCH /api/chamadas/{id}` tem sucesso THEN a API SHALL incrementar `versao` em 1.
6. WHEN `POST /api/chamadas/{id}/prorrogar` recebe `dataLimite` posterior à vigente THEN a API
   SHALL atualizar o prazo, incrementar `versao` e responder 200.
7. WHEN a nova `dataLimite` da prorrogação é anterior ou igual à vigente, ou está ausente THEN a
   API SHALL responder 422 com `campos.dataLimite` preenchido — prorrogar nunca encurta prazo.
8. WHEN `POST /api/chamadas/{id}/encerrar` é chamado THEN a API SHALL marcar
   `encerradaManualmente: true`, incrementar `versao` e responder 200.
9. WHEN `tamanhoMaximoMb` excede o limite configurado do servidor THEN a API SHALL responder 422
   com `campos.tamanhoMaximoMb` preenchido.
10. WHEN a chamada não existe THEN a API SHALL responder 404 com `codigo: "chamada_inexistente"`.

**Independent Test**: prorrogar para uma data anterior à vigente e conferir o 422.

---

### P1: Critérios de avaliação ⭐ MVP

**User Story**: Como chair, quero definir os critérios pelos quais os avaliadores pontuam.

**Why P1**: Item obrigatório do checklist de publicação.

**Acceptance Criteria**:

1. WHEN `GET /api/eventos/{id}/criterios` é chamado THEN a API SHALL responder 200 com os critérios
   do evento, cada um com `notaMinima`, `notaMaxima`, `peso`, `ordem`, `ativo` e `temNotas`.
2. WHEN `POST /api/eventos/{id}/criterios` recebe corpo válido THEN a API SHALL responder 201 com o
   critério criado, `ativo: true` e `temNotas: false` por padrão.
3. WHEN `notaMaxima` é menor ou igual a `notaMinima` THEN a API SHALL responder 422 com
   `campos.notaMaxima` preenchido — na criação e na edição.
4. WHEN `peso` é menor ou igual a zero THEN a API SHALL responder 422 com `campos.peso` preenchido
   — na criação e na edição.
5. WHEN `DELETE /api/criterios/{id}` é chamado num critério **sem** notas THEN a API SHALL excluir
   e responder **204 sem corpo**.
6. WHEN `DELETE /api/criterios/{id}` é chamado num critério **com** notas registradas THEN a API
   SHALL responder 409 com `codigo: "criterio_com_notas"` e o campo extra
   `acaoSugerida: "desativar"`.
7. WHEN o critério não existe THEN a API SHALL responder 404 com `codigo: "criterio_inexistente"`.
8. WHEN `ordem` não é informada na criação THEN a API SHALL atribuir a próxima posição livre
   **dentro daquele evento**.

**Independent Test**: excluir critério sem notas (204) e com notas (409 com `acaoSugerida`).

---

### P1: Checklist de publicação e publicar ⭐ MVP

**User Story**: Como chair, quero saber exatamente o que falta antes de publicar meu evento.

**Why P1**: É o fecho da configuração e o gate para o evento existir publicamente.

**Acceptance Criteria**:

1. WHEN `GET /api/eventos/{id}/checklist-publicacao` é chamado THEN a API SHALL responder 200 com
   `{ temChamada, temCriterioAtivo, formularioDefinido, etapasDefinidas, eventoAprovado }`, todos
   booleanos.
2. WHEN o evento tem ao menos uma chamada THEN `temChamada` SHALL ser `true`; caso contrário
   `false`.
3. WHEN o evento tem ao menos um critério com `ativo: true` THEN `temCriterioAtivo` SHALL ser
   `true`; um critério inativo **não** conta.
4. WHEN existe ao menos um registro em `formularios_chamada` para alguma chamada do evento THEN
   `formularioDefinido` SHALL ser `true`; caso contrário `false` (AD-007).
5. WHEN existe ao menos um registro em `fases_evento` para o evento THEN `etapasDefinidas` SHALL
   ser `true`; caso contrário `false` (AD-007).
6. WHEN a situação do evento é `aprovado` ou `publicado` THEN `eventoAprovado` SHALL ser `true`.
7. WHEN `POST /api/eventos/{id}/publicar` é chamado com o evento **não** em situação `aprovado`
   THEN a API SHALL responder 409 com `codigo: "evento_nao_aprovado"`.
8. WHEN o checklist tem algum item diferente de `eventoAprovado` em `false` THEN a API SHALL
   responder 422 com `codigo: "checklist_incompleto"` e `campos` contendo **uma chave por item
   faltante**, nomeada com o próprio nome do item.
9. WHEN o corpo traz `versao` diferente da atual THEN a API SHALL responder 409 com
   `codigo: "conflito_de_versao"` e o evento atual completo em `atual` (D2).
10. WHEN tudo está satisfeito THEN a API SHALL mudar a situação para `publicado`, incrementar
    `versao` e responder 200 com o evento.

**Independent Test**: publicar um evento sem critério ativo e conferir `campos.temCriterioAtivo` no
422.

---

### P2: Vitrine pública e meus eventos

**User Story**: Como visitante, quero ver os eventos existentes sem estar logado; como participante,
quero ver apenas os meus.

**Why P2**: São duas telas reais do front hoje ligadas a handlers de casca; a área de gestão
funciona sem elas.

**Acceptance Criteria**:

1. WHEN `GET /api/eventos` é chamado **sem sessão** THEN a API SHALL responder 200 com os eventos
   publicados, cada um com `{ id, titulo, site, cidade, estado, pais, dataInicio, dataTermino,
   encerrado, subEventos }` — dados estruturados, nunca texto de apresentação já formatado (D1).
2. WHEN um evento não está publicado THEN ele SHALL ser omitido da vitrine pública.
3. WHEN a resposta é montada THEN a API SHALL **não** devolver `local` nem `periodo`: compor local
   e período legíveis é trabalho do front, que precisa dos dados brutos para formatar no fuso do
   evento e ordenar por data (D1).
4. WHEN um evento tem eventos filhos publicados THEN `subEventos` SHALL listá-los.
5. WHEN `GET /api/me/eventos` é chamado com sessão válida THEN a API SHALL responder 200 com os
   eventos em que o usuário tem participação ativa, no mesmo formato da vitrine.
6. WHEN `GET /api/me/eventos` é chamado sem sessão THEN a API SHALL responder 401.

**Independent Test**: chamar `/api/eventos` sem header de autorização e receber 200.

---

### P2: Limite de tentativas de login

**User Story**: Como responsável pelo sistema, quero que tentativas repetidas de senha sejam
freadas.

**Why P2**: O front já trata o 429, mas nenhuma tela depende dele para funcionar.

**Acceptance Criteria**:

1. WHEN mais de 10 tentativas de login falham para o mesmo e-mail em 15 minutos THEN a API SHALL
   responder 429 com `codigo: "muitas_tentativas"` e o header `Retry-After` em segundos.
2. WHEN um login tem sucesso THEN o contador de tentativas daquele e-mail SHALL ser zerado.
3. WHEN a janela de 15 minutos expira THEN o contador SHALL ser zerado.

**Independent Test**: 11 logins errados seguidos; o décimo primeiro devolve 429.

---

### P1: Execução local e integração com o front ⭐ MVP

**User Story**: Como desenvolvedor do time, quero subir API e front e ver as telas com dados reais.

**Why P1**: É a prova de que "só plugar as rotas" aconteceu.

**Acceptance Criteria**:

1. WHEN `docker-compose up` roda com um `.env` completo THEN a API SHALL subir em
   `http://localhost:5000` com as migrations aplicadas.
2. WHEN o front roda `npm run dev` THEN as chamadas a `/api/*` SHALL ser encaminhadas para a API
   por `server.proxy` do Vite, na mesma origem.
3. WHEN o front roda em modo de desenvolvimento contra a API real THEN o MSW SHALL poder ser
   desligado por variável de ambiente, sem alteração de código.
4. WHEN falta uma variável de ambiente obrigatória THEN a aplicação SHALL falhar no boot com
   mensagem nomeando a variável.
5. WHEN o repositório é clonado THEN um `.env.example` SHALL listar todas as variáveis exigidas.

**Independent Test**: subir os dois, fazer login pela tela real e ver o menu montado a partir de
`/api/me/participacoes`.

---

### P1: Suíte de testes contra Postgres real ⭐ MVP

**User Story**: Como responsável pela qualidade, quero que cada tarefa tenha um gate que rode
contra o banco de verdade.

**Why P1**: É o gate de todas as outras histórias (AD-012).

**Acceptance Criteria**:

1. WHEN a suíte roda THEN ela SHALL conectar a um database `sgs_test` separado do de
   desenvolvimento, criado e migrado por fixture.
2. WHEN um teste termina THEN sua transação SHALL sofrer rollback, de modo que nenhum teste
   enxergue o que outro escreveu.
3. WHEN a suíte é executada THEN cada endpoint do contrato SHALL ter ao menos um teste de caminho
   feliz e um de erro, exercitando a API pelo cliente HTTP do Flask, não chamando o service direto.
4. WHEN um teste falha THEN o comando SHALL sair com código diferente de zero — o gate é o código
   de saída, não a contagem de testes verdes.

**Independent Test**: rodar a suíte duas vezes seguidas e obter o mesmo resultado, sem limpeza
manual.

---

### P1: Adequação do front às divergências aceitas ⭐ MVP

**User Story**: Como responsável pelo projeto, quero que o front acompanhe as quatro mudanças de
contrato no mesmo ciclo, para que os dois lados nunca fiquem incompatíveis.

**Why P1**: D3 é pré-requisito de API-13; as outras três, aplicadas só de um lado, quebram telas
na integração (AD-015).

**Acceptance Criteria**:

1. WHEN os handlers MSW do front são atualizados THEN eles SHALL refletir exatamente as quatro
   divergências, permanecendo a referência executável do contrato para os testes do front.
2. WHEN `EventosPublicos.tsx` e `MinhasParticipacoes.tsx` recebem os dados estruturados de D1 THEN
   eles SHALL compor local e período na própria camada de apresentação, exibindo o mesmo texto de
   antes.
3. WHEN uma resposta 409 de conflito de versão chega THEN `evento.ts`, `chamadas.ts` e
   `publicacao.ts` SHALL ler o registro atual de `atual` no erro normalizado, e o comportamento
   de "recarregar" observável pelo usuário SHALL permanecer idêntico.
4. WHEN `TelaDeConvite.tsx` recebe um convite de `tipo: "participacao"` THEN ela SHALL **não**
   exibir linha de título de submissão; e WHEN recebe `tipo: "avaliacao"` THEN SHALL exibi-la
   como antes.
5. WHEN `TelaDeConvite.tsx` trata erro de convite THEN ela SHALL ler `contatoDaOrganizacao` do
   corpo do erro, e o contato exibido SHALL ser o mesmo de antes.
6. WHEN as alterações estão completas THEN `npm run gate` no repositório do front SHALL sair com
   código 0 — nenhum dos 1302 testes existentes SHALL ser enfraquecido, pulado ou removido para
   isso; testes que afirmavam o formato antigo SHALL ser reescritos para afirmar o novo.

**Independent Test**: rodar `npm run gate` no front após as alterações e obter saída 0.

---

## Edge Cases

- WHEN o token de acesso é válido mas a conta foi desativada depois de emitido THEN a API SHALL
  responder 401 com `codigo: "nao_autenticado"` — a checagem de `ativo` acontece a cada requisição,
  não só no login.
- WHEN dois cadastros com o mesmo e-mail chegam simultaneamente THEN a constraint única do banco
  SHALL fazer o segundo falhar, e a API SHALL traduzir o erro de integridade para 409
  `email_existente`, não 500.
- WHEN duas aprovações da mesma solicitação chegam simultaneamente THEN apenas uma SHALL criar
  evento; a outra SHALL receber 409 `solicitacao_ja_decidida`.
- WHEN `identificadorPagina` é alterado num evento já publicado THEN a API SHALL responder 422 com
  `campos.identificadorPagina` — links públicos já divulgados não podem quebrar.
- WHEN o fuso do evento é alterado com chamadas já criadas THEN os prazos armazenados SHALL
  permanecer inalterados no instante absoluto; apenas a exibição muda.
- WHEN o corpo de uma requisição excede o limite configurado THEN a API SHALL responder 413 com o
  envelope de erro, sem carregar o corpo inteiro em memória.
- WHEN `GET /api/eventos/{id}/descendentes` encontra um ciclo em dados legados THEN a travessia
  SHALL terminar sem recursão infinita, visitando cada evento uma única vez.
- WHEN um convite é aceito por alguém já logado com **outra** conta THEN a API SHALL vincular o
  convite ao e-mail do convite, não à sessão em curso.
- WHEN uma solicitação é aprovada e o solicitante já tem participação de chair naquele evento
  (reprocessamento) THEN nenhuma participação duplicada SHALL ser criada.

---

## Requirement Traceability

| ID | História | Front | Fase | Status |
| -- | -------- | ----- | ---- | ------ |
| API-01 | P1: Fundação HTTP — envelope, formato e correlação | BASE-09, BASE-11 | Specify | Pending |
| API-02 | P1: Modelagem versionada em UUID | — (infra) | Specify | Pending |
| API-03 | P1: Login e emissão de sessão | BASE-01 | Specify | Pending |
| API-04 | P1: Renovação silenciosa e logout | BASE-01 | Specify | Pending |
| API-05 | P1: Autocadastro | BASE-02 | Specify | Pending |
| API-06 | P1: Confirmação de e-mail e reenvio | BASE-02 | Specify | Pending |
| API-07 | P1: Identidade e participações do usuário | BASE-04, BASE-05 | Specify | Pending |
| API-08 | P1: Convite por token, sem sessão | BASE-08 | Specify | Pending |
| API-09 | P1: Autorização por papel no evento | BASE-05, §8.2 | Specify | Pending |
| API-10 | P1: Serviço de e-mail com backend trocável | BASE-02, §8.4 | Specify | Pending |
| API-11 | P1: Solicitação de criação de evento | EVT-01 | Specify | Pending |
| API-12 | P1: Fila e decisão do administrador | EVT-02, EVT-03 | Specify | Pending |
| API-13 | P1: Efeitos da aprovação — participações e convites | EVT-02, BASE-04 | Specify | Pending |
| API-14 | P1: Leitura, edição e concorrência do evento | EVT-04, EVT-05, EVT-10, EVT-14 | Specify | Pending |
| API-15 | P1: Trilhas | EVT-06 | Specify | Pending |
| API-16 | P1: Chamadas, prorrogação e encerramento | EVT-07 | Specify | Pending |
| API-17 | P1: Critérios de avaliação | EVT-08 | Specify | Pending |
| API-18 | P1: Checklist de publicação e publicar | EVT-11 | Specify | Pending |
| API-19 | P2: Vitrine pública e meus eventos | EVT-13, FID-09 | — | Pending |
| API-20 | P2: Limite de tentativas de login | BASE-01 | — | Pending |
| API-21 | P1: Execução local e integração com o front | — (infra) | Specify | Pending |
| API-22 | P1: Suíte de testes contra Postgres real | — (infra) | Specify | Pending |
| API-23 | P1: Adequação do front às divergências aceitas | D1–D4 (AD-014, AD-015) | Specify | Pending |

**Cobertura:** 23 requisitos (21 P1, 2 P2), 0 mapeados em tarefas (fase Specify).

**Rastreio ao documento V2 do front:** RN01–RN16, RN24, RN39, RN40, RN46, RF01.1–RF01.4,
RF02.1–RF02.5, RF03.1–RF03.4, §3.7, §8.2, §8.4.

---

## Success Criteria

- [ ] Desligar o MSW no front e a aplicação continuar funcionando em login, seletor de evento,
      menu por papel, solicitação de evento, fila do administrador e configuração completa do
      evento — sem alterar código de tela.
- [ ] Um percurso completo (cadastro → confirmação → login → solicitar → aprovar → trilha →
      chamada → critério → publicar) roda contra Postgres real como teste automatizado.
- [ ] Nenhuma rota de gestão responde 200 para usuário sem o papel exigido — verificado por teste
      em cada rota.
- [ ] Nenhuma resposta de erro sai fora do envelope `{ codigo, mensagem, campos?, correlacao }` —
      verificado por teste que varre todos os endpoints.
- [ ] `pytest` sai com código 0 e cada endpoint do contrato tem caminho feliz e caminho de erro.
- [ ] `npm run gate` no repositório do front sai com código 0 após as quatro divergências, sem
      nenhum teste enfraquecido ou removido.
