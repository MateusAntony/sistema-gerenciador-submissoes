# STATE

Projeto: **SGS — Sistema de Gestão de Submissões** (backend / API REST)
Repositório: `sistema-gerenciador-submissoes` · Front consumidor: `C:\Users\lucas\projeto-extensao`
Origem do contrato: `.specs/features/*/spec.md` (seções "Contrato de API consumido") e os
handlers MSW em `app/src/mocks/handlers/` do repositório do front.

## Decisions

### AD-001

- **Decision**: O contrato do front é o **ponto de partida**, não a autoridade. A forma da API é
  derivada dos handlers MSW do front (`app/src/mocks/handlers/`) — que valem sobre a tabela
  resumida de cada `spec.md` quando os dois divergem, por serem o que o código realmente
  exercita. Mas **onde a API tiver razão, a API muda e o front se adapta**: toda divergência
  proposta é registrada com justificativa, decidida explicitamente e comunicada ao front como
  mudança de contrato, nunca aplicada em silêncio.
- **Reason**: Seguir o contrato existente evita reescrever 1302 testes já verdes e cumpre o
  objetivo de "depois só plugar as rotas". Mas o contrato nasceu de mocks escritos sem servidor:
  alguns pontos codificam limitações do mock (ver AD-014) e congelá-los transformaria um artefato
  de teste em requisito permanente.
- **Trade-off**: Cada divergência custa uma alteração no repositório do front e a revisão dos
  testes que a tocam. Em compensação, a API não herda decisões que sabidamente não se sustentam.
- **Scope**: projeto
- **Date**: 2026-09-07
- **Status**: active

### AD-002

- **Decision**: Sessão por **JWT de acesso curto devolvido no corpo do login** + **token de
  renovação em cookie httpOnly**, renovado em `POST /api/auth/refresh`. Substitui a sessão por
  cookie do Flask (`session['user_id']`) implementada anteriormente.
- **Reason**: É o que o cliente HTTP do front já implementa — `cliente.ts` injeta
  `Authorization: Bearer`, enfileira renovações concorrentes e trata a perda de sessão. Manter
  sessão Flask exigiria reescrever o cliente e os testes de renovação, em código já verificado.
- **Trade-off**: Refatora ~80 linhas de código de outro desenvolvedor (José Victor) e adiciona
  dependência de JWT. O responsável assume o alinhamento com ele.
- **Scope**: toda a API
- **Date**: 2026-09-07
- **Status**: active

### AD-003

- **Decision**: Escopo desta rodada = **plataforma-base (BASE) + eventos-e-chamadas (EVT)**,
  34 endpoints. FORM, FASE, SUB, AVAL, DEC e ACOMP ficam para rodadas seguintes.
- **Reason**: São as duas áreas do front já implementadas e verificadas cujo consumo é imediato;
  entregam a navegação completa do app (login → participações → gestão do evento).
- **Trade-off**: `GET /eventos/{id}/checklist-publicacao` precisa de sinalizadores que pertencem
  a FORM e FASE — resolvido por AD-007.
- **Scope**: projeto
- **Date**: 2026-09-07
- **Status**: active

### AD-004

- **Decision**: Chaves primárias em **UUID** (`uuid_generate_v4()`), serializadas como string no
  JSON. Substitui o `BIGSERIAL` do schema manual existente.
- **Reason**: O front tipa todo `id` como `string`. UUID não vaza volume de dados por sequência
  e a extensão `uuid-ossp` já estava habilitada no schema, sem uso.
- **Trade-off**: Reescreve o schema e as chaves estrangeiras existentes; índices um pouco
  maiores que os de `BIGSERIAL`.
- **Scope**: toda a modelagem
- **Date**: 2026-09-07
- **Status**: active

### AD-005

- **Decision**: Schema versionado com **Alembic** (via Flask-Migrate), gerado a partir dos models
  SQLAlchemy. `init-scripts/01-schema.sql` sai; o container passa a aplicar migrations.
- **Reason**: O schema vai crescer feature a feature e o banco dos outros desenvolvedores precisa
  acompanhar sem derrubar o volume do Postgres — o que o `docker-entrypoint-initdb.d` exige, já
  que só roda em banco vazio.
- **Trade-off**: Uma etapa a mais no boot e o time precisa aprender o fluxo de migration.
- **Scope**: toda a modelagem
- **Date**: 2026-09-07
- **Status**: active

### AD-006

- **Decision**: **Pydantic v2** para validação de entrada e serialização de saída, com alias
  camelCase, e um **handler de erro central** que traduz `ValidationError` para o envelope
  `{ codigo, mensagem, campos, correlacao }` do contrato.
- **Reason**: O contrato exige `campos: { [campo]: mensagem }` em todo 422; escrever isso à mão
  em 34 endpoints reintroduz a divergência de formato a cada endpoint novo.
- **Trade-off**: Uma dependência a mais e uma camada de schemas entre controller e service.
- **Scope**: toda a borda HTTP
- **Date**: 2026-09-07
- **Status**: active

### AD-007

- **Decision**: `formularioDefinido` e `etapasDefinidas` do checklist de publicação são derivados
  de **tabelas mínimas de FORM e FASE criadas nesta rodada** (`formularios_chamada`,
  `fases_evento`), por `EXISTS`. As tabelas nascem vazias; nenhum endpoint de FORM/FASE é
  implementado agora.
- **Reason**: As alternativas são mentir (`true` fixo, e o 422 de checklist incompleto nunca é
  exercitado) ou travar (`false` fixo, e nenhum evento pode ser publicado nesta rodada).
- **Trade-off**: Duas migrations que esta rodada não consome. Em compensação, quando FORM e FASE
  chegarem, as tabelas e o sinalizador já existem.
- **Scope**: EVT-11, FORM, FASE
- **Date**: 2026-09-07
- **Status**: active

### AD-008

- **Decision**: **RBAC real por papel no evento** em toda rota de gestão; `/admin/*` exige
  `administrador`. A API bloqueia com 403 mesmo onde o handler MSW correspondente não checa nada.
- **Reason**: O próprio `handlers/eventos-e-chamadas.ts` declara que "autorização não é simulada
  além do que os próprios critérios de aceite descrevem", e a AD-001 do front afirma que o
  backend permanece a autoridade. Sem isto, qualquer usuário autenticado edita qualquer evento.
- **Trade-off**: Surgem 403 que nenhum teste do front exercita — risco de integração concentrado
  em telas que o front acredita permitidas. Mitigação: o front já filtra o menu por `pode()`, e
  a matriz de permissões da API é derivada de `shared/auth/permissoes.ts` do front.
- **Scope**: toda a API
- **Date**: 2026-09-07
- **Status**: active

### AD-009

- **Decision**: Aprovar uma solicitação de evento **cria a participação de chair do solicitante**,
  participações para cada `chairsIniciais` com conta existente, e **convite por token** por
  e-mail para os que não têm conta.
- **Reason**: Sem isso `GET /me/participacoes` volta vazio depois da aprovação e o solicitante
  não consegue gerir o evento que pediu — a navegação do app não fecha.
- **Trade-off**: A aprovação deixa de ser uma escrita só e vira transação com efeitos colaterais
  (participações + convites + e-mails). Exige que tudo aconteça na mesma transação.
- **Scope**: EVT-02, BASE-04, BASE-08
- **Date**: 2026-09-07
- **Status**: active

### AD-010

- **Decision**: Serviço de e-mail com **backend trocável por variável de ambiente**: em
  desenvolvimento grava o e-mail (com o link e o token) em log e numa tabela `emails_enviados`;
  em produção, SMTP.
- **Reason**: Confirmação de e-mail e convite de chair precisam entregar um token para o fluxo
  fechar, e não há credencial de servidor de e-mail institucional disponível agora.
- **Trade-off**: O caminho SMTP real só é exercitado quando houver credencial — fica declarado
  como dívida, não como pronto.
- **Scope**: BASE-02, BASE-08, EVT-02
- **Date**: 2026-09-07
- **Status**: active

### AD-011

- **Decision**: Front e API na **mesma origem em desenvolvimento**, via `server.proxy['/api']` no
  `vite.config.ts` do front apontando para `http://localhost:5000`.
- **Reason**: O cliente do front usa base **relativa** `/api` com `credentials: 'include'`. Um
  cookie de renovação `SameSite=Lax` não é enviado num POST cross-site, e `SameSite=None`
  exigiria HTTPS até em desenvolvimento.
- **Trade-off**: Exige uma alteração de 4 linhas no repositório do front, fora deste repositório.
- **Scope**: integração dev
- **Date**: 2026-09-07
- **Status**: active

### AD-012

- **Decision**: Gate de verificação por tarefa = **pytest contra Postgres real**, num database
  `sgs_test` do mesmo container do compose, migrado por fixture, com rollback de transação por
  teste.
- **Reason**: UUID, `TIMESTAMPTZ`, `ENUM` e constraints únicas se comportam de forma diferente em
  SQLite — testes verdes que não provariam nada sobre o banco real.
- **Trade-off**: A suíte exige o Postgres de pé; não roda em máquina sem Docker.
- **Scope**: todas as features
- **Date**: 2026-09-07
- **Status**: active

### AD-013

- **Decision**: Git flow: **`dev` derivada de `main`**, features derivadas de `dev`, merge de
  volta em `dev`. `main` só recebe `dev` em ponto de entrega.
- **Reason**: Pedido explícito do responsável.
- **Scope**: projeto
- **Date**: 2026-09-07
- **Status**: active

### AD-014

- **Decision**: Quatro divergências ao contrato atual do front são **propostas** por esta rodada
  (detalhadas na seção "Divergências propostas" de `spec.md`): (a) `GET /eventos` devolve dados
  estruturados em vez de `local` e `periodo` já formatados; (b) o conflito de versão passa a usar
  o envelope de erro com o registro atual em `atual`, em vez de devolver o registro cru com 409;
  (c) o convite ganha `tipo` e `submissaoTitulo` opcional, porque convite de chair não tem
  submissão; (d) o contato da organização sai de `campos.contato` e vira campo próprio no corpo
  de erro do convite.
- **Reason**: Cada uma codifica uma limitação do mock, não um requisito. (a) formatar
  apresentação é trabalho do front, e o próprio arquivo de cascas declara que aquele tipo "morre
  quando EVT assumir `/eventos`". (b) é a única resposta de erro do contrato fora do envelope
  universal. (c) é um defeito real que AD-009 revela: reusar o contrato de convite de avaliador
  para convite de chair exigiria inventar um `submissaoTitulo` inexistente. (d) o comentário do
  próprio handler admite que `campos` foi usado por ser "o único campo capaz de carregar dado
  junto de um 404".
- **Trade-off**: Cada divergência é uma alteração no repositório do front com os testes que a
  tocam. (c) é obrigatória — sem ela AD-009 não se implementa honestamente. (a), (b) e (d) são
  melhorias de coerência e podem ser recusadas sem bloquear a rodada.
- **Scope**: EVT-13, EVT-10, BASE-08
- **Date**: 2026-09-07
- **Status**: active — **as quatro aceitas** pelo responsável em 2026-09-07

### AD-015

- **Decision**: As alterações no repositório do front exigidas por AD-014 são feitas **no mesmo
  ciclo** que a API — handlers MSW, componentes e testes afetados juntos —, com `npm run gate`
  saindo 0 como prova de que o front continua verde.
- **Reason**: Deixar a API no formato novo e o front no antigo produz incompatibilidade
  garantida na integração, exatamente no ponto que a rodada existe para fechar.
- **Trade-off**: Duas árvores de trabalho em dois repositórios no mesmo ciclo, com dois gates
  distintos (pytest aqui, `npm run gate` lá). O front não tem branch `dev`: as alterações vão
  para `main` lá, que é a branch de trabalho daquele repositório.
- **Scope**: integração front↔API
- **Date**: 2026-09-07
- **Status**: active

### AD-016

- **Decision**: Código organizado em **módulos por domínio** (`app/modules/<dominio>/`), com as
  quatro camadas do padrão existente **dentro** de cada módulo (`controller.py`, `service.py`,
  `repository.py`, `models.py`, `schemas.py`) e a infraestrutura transversal em `app/core/`.
  Substitui a organização por camada (`app/controllers/`, `app/services/`, …).
- **Reason**: São 8 áreas e ~100 endpoints à frente; com camadas planas cada pasta vira uma lista
  de 8+ arquivos e nada de um domínio fica junto. Espelha a organização por feature do front
  (AD-013 lá), o que ajuda quem cruza os dois repositórios.
- **Trade-off**: Move os arquivos que o outro desenvolvedor criou. Os nomes de camada são
  preservados exatamente para que o padrão dele continue reconhecível.
- **Scope**: toda a API
- **Date**: 2026-09-07
- **Status**: active

### AD-017

- **Decision**: `flask-jwt-extended` 4.7.4 para emissão, verificação e mecânica de cookie. A
  rotação do token de renovação e a detecção de reuso vivem numa tabela `sessoes` própria, com
  **família** de tokens. De todo token de vida longa (renovação, confirmação de e-mail, convite) o
  banco guarda **apenas o SHA-256** — o valor cru existe só no e-mail ou no cookie.
- **Reason**: A mecânica de cookie httpOnly é fácil de errar e a biblioteca já a resolve; a
  rotação com detecção de reuso nenhuma biblioteca entrega, e exigiria tabela própria de qualquer
  forma. Guardar só o hash faz com que vazamento do banco não entregue sessão nem convite ativo.
- **Trade-off**: Um token perdido não pode ser reexibido — só reemitido. Aceitável.
- **Scope**: BASE-01, BASE-02, BASE-08
- **Date**: 2026-09-07
- **Status**: active

### AD-018

- **Decision**: AD-007 é **estendida** a mais duas tabelas mínimas vazias: `submissoes` (dona: SUB)
  e `notas_parecer` (dona: AVAL), junto de `formularios_chamada` e `fases_evento`. As quatro
  existem para que `checklist.formularioDefinido`, `checklist.etapasDefinidas`,
  `trilha.submissoesVinculadas` e `criterio.temNotas` sejam derivados de verdade.
- **Reason**: Mesmo racional de AD-007. Sem `notas_parecer`, o 409 de "critério com notas não pode
  ser excluído" (API-17 AC6) seria código morto sem teste possível; com ela, o teste insere uma
  linha e exercita o caminho.
- **Trade-off**: Quatro tabelas que esta rodada não preenche. As áreas donas as ampliam por
  migration aditiva.
- **Scope**: EVT, FORM, FASE, SUB, AVAL
- **Date**: 2026-09-07
- **Status**: active

### AD-019

- **Decision**: Um **commit por requisição**, em `app/core/unidade_de_trabalho.py`. Repositórios
  não chamam `db.session.commit()`.
- **Reason**: A aprovação de solicitação precisa criar evento, participações e convites
  atomicamente (API-13 AC4). Com commit por operação de repositório — o padrão atual em
  `user_repository.py` — uma falha no meio deixa estado parcial gravado.
- **Trade-off**: Quem escreve service precisa lembrar que nada é persistido até o fim da
  requisição. Em troca, toda operação composta é atômica sem esforço.
- **Scope**: toda a API
- **Date**: 2026-09-07
- **Status**: active

---

## Handoff

- **Feature**: `api-base-e-eventos` — fase **Execute**, Fases 0 a 4 (Lotes 1 a 4) concluídas.
  A plataforma-base (BASE) está completa.
- **Branch**: `feature/api-base-e-eventos` (derivada de `dev`).
- **Completed**: T1..T8 (Fase 0), T9..T14 (Fase 1), T15..T20 (Fase 2), T21..T24 (Fase 3) e
  T25..T27 (Fase 4). Fase 3: matriz de permissões da §3.7 portada para `app/core/permissoes.py`
  com teste de paridade que lê `permissoes.ts` do front em tempo de execução (R9);
  `ParticipacaoRepository` com as duas consultas do RBAC; `@exige_acao(acao, evento_de=...)`,
  que autentica antes de autorizar e autoriza antes de buscar o recurso;
  `GET /api/me/participacoes`. Fase 4: `ConviteService.criar_para_participacao` (D3, só o
  SHA-256 do token vai ao banco), `GET /api/convites/{token}` e
  `POST /api/convites/{token}/aceitar`. Um commit por tarefa. 312 testes, ruff limpo.
- **Next step**: **parada de validação com o responsável** — o front real é ligado contra a API.
  Depois dela, Lote 5 — Fase 5 (T28..T34), solicitação e decisão de evento. Antes dele, o
  Verificador das Fases 3 e 4.
- **Blockers**: none.
- **Uncommitted files**: none.
- **Notas de ambiente**:
  - A porta 5000 do host está ocupada por um contêiner `registry` alheio ao projeto, o
    que impede o `web` do compose de publicar a porta nesta máquina. O contêiner foi
    verificado por dentro da rede do compose: gunicorn sobe, as migrations são aplicadas
    no boot e a aplicação responde. Nenhuma mudança de código é necessária.
  - `requirements.txt` fixa `psycopg2-binary==2.9.12`: a 2.9.9 anterior não tem wheel
    para Python 3.13.
  - `EMAIL_BACKEND` é opcional e vale `log` por padrão; com `smtp`, as cinco variáveis
    `SMTP_*` passam a ser obrigatórias e faltar qualquer uma derruba o boot nomeando-a.
  - `CONTATO_DA_ORGANIZACAO` é opcional e vale `contato@sgs.local` por padrão. Ela existe
    porque o 404 de convite inválido precisa oferecer contato sem ter convite de onde tirá-lo.
  - `EmailService.enviar` captura exceção de qualquer tipo por exigência da API-10 AC2;
    a linha carrega `# noqa: BLE001` com a justificativa ao lado.
  - O teste de paridade de permissões procura o front em `C:\Users\lucas\projeto-extensao`;
    a variável `REPOSITORIO_DO_FRONT` sobrescreve o caminho. Sem o arquivo o teste **falha**
    — nunca é pulado.
- **Notas da Fase 2**:
  - `SessaoService.renovar` e `.autenticar` devolvem a falha como **valor**, não como
    exceção: a revogação de família por reuso e o registro da tentativa de login precisam
    ser commitados junto com a resposta de erro, e uma exceção desfaria a transação que os
    carrega. O controller levanta o erro depois de a transação fechar.
  - A recusa de `POST /api/auth/refresh` é a única resposta de erro montada fora do
    tratador central, porque o `Set-Cookie` que apaga o cookie precisa sair nela.
  - `ErroDaApi` ganhou `cabecalhos`, usado pelo `Retry-After` do 429 de API-20.
  - O login confere o e-mail inexistente contra um hash bcrypt fixo que nada abre, para os
    dois caminhos de 401 custarem o mesmo tempo (API-03 AC2).
- **Notas das Fases 3 e 4**:
  - `ParticipacaoRepository` devolve os papéis como **strings** da coluna, e quem precisa
    deles como `Papel` converte na borda. A dependência tem uma direção só, e é isso que
    evita o ciclo `core.permissoes` ↔ `eventos.repository`.
  - `@exige_acao` autentica por conta própria em vez de exigir `@exige_autenticacao`
    empilhado: a distinção 401/403 de API-09 AC3 não pode depender de a rota lembrar de
    empilhar dois decoradores.
  - As rotas reais de gestão chegam na Fase 5. A guarda é exercitada agora por rotas
    sintéticas em `tests/rotas_de_guarda.py`, registradas **só pela suíte** (um blueprint
    só pode ser registrado antes da primeira requisição, daí elas entrarem na fixture
    `aplicacao`). Quando as rotas reais existirem, elas podem sair.
  - **SPEC_DEVIATION** — coluna `convites.submissao_titulo`, ausente do schema do design
    (migration `d617d0800afa`). API-08 AC6 exige `submissaoTitulo` presente e não vazio no
    convite de avaliação, e `submissoes` — tabela da área SUB — não tem título; ampliá-la
    aqui violaria AD-018. O título vira snapshot no próprio convite, que já é o artefato
    lido sem sessão.
  - O `CHECK` de `convites` é unidirecional (`tipo <> 'avaliacao' OR submissao_id IS NOT
    NULL`), como o design o especifica: ele proíbe avaliação sem submissão, mas não proíbe
    participação **com** submissão. A outra metade de D3 é garantida pelo service, que é o
    único criador de convite de participação.
  - `ConviteService.consultar` confere `aceito` **antes** do prazo, para o aceite repetido
    responder 409 `convite_ja_usado` mesmo depois de a data passar (AC4 e AC9).
  - **Divergência de contrato ainda não decidida**: `TelaDeConvite.tsx` do front lê
    `resposta.destino` do aceite e navega para ele; a spec (API-08 AC7) define a resposta
    como `{ tokenDeAcesso, usuario }`, e `destino` não aparece em lugar nenhum das specs nem
    em AD-014. A API foi implementada conforme a spec. Decidir na Fase 8: ou o front passa
    a navegar por conta própria, ou `destino` vira a quinta divergência aceita.
