# Validation — `api-base-e-eventos`

Relatório do Verificador independente (author ≠ verifier). Cada fase acrescenta a sua
própria seção; nada de fase anterior é sobrescrito.

---

## Fase 5 — T28..T34 (API-11, API-12, API-13)

- **Range de commits**: `70ed954..1b80514` (7 commits), sobre `be75bad`.
  - `70ed954` modelos de solicitacao e evento (T28)
  - `c4edea1` criacao de solicitacao de evento (T29)
  - `753e25b` edicao e listagem das proprias solicitacoes (T30)
  - `85f18bd` fila administrativa de solicitacoes (T31)
  - `090991b` aprovacao de solicitacao (T32)
  - `d744a2d` participacoes e convites na aprovacao (T33)
  - `1b80514` recusa de solicitacao com motivo obrigatorio (T34)
- **Branch**: `feature/api-base-e-eventos`
- **Data**: 2026-09-07

### Veredito: **PASS com uma lacuna**

Todos os gates passam, e 18 de 18 mutantes injetados foram mortos pelos testes —
com uma exceção decisiva: **o mutante que apaga a detecção de ciclo por inteiro
sobrevive à suíte e2e completa**. API-11 AC5 não tem cobertura pela borda HTTP e,
mais que isso, **não é alcançável por nenhuma rota HTTP existente** (ver Lacuna
L1). O restante da fase está coberto com asserções de valor exato.

---

### Gates

| Gate | Comando | Código de saída | Resultado |
| --- | --- | --- | --- |
| Testes | `.venv/Scripts/python.exe -m pytest -q` | **0** | 399 passed, 4 warnings |
| Lint | `.venv/Scripts/python.exe -m ruff check app tests` | **0** | All checks passed! |

Suíte reexecutada depois de toda a campanha de mutação: **399 passed, exit 0**.
`git status --porcelain` vazio — nenhuma mutação ficou na árvore.

---

### Cobertura por critério (evidência-ou-zero)

Cada linha registra a asserção que cobre o critério — `arquivo:linha` mais a
**expressão** asserida — e se o valor asserido bate com o desfecho que a spec define.

#### T28 — Modelos e repositório

| Critério | Evidência (`arquivo:linha` + expressão) | Desfecho da spec | Status |
| --- | --- | --- | --- |
| Busca por id | `tests/integracao/eventos/test_solicitacoes_repository.py:52` — `SolicitacaoRepository.por_id(solicitacao.id).id == solicitacao.id`; `:56` — `por_id(uuid.uuid4()) is None` | consulta existe | ✅ |
| Busca por `identificador_pagina` | `test_solicitacoes_repository.py:67` — `encontrada.identificador_pagina == "simposio-2026"`; `:78` — `EventoRepository.por_identificador("congresso-2026").id == evento.id` | consulta nas duas tabelas | ✅ |
| Listagem por solicitante | `test_solicitacoes_repository.py:100` — `[s.id for s in minhas] == [minha.id]` (com uma alheia gravada); `:104` — `== []` | só as do próprio | ✅ |
| Listagem administrativa ordenada por `criado_em` **crescente** | `test_solicitacoes_repository.py:125-129` — `[s.id for s in listadas] == [primeira.id, meio.id, ultima.id]`, com inserção fora de ordem | ordem crescente exata | ✅ |
| `eventos.evento_pai_id` auto-referência | `test_solicitacoes_repository.py:195` — `sessao.get(Evento, filho.id).evento_pai_id == pai.id`; `:196` — `EventoRepository.filhos_de(pai.id) == [filho.id]` | auto-referência funciona | ✅ |
| `UNIQUE (solicitacao_id, email)` em chairs iniciais | `test_solicitacoes_repository.py:163-164` — `pytest.raises(IntegrityError)` no segundo `flush()` do mesmo par | constraint real no banco | ✅ |
| `UNIQUE` de `identificador_pagina` em solicitações | `test_solicitacoes_repository.py:85-86` — `pytest.raises(IntegrityError)` | constraint real | ✅ |

#### T29 / API-11 AC1..AC5

| Critério | Evidência | Desfecho da spec | Status |
| --- | --- | --- | --- |
| **AC1** 201 com `situacao: "pendente"`, `criadoEm`, `versao: 1` | `tests/e2e/test_solicitacoes_evento.py:77-85` — `resposta.status_code == 201`, `corpo["situacao"] == "pendente"`, `corpo["versao"] == 1`, `corpo["solicitanteId"] == str(usuario.id)`, `corpo["criadoEm"].endswith("Z")`, `uuid.UUID(corpo["id"])` | 201 + os quatro campos exatos | ✅ |
| **AC2** 422 `campos.identificadorPagina` — já existe em **solicitação** | `test_solicitacoes_evento.py:122-125` — `status_code == 422`, `corpo["codigo"] == "dados_invalidos"`, `"identificadorPagina" in corpo["campos"]` | 422 no campo | ✅ |
| **AC2** já existe em **evento** (checagem cruzada) | `test_solicitacoes_evento.py:136-137` — `status_code == 422`, `"identificadorPagina" in ...["campos"]` | 422 no campo | ✅ |
| **AC3** campo faltante nomeado — `titulo` | `test_solicitacoes_evento.py:149-150` — `== 422`, `"titulo" in ...["campos"]` | 422 nomeando o campo | ✅ |
| **AC3** — `identificadorPagina` **vazio** | `test_solicitacoes_evento.py:158-159` — `== 422`, `"identificadorPagina" in ...` | idem (cobre "vazio") | ✅ |
| **AC3** — `dataInicio` ausente | `test_solicitacoes_evento.py:168-169` — `== 422`, `"dataInicio" in ...` | idem | ✅ |
| **AC3** — `dataTermino` ausente | `test_solicitacoes_evento.py:178-179` — `== 422`, `"dataTermino" in ...` | idem | ✅ |
| **AC4** término anterior ao início → `campos.dataTermino` | `test_solicitacoes_evento.py:192-195` — `== 422`, `"dataTermino" in campos`, **`"dataInicio" not in campos`** | 422 no campo certo, e só nele | ✅ |
| **AC5** ciclo em `eventoPaiId` → 422 | **sem asserção pela borda HTTP** — ver Lacuna **L1**. A regra é testada só na camada de service: `tests/integracao/eventos/test_deteccao_de_ciclo.py:228-229` — `"eventoPaiId" in recusa.value.extras["campos"]`, `recusa.value.status == 422` | 422 `campos.eventoPaiId` numa requisição | ⚠️ **L1** |
| Pai inexistente → 422 `eventoPaiId` | `test_solicitacoes_evento.py:206-207` — `== 422`, `"eventoPaiId" in ...` | (não é AC; validação extra) | ✅ |
| 401 sem token | `test_solicitacoes_evento.py:227-229` — `== 401`, `codigo == "nao_autenticado"`, **`SolicitacaoRepository.listar() == []`** (nada gravado) | 401 e nenhum efeito | ✅ |

#### T30 / API-11 AC6..AC8 + API-09 AC6

| Critério | Evidência | Desfecho da spec | Status |
| --- | --- | --- | --- |
| **AC6** PATCH pendente pelo dono aplica, incrementa `versao`, 200 | `tests/e2e/test_minhas_solicitacoes.py:73-77` — `== 200`, `corpo["titulo"] == "Simpósio Renomeado"`, **`corpo["versao"] == 2`**, `corpo["situacao"] == "pendente"`; persistência em `:90` — `por_id(...).titulo == "Título Persistido"` | 200 + versão exata 2 | ✅ |
| PATCH parcial não apaga campo não enviado | `test_minhas_solicitacoes.py:103-104` — `corpo["cidade"] == "Feira de Santana"`, `corpo["titulo"] == "Título Original"` | semântica de PATCH | ✅ |
| **AC7** PATCH em já decidida → 409 `solicitacao_ja_decidida` | `test_minhas_solicitacoes.py:123-124` — `== 409`, `codigo == "solicitacao_ja_decidida"`; e `:140-141` — `gravada.titulo == "Título Congelado"`, **`gravada.versao == 1`** | 409 com código exato, sem efeito | ✅ |
| **API-09 AC6** PATCH por não-solicitante → 403 | `test_minhas_solicitacoes.py:158-160` — `== 403`, `codigo == "sem_permissao"`, `por_id(...).titulo == "Título do Dono"` | 403 e nada alterado | ✅ |
| **AC8** `GET /me/solicitacoes-evento` só as próprias | `test_minhas_solicitacoes.py:196-197` — `[e["id"] for e in corpo] == [str(minha.id)]` com uma alheia gravada; `:204` — `== []` | só as do próprio | ✅ |
| 401 / 404 no PATCH e na lista | `:170-171` — `== 401` + `codigo`; `:181-182` — `== 404`, `codigo == "solicitacao_inexistente"`; `:210-211` — `== 401` | envelope de erro | ✅ |

#### T31 / API-12 AC1, AC2

| Critério | Evidência | Desfecho da spec | Status |
| --- | --- | --- | --- |
| **AC1** 200 ordenado por `criadoEm` crescente, três fora de ordem | `tests/e2e/test_fila_de_solicitacoes.py:293-298` — `== 200` e `[e["titulo"] for e in ...] == ["A primeira", "Do meio", "A última"]`, inseridas na ordem meio→última→primeira | ordem crescente exata | ✅ |
| **AC2** `?status=pendente` filtra | `test_fila_de_solicitacoes.py:327` — `[e["titulo"] for e in corpo] == ["Pendente"]`, com aprovada e recusada gravadas | só aquela situação | ✅ |
| **AC2** sem parâmetro traz todas | `test_fila_de_solicitacoes.py:339-343` — `[e["situacao"] for e in corpo] == ["pendente", "aprovada", "recusada"]` | todas as situações | ✅ |
| Campos do contrato na fila | `test_fila_de_solicitacoes.py:309-312` — `corpo[0]["id"]`, `["solicitanteId"]`, `["situacao"] == "pendente"`, `["versao"] == 1` | projeção correta | ✅ |
| 403 não-administrador (AD-008) | `test_fila_de_solicitacoes.py:362-363` — `== 403`, `codigo == "sem_permissao"` | 403 | ✅ |
| 401 sem token | `test_fila_de_solicitacoes.py:369-370` — `== 401`, `codigo == "nao_autenticado"` | 401 | ✅ |

#### T32 / API-12 AC3, AC4, AC7, AC8 + Edge Case de concorrência

| Critério | Evidência | Desfecho da spec | Status |
| --- | --- | --- | --- |
| **AC3** 200 `{ solicitacao, evento }`, `aprovada` com `decididoPorId`/`decididoEm` | `tests/e2e/test_aprovacao_de_solicitacao.py:84-91` — `== 200`, **`set(corpo) == {"solicitacao", "evento"}`**, `["solicitacao"]["situacao"] == "aprovada"`, `["decididoPorId"] == str(administrador.id)`, `["decididoEm"].endswith("Z")`, `["evento"]["situacao"] == "aprovado"` | 200, chaves exatas, situações exatas | ✅ |
| **AC3** persistência do evento ligado à solicitação | `test_aprovacao_de_solicitacao.py:120-121` — `EventoRepository.por_solicitacao(...) is not None`, `por_id(...).situacao == "aprovada"` | gravado de fato | ✅ |
| Cópia dos dados da solicitação para o evento | `test_aprovacao_de_solicitacao.py:102-110` — nove igualdades exatas (`titulo`, `sigla`, `ano`, `tipo`, `cidade`, `pais`, `fuso`, `dataInicio`, `dataTermino`) | evento herda os dados | ✅ |
| **AC4** `modeloDeAvaliacao: "aberta"` | `test_aprovacao_de_solicitacao.py:135` — `evento["modeloDeAvaliacao"] == "aberta"` | valor exato | ✅ |
| **AC4** `avaliadoresPorSubmissao: 1` | `:146` — `evento["avaliadoresPorSubmissao"] == 1` | valor exato | ✅ |
| **AC4** `rebuttalHabilitado: false` | `:157` — `evento["rebuttalHabilitado"] is False` (identidade, não truthiness) | valor exato | ✅ |
| **AC4** `maximoDeRodadas: 1` | `:168` — `evento["maximoDeRodadas"] == 1` | valor exato | ✅ |
| **AC4** `versao: 1` | `:179` — `evento["versao"] == 1` | valor exato | ✅ |
| **AC7** 409 carregando `decididoPorId`, `decididoEm`, `situacao` | `test_aprovacao_de_solicitacao.py:196-203` — `== 409`, `codigo == "solicitacao_ja_decidida"`, `corpo["decididoPorId"] == str(quem_decidiu.id)`, **`corpo["decididoEm"] == "2026-04-01T12:00:00Z"`** (valor literal), `corpo["situacao"] == "aprovada"`, `"correlacao" in corpo`, `"mensagem" in corpo` | 409 + os 3 extras **ao lado** do envelope | ✅ |
| Segunda aprovação sequencial não cria 2º evento | `:213-215` — `primeira == 200`, `segunda == 409`, `segunda...["decididoPorId"] == str(administrador.id)` | idem AC7 | ✅ |
| **AC8** 404 `solicitacao_inexistente` | `:226-227` — `== 404`, `codigo == "solicitacao_inexistente"` | código exato | ✅ |
| 403 não-administrador | `:236-238` — `== 403`, `codigo == "sem_permissao"`, **`EventoRepository.por_solicitacao(...) is None`** | 403 e nenhum evento | ✅ |
| 401 sem token | `:246-247` — `== 401`, `codigo == "nao_autenticado"` | 401 | ✅ |
| **Edge Case** aprovações simultâneas: uma cria, outra 409 | `test_aprovacao_de_solicitacao.py:335-345` — `len(conflitos) == 1`, `conflitos[0].codigo == "solicitacao_ja_decidida"`, **`eventos == 1`** (contagem lida em conexão separada). Duas conexões reais + `Barrier(2)` | exatamente um evento, 409 na outra | ✅ (mutação reproduzida, ver M15) |

#### T33 / API-13 AC1..AC6 + Edge Case de reprocessamento

| Critério | Evidência | Desfecho da spec | Status |
| --- | --- | --- | --- |
| **AC1** solicitante vira `chair` ativo | `tests/integracao/eventos/test_efeitos_da_aprovacao.py:86` — `papeis(evento.id, solicitante.id) == ["chair"]` (via `papeis_no_evento`, que filtra `ativo.is_(True)`) | participação ativa de chair | ✅ |
| **AC1** aparece em `GET /me/participacoes` | `:97-98` — `[e.evento_id for e in listadas] == [evento.id]`, `listadas[0].papeis == ["chair"]` | a navegação do app fecha | ✅ |
| **AC2** chair inicial **com** conta vira participação | `:112-113` — `papeis(evento.id, ana.id) == ["chair"]` **e** `convites_de(evento.id, "ana@...") == []` (participação sim, convite não) | participação, sem convite | ✅ |
| **AC3** chair **sem** conta vira convite `participacao` | `:127-133` — `len(convites) == 1`, `convites[0].tipo == "participacao"`, `.papel == "chair"`, `.situacao == "pendente"`, **`.submissao_id is None`** (D3), `.token_hash` | convite pendente com token, sem submissão | ✅ |
| **AC3** e-mail disparado | `:150-151` — `len(enviados) == 1`, `enviados[0].situacao == "enviado"` | e-mail correspondente | ✅ |
| **AC3+AC2** um de cada tipo | `:166-168` — `papeis(...bia...) == ["chair"]`, `len(convites_de(..."sem-conta"...)) == 1`, `convites_de(..."bia"...) == []` | Independent Test da spec | ✅ |
| **AC6** e-mail repetido → **um** efeito | `:187-195` — `count(ParticipacaoEvento) where evento+usuario == 1`, com a lista contendo `["ana@...", "ana@..."]` | exatamente 1 | ✅ |
| **AC6** e-mail do próprio solicitante na lista | `:205-214` — `convites_de(..., "organizador@...") == []` **e** contagem de participações `== 1` | um efeito só | ✅ |
| **AC4** falha no meio não persiste nada | `:245-250` — `contar(Evento) == eventos_antes`, `contar(ParticipacaoEvento) == participacoes_antes`, `contar(Convite) == convites_antes`, `db.session.get(SolicitacaoEvento, ...).situacao == "pendente"`. Erro forçado na **última** etapa (`ConviteService.criar_para_participacao`), quando evento e participação já estão na sessão; contagens tiradas após `sessao.commit()` da preparação | zero linhas gravadas, incluindo a solicitação | ✅ |
| **AC5** falha de e-mail não desfaz a aprovação | `:278-288` — `solicitacao_decidida.situacao == "aprovada"`, `evento.situacao == "aprovado"`, `len(convites_de(...)) == 1`, `papeis(...) == ["chair"]`, **`registro.situacao == "falha"`**. Backend de e-mail que levanta `RuntimeError` | aprovação válida + registro `falha` | ✅ |
| **Edge Case** reprocessar não duplica participação | `:312-314` — `total == 2` (solicitante + ana, não 4), `papeis(...solicitante...) == ["chair"]`, `papeis(...ana...) == ["chair"]`, após chamar `_aplicar_efeitos` uma segunda vez | nenhuma duplicata | ✅ |
| **Edge Case** reprocessar não emite 2º convite | `:327` — `len(convites_de(evento.id, "sem-conta@...")) == 1` | um convite só | ✅ |

**Sobre a remoção do conjunto `ja_atendidos`**: verificado. A idempotência não depende
dele e está garantida em três camadas independentes, cada uma com mutante próprio que
morre: `SolicitacaoRepository.definir_chairs_iniciais` deduplica na gravação
(`dict.fromkeys`, mutante **M17** morto), `ParticipacaoRepository.garantir` só cria se não
existir (**M14** morto) e `ConviteRepository.pendente_de_participacao` barra o segundo
convite (**M16** morto). Os três cenários pedidos — e-mail repetido em `chairsIniciais`,
e-mail do próprio solicitante na lista, e reprocessamento inteiro — têm teste com
contagem exata (`== 1`). A conclusão do autor de que `ja_atendidos` era código sem efeito
se sustenta.

#### T34 / API-12 AC5..AC8

| Critério | Evidência | Desfecho da spec | Status |
| --- | --- | --- | --- |
| **AC5** 200 com `recusada`, `motivoRecusa`, `decididoPorId`, `decididoEm` | `tests/e2e/test_recusa_de_solicitacao.py:85-90` — `== 200`, `corpo["situacao"] == "recusada"`, `corpo["motivoRecusa"] == "Fora do escopo institucional."`, `corpo["decididoPorId"] == str(administrador.id)`, `corpo["decididoEm"].endswith("Z")` | 200 + os quatro campos | ✅ |
| **AC5** persistência | `:104-106` — `gravada.situacao == "recusada"`, `.motivo_recusa == "Datas conflitantes."`, `.decidido_por_id == administrador.id` | gravado de fato | ✅ |
| **AC6** motivo ausente → 422 `campos.motivo` | `:120-124` — `== 422`, `codigo == "dados_invalidos"`, `"motivo" in corpo["campos"]`, **`por_id(...).situacao == "pendente"`** | 422 no campo, sem efeito | ✅ |
| **AC6** motivo **vazio** → 422 | `:135-137` — `== 422`, `"motivo" in ...["campos"]`, `situacao == "pendente"` | idem | ✅ |
| **AC7** 409 com `decididoPorId`/`decididoEm`/`situacao` | `:158-165` — `== 409`, `codigo == "solicitacao_ja_decidida"`, `corpo["decididoPorId"] == str(quem_decidiu.id)`, `corpo["decididoEm"] == "2026-04-01T12:00:00Z"`, `corpo["situacao"] == "aprovada"`, `"correlacao" in corpo`, `"mensagem" in corpo` | 409 + 3 extras | ✅ |
| **AC7** 2ª recusa não sobrescreve o motivo | `:183-187` — `segunda.status_code == 409`, `por_id(...).motivo_recusa == "Motivo original."` | estado imutável após decisão | ✅ |
| **AC8** 404 `solicitacao_inexistente` | `:200-201` — `== 404`, `codigo == "solicitacao_inexistente"` | código exato | ✅ |
| 403 não-administrador | `:214-216` — `== 403`, `codigo == "sem_permissao"`, `situacao == "pendente"` | 403 sem efeito | ✅ |
| 401 sem token | `:224-225` — `== 401`, `codigo == "nao_autenticado"` | 401 | ✅ |
| Recusa **não** cria evento nem participação | `:244-246` — `contar(Evento) == eventos_antes`, `contar(ParticipacaoEvento) == participacoes_antes`, `EventoRepository.por_solicitacao(...) is None` | nenhum rastro | ✅ |

#### Edge Cases da spec aplicáveis à Fase 5

| Edge Case | Evidência | Status |
| --- | --- | --- |
| Duas aprovações simultâneas: só uma cria evento, a outra 409 | `test_aprovacao_de_solicitacao.py:335-345` (ver T32) | ✅ |
| Solicitante já tem participação de chair (reprocessamento) → nenhuma duplicata | `test_efeitos_da_aprovacao.py:312-314` | ✅ |
| Ciclo em dados legados: travessia termina, cada evento visitado uma vez | `tests/integracao/eventos/test_deteccao_de_ciclo.py:260-270` — grava `primeiro.evento_pai_id = segundo.id` fechando o ciclo e chama `validar_evento_pai`; o teste termina (sem `RecursionError`/loop) | ✅ (camada de service) |
| `identificadorPagina` alterado em evento publicado → 422 | fora do escopo da Fase 5 (T36, Fase 6) | n/a |

---

### Sensor de discriminação (mutação)

18 mutantes injetados em estado descartável (cópia do arquivo antes, restauração
depois). **17 mortos, 1 sobrevivente.**

| # | Alvo | Mutação | Testes | Resultado |
| --- | --- | --- | --- | --- |
| M1 | ordenação `criado_em` crescente na fila | `.order_by(criado_em)` → `.desc()` | fila e2e + repo | **morto** (3 falhas) |
| M2 | checagem cruzada contra `eventos` | `if EventoRepository.por_identificador(...)` → `if False and ...` | e2e criação | **morto** (1 falha, o teste certo) |
| M3 | comparação de datas | `termino < inicio` → `termino > inicio` | e2e criação + edição | **morto** (9 falhas) |
| M4 | API-12 AC4 `modeloDeAvaliacao` | `"aberta"` → `"duplo_cega"` | e2e aprovação | **morto** (1 falha, o teste dedicado) |
| M5 | API-12 AC4 `avaliadoresPorSubmissao` | `1` → `3` | e2e aprovação | **morto** (1 falha, o teste dedicado) |
| M6 | API-12 AC4 `rebuttalHabilitado` | `False` → `True` | e2e aprovação | **morto** (10 falhas) |
| M7 | API-12 AC4 `maximoDeRodadas` | `1` → `2` | e2e aprovação | **morto** (1 falha, o teste dedicado) |
| M8 | API-12 AC4 `versao` do evento | `versao=1` → `versao=7` | e2e aprovação | **morto** (1 falha, o teste dedicado) |
| M9 | `versao += 1` na edição | `+= 1` → `+= 0` | e2e edição | **morto** (1 falha) |
| M10 | filtro do `por_solicitante` (vazar alheia) | `.where(solicitante_id == ...)` removido | e2e edição + repo | **morto** (2 falhas) |
| M11 | guarda `situacao != pendente` | `if solicitacao.situacao != PENDENTE` → `if False` | aprovação + recusa + edição | **morto** (7 falhas) |
| M12 | extras `decididoPorId`/`decididoEm`/`situacao` no 409 | os três `kwargs` removidos do `Conflito` | aprovação + recusa | **morto** (3 falhas) |
| M13 | participação de chair do solicitante | chamada `garantir(...solicitante_id...)` removida | efeitos da aprovação | **morto** (4 falhas) |
| M14 | idempotência de `ParticipacaoRepository.garantir` | `if existente is not None: return existente` removido | efeitos da aprovação | **morto** (3 falhas) |
| M15 | `with_for_update()` no lock da decisão | linha removida — **3 execuções independentes** | `test_duas_aprovacoes_simultaneas_criam_um_evento_so` | **morto 3/3** |
| M16 | dedup do convite (`pendente_de_participacao`) | `if ... is None:` → `if True:` | efeitos da aprovação | **morto** (1 falha) |
| M17 | dedup de e-mails em `definir_chairs_iniciais` | `dict.fromkeys(emails)` → `emails` | repo + e2e criação | **morto** (1 falha) |
| **M18** | **detecção de ciclo (API-11 AC5) inteira** | `if evento_proprio is None: return` → `return` incondicional (apaga a travessia) | **toda a suíte e2e** | **SOBREVIVEU — 165 passed** |

**M15 — reprodução da alegação do autor**: confirmada. Sem `with_for_update()`, o
teste de aprovações simultâneas falha nas **3 de 3** execuções. A construção com duas
conexões próprias e `Barrier(2)` é o que dá ao teste esse poder discriminatório: as
duas transações estão comprovadamente abertas e sobrepostas antes de qualquer uma
decidir. O teste é legítimo, e a afirmação do autor se sustenta.

Árvore verificada limpa ao fim da campanha: `git status --porcelain` sem saída;
suíte reexecutada com **399 passed, exit 0**.

---

### Lacunas

#### L1 — API-11 AC5 (ciclo em `eventoPaiId`) não tem cobertura pela borda HTTP, e a regra é inalcançável por qualquer rota

**Severidade: média.** Não quebra nada em produção hoje, mas um critério de aceite
declarado está sem implementação efetiva, e a task T29 marca "Testes e2e para os seis
casos" quando só cinco são exercitáveis.

**Critério descoberto**: spec API-11 AC5 — *"WHEN `eventoPaiId` aponta para um evento
que é descendente do evento sendo criado THEN a API SHALL responder 422 com
`campos.eventoPaiId`"*; e o "Done when" de T29: *"422 `campos.eventoPaiId` quando o pai
é descendente do próprio evento (ciclo, AC5)"*.

**Evidência**: a asserção existe apenas em
`tests/integracao/eventos/test_deteccao_de_ciclo.py:226` — chamada **direta** a
`SolicitacaoService.validar_evento_pai(filho.id, evento_proprio=proprio.id)`. Nenhum
teste em `tests/e2e/` passa um `eventoPaiId` que feche ciclo por uma requisição.

**Prova de que não é só falta de teste — a regra é código morto pelas rotas atuais**:
o mutante **M18** apaga a travessia inteira e **os 165 testes e2e continuam passando**.
O motivo é estrutural, não acidental:

- No `POST` (`services/solicitacao.py:68`), `criar` chama
  `validar_evento_pai(..., evento_proprio=None)` — literal. Com `evento_proprio is None`,
  a função retorna em `solicitacao.py:312-313` antes de qualquer travessia.
- No `PATCH` (`services/solicitacao.py:116`), `evento_proprio` vem de
  `EventoRepository.por_solicitacao(solicitacao.id)`. Mas o controller só deixa o PATCH
  chegar ao service em solicitação **pendente** (`controllers/solicitacoes.py:290`,
  `exigir_pendente`), e um evento só passa a existir na **aprovação**
  (`solicitacao.py:174`). Logo `por_solicitacao` devolve `None` em 100% das chamadas
  alcançáveis, e `evento_proprio` é sempre `None` também aqui.

**Julgamento sobre a leitura do autor**: a premissa está certa — na *criação* não há
evento próprio, então AC5 de fato não pode disparar no POST. Mas a conclusão de que
"a regra vive no service e é acionada pelo PATCH quando a solicitação já tem evento"
**não se sustenta**: o PATCH é barrado em solicitação decidida, que é justamente a
única em que existe evento. Não há hoje nenhum caminho HTTP que faça `evento_proprio`
ser diferente de `None`. A cobertura de service é adequada como teste *da função*, e o
caso de dados legados (`test_deteccao_de_ciclo.py:260`) é um bom teste do Edge Case de
travessia; o que falta é o consumidor real da regra.

**Encaminhamento sugerido** (uma das três, a decidir pelo autor/orientador):
1. Reconhecer que AC5 pertence à **edição do evento** (`PATCH /api/eventos/{id}`, Fase 6
   / API-14 AC8, que a T-de-ciclo em `tasks.md:948` já prevê) e registrar em `STATE.md`
   que AC5 de API-11 é herdado por ela — com o e2e escrito lá.
2. Ou implementar em API-11 a variante que *é* alcançável na criação: recusar
   `eventoPaiId` que forme ciclo **entre solicitações pendentes encadeadas**.
3. Ou emendar a spec, movendo AC5 de API-11 para API-14 e ajustando o "Done when" de
   T29 de seis para cinco casos e2e.

Em qualquer caso, **T29 não deveria ficar marcada como tendo os seis casos e2e**
enquanto o sexto não existir.

#### L2 — Lacuna de precisão de spec: ordem entre API-12 AC6 e AC7 na recusa

**Severidade: baixa.** Não é defeito de implementação; é ambiguidade da spec, e o autor
já a registrou honestamente em `STATE.md`.

Quando `POST .../recusar` chega **sem motivo** numa solicitação **já decidida**, a
implementação responde **422** (a validação de corpo, em `controllers/solicitacoes.py:348`,
roda antes de `transacao()` e antes do `exigir_pendente` de dentro de `recusar`). A spec
enuncia AC6 e AC7 sem estabelecer precedência, então nenhum dos dois desfechos é
contrariado — mas também nenhum é *definido*. Não há teste para essa combinação, e
marcá-lo como coberto seria aprovar uma asserção que a spec não ancora.

**Encaminhamento**: decidir o desfecho desejado (o 409 tende a ser mais útil para a
tela, que precisa dizer que a decisão já ocorreu), registrar como AD, e então escrever
o teste. Enquanto não houver decisão, fica como lacuna de precisão de spec, não como
falha.

---

### Resumo

- **Gates**: pytest exit **0** (399 passed) · ruff exit **0**.
- **Mutação**: 18 injetados, **17 mortos, 1 sobrevivente** (M18 → Lacuna L1).
- **Árvore**: limpa (`git status --porcelain` vazio), suíte restaurada em 399 passed.
- **Alegações do autor verificadas**: `with_for_update()` reproduzido **3/3** (procede);
  remoção de `ja_atendidos` (procede, idempotência garantida em 3 camadas com mutante
  próprio em cada); AC5 inalcançável pelo POST (premissa procede, mas a alternativa
  proposta — PATCH — também é inalcançável, ver L1).
- **T28, T30, T31, T32, T33, T34**: totalmente cobertas com asserções de valor exato.
- **T29**: coberta em 5 dos 6 critérios; AC5 pendente (L1).

---
---

# Validação independente — Fases 5 + 6 (EVT)

**Data**: 2026-09-07
**Spec**: `.specs/features/api-base-e-eventos/spec.md`
**Intervalo de commits**: `2569642..b928d07` (19 commits, 40 arquivos, +6263/-120)
**Verificador**: sub-agente independente (autor ≠ verificador) — não herdou o modelo mental de quem escreveu
**Requisitos em escopo**: API-11, API-12, API-13, API-14, API-15, API-16, API-17 + Edge Cases que tocam essas rotas
**Restrições ativas conferidas**: AD-008 (RBAC por papel), AD-009 (efeitos da aprovação), AD-014 D2 (`atual` no 409), AD-019 (commit por requisição)

**Veredito**: ❌ **FAIL** — 1 AC com defeito de comportamento confirmado (API-11 AC5, metade "não aprovado").

---

## Gate

| Comando | Exit | Resultado |
| ------- | ---- | --------- |
| `.venv/Scripts/python.exe -m pytest -q` | **0** | **509 passed**, 0 failed, 0 skipped, 83.65s |
| `.venv/Scripts/python.exe -m ruff check app tests` | **0** | All checks passed |
| `flask db upgrade` (com `.env` carregado) | **0** | idempotente, sem DDL pendente |

Gate reexecutado ao fim do sensor de mutação: **509 passed, exit 0** — nenhuma mutação residual.
Contagem de testes antes da Fase 5 (relatório anterior): 399 → **509**. Delta **+110**, sem
remoção nem enfraquecimento de teste algum.

---

## Checagem ancorada na spec — evidência-ou-zero

Cada AC abaixo foi rastreada até `arquivo:linha` com a expressão da asserção reproduzida, e o
**valor afirmado** foi conferido contra o resultado que a spec define — não apenas a existência
de uma asserção.

### API-11 — Solicitação de criação de evento

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | 201 com `situacao: "pendente"`, `versao: 1`, `solicitanteId`, `criadoEm` | `tests/e2e/test_solicitacoes_evento.py:77-85` — `assert resposta.status_code == 201`; `assert corpo["situacao"] == "pendente"`; `assert corpo["versao"] == 1`; `assert corpo["solicitanteId"] == str(usuario.id)`; `assert corpo["criadoEm"].endswith("Z")` | ✅ PASS |
| AC2 | 422 com `campos.identificadorPagina` — colisão com **solicitação** e com **evento** | `tests/e2e/test_solicitacoes_evento.py:122-125` (solicitação) e `:136-137` (evento) — `assert resposta.status_code == 422`; `assert "identificadorPagina" in corpo["campos"]` | ✅ PASS (as duas metades) |
| AC3 | 422 nomeando o campo faltante | `:149-150` (titulo), `:158-159` (identificadorPagina vazio), `:168-169` (dataInicio), `:178-179` (dataTermino) | ✅ PASS |
| AC4 | 422 com `campos.dataTermino` | `:192-195` — `assert "dataTermino" in campos`; `assert "dataInicio" not in campos` (afirma o campo **certo**, não só a presença de erro) | ✅ PASS |
| AC5a | 422 com `campos.eventoPaiId` — pai **inexistente** | `:206-207` — `assert resposta.status_code == 422`; `assert "eventoPaiId" in resposta.get_json()["campos"]` | ✅ PASS |
| **AC5b** | **422 com `campos.eventoPaiId` — pai existente porém `não aprovado`** | **sem evidência** — busca feita em `tests/` por `nao_aprovado`, `pendente_aprovacao` e por construção de pai em outra situação; `criar_evento` (`test_solicitacoes_evento.py:47-54`) fixa `situacao="aprovado"`, e nenhum teste do intervalo constrói um pai não aprovado | ❌ **GAP — defeito confirmado** |
| AC6 | 200, alterações aplicadas, `versao` incrementada | `tests/e2e/test_minhas_solicitacoes.py:73-77` — `assert corpo["versao"] == 2`; `assert corpo["titulo"] == "Simpósio Renomeado"`; persistência em `:90` | ✅ PASS |
| AC7 | 409 `solicitacao_ja_decidida` | `tests/e2e/test_minhas_solicitacoes.py:123-124` — `assert resposta.get_json()["codigo"] == "solicitacao_ja_decidida"`; e `:140-141` prova que nada mudou (`titulo` e `versao`) | ✅ PASS |
| AC8 | 200 só com as solicitações do próprio usuário | `tests/e2e/test_minhas_solicitacoes.py:196-197` — `assert [entrada["id"] for entrada in corpo] == [str(minha.id)]` (igualdade de lista: prova a **ausência** da alheia, não só a presença da própria) | ✅ PASS |

### API-12 — Fila e decisão do administrador

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | 200 ordenado por `criadoEm` **crescente** | `tests/e2e/test_fila_de_solicitacoes.py:82-88` — `assert [entrada["titulo"] for entrada in resposta.get_json()] == [...]` (ordem exata) | ✅ PASS |
| AC2 | com `status`, só aquela situação; sem, todas | `:116` — `assert [entrada["titulo"] for entrada in corpo] == ["Pendente"]`; `:128-133` — lista das três situações | ✅ PASS |
| AC3 | 200 `{solicitacao, evento}`, `aprovada` + `decididoPorId`/`decididoEm`, evento `aprovado` | `tests/e2e/test_aprovacao_de_solicitacao.py:86-91` — `assert set(corpo) == {"solicitacao","evento"}`; `assert corpo["solicitacao"]["decididoPorId"] == str(administrador.id)`; `assert corpo["evento"]["situacao"] == "aprovado"` | ✅ PASS |
| AC4 | padrões `aberta` / `1` / `false` / `1` e `versao: 1` | `:135`, `:146`, `:157`, `:168`, `:179` — um teste por padrão, cada um com o **valor exato** (`is False`, `== 1`) | ✅ PASS |
| AC5 | 200 `recusada` + `motivoRecusa` + `decididoPorId` + `decididoEm` | `tests/e2e/test_recusa_de_solicitacao.py:87-90` — `assert corpo["motivoRecusa"] == "Fora do escopo institucional."` (valor, não presença) | ✅ PASS |
| AC6 | 422 `campos.motivo` em solicitação **pendente** | `:120-124` (ausente) e `:135-137` (vazio) — ambos afirmam também `situacao == "pendente"` depois | ✅ PASS |
| **AC6b** | **409 tem precedência sobre 422 em solicitação já decidida** | `tests/e2e/test_recusa_de_solicitacao.py:269-273` — `assert resposta.status_code == 409`; `assert corpo["codigo"] == "solicitacao_ja_decidida"`; **`assert "campos" not in corpo`** (prova a precedência, não só o código). Contraprova em `:276-289` (pendente sem motivo continua 422) | ✅ PASS |
| AC7 | 409 com `decididoPorId`, `decididoEm`, `situacao` além do envelope | aprovar: `test_aprovacao_de_solicitacao.py:198-203` — `assert corpo["decididoEm"] == "2026-04-01T12:00:00Z"` (valor literal); recusar: `test_recusa_de_solicitacao.py:160-165` | ✅ PASS |
| AC8 | 404 `solicitacao_inexistente` | `test_aprovacao_de_solicitacao.py:226-227`; `test_recusa_de_solicitacao.py:200-201` | ✅ PASS |

### API-13 — Efeitos da aprovação (AD-009)

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | participação ativa `chair` para o solicitante | `tests/integracao/eventos/test_efeitos_da_aprovacao.py:86` — `assert papeis(evento.id, solicitante.id) == ["chair"]`; visível em `/me/participacoes` em `:97-98` | ✅ PASS |
| AC2 | participação `chair` para chair inicial **com** conta | `:112-113` — `assert papeis(evento.id, ana.id) == ["chair"]`; `assert convites_de(evento.id, "ana@exemplo.test") == []` (afirma também o que **não** deve existir) | ✅ PASS |
| AC3 | convite pendente, `tipo: "participacao"`, sem `submissaoTitulo` (D3), e-mail disparado | `:127-133` — `assert convites[0].tipo == "participacao"`; `assert convites[0].papel == "chair"`; `assert convites[0].situacao == "pendente"`; `assert convites[0].submissao_id is None`; e-mail em `:150-151` | ✅ PASS |
| AC4 | falha ⇒ nada persiste (mesma transação, AD-019) | `:245-248` — `assert contar(Evento) == eventos_antes`; idem `ParticipacaoEvento` e `Convite` | ✅ PASS |
| AC5 | e-mail que falha não desfaz a aprovação; registro fica `falha` | `:278-288` — `assert solicitacao_decidida.situacao == "aprovada"`; `assert registro.situacao == "falha"` | ✅ PASS |
| AC6 | e-mail repetido ⇒ um efeito só | `:195` — `assert participacoes == 1`; `:205-214` (solicitante repetido) | ✅ PASS |
| Edge Case | reprocessamento não duplica participação | `:312-314` — `assert total == 2`; `:327` — `assert len(convites_de(...)) == 1` | ✅ PASS |
| Edge Case | duas aprovações simultâneas ⇒ um evento só | `tests/e2e/test_aprovacao_de_solicitacao.py:335-345` — `assert len(conflitos) == 1`; `assert conflitos[0].codigo == "solicitacao_ja_decidida"`; `assert eventos == 1` | ✅ PASS |

### API-14 — Leitura, edição e concorrência do evento

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | 200 evento completo; 404 `evento_inexistente` | `tests/e2e/test_leitura_de_evento.py:23-40` — 18 asserções de valor campo a campo (`titulo`, `fuso`, `dataInicio`, `avaliadoresPorSubmissao == 1`, `rebuttalHabilitado is False`, `versao == 1`); 404 em `:48-49` | ✅ PASS |
| AC2 | resolve por identificador **sem exigir participação**; 404 | `:70-80` — `test_a_leitura_por_identificador_nao_exige_participacao_no_evento`, `assert resposta.status_code == 200`; 404 em `:88-89` | ✅ PASS |
| AC3 | 200, alterações aplicadas, `versao` +1 | `tests/e2e/test_edicao_de_evento.py:43-44` — `assert corpo["versao"] == 2`; persistência em `:58-59` — `assert gravado.versao == 2` | ✅ PASS |
| AC4 (D2) | 409 `conflito_de_versao` com o registro atual **em `atual`** | `tests/e2e/test_edicao_de_evento.py:79-84` — `assert corpo["codigo"] == "conflito_de_versao"`; `assert corpo["atual"]["id"] == str(evento.id)`; `assert corpo["atual"]["titulo"] == "Título Vigente"`; `assert corpo["atual"]["versao"] == 1`. Estado inalterado em `:98-99` | ✅ PASS |
| AC5 | 422 `campos.avaliadoresPorSubmissao` | `:115-118` | ✅ PASS |
| AC6 | 422 `campos.prazoRebuttalDias` | `:134-135`; contraprova (com prazo ⇒ 200 e `prazoRebuttalDias == 7`) em `:148-151` | ✅ PASS |
| AC7 | 422 `campos.maximoDeRodadas` | `:167-168` | ✅ PASS |
| AC8 | 200 `{descendentes: [...]}` com **toda a árvore** | `tests/e2e/test_descendentes_de_evento.py:28-29` — `assert set(corpo["descendentes"]) == {str(filho.id), str(neto.id), str(bisneto.id)}` (três níveis, conjunto exato); exclusões em `:40` e `:52-53` | ✅ PASS |
| **AC9** | **422 `campos.eventoPaiId` quando o pai é descendente do próprio evento** | `tests/e2e/test_edicao_de_evento.py:222-224` — `assert resposta.status_code == 422`; `assert "eventoPaiId" in resposta.get_json()["campos"]`; `assert EventoRepository.por_id(evento.id).evento_pai_id is None`. Contraprova (fora da árvore ⇒ 200) em `:240-241`. Unitários em `tests/integracao/eventos/test_deteccao_de_ciclo.py:25,36,47,56` | ✅ PASS — **travessia agora alcançável** (ver M1) |
| Edge Case | ciclo em dados legados termina, cada evento uma vez | `tests/e2e/test_descendentes_de_evento.py:88-93` — `assert sorted(descendentes) == sorted([str(b.id), str(c.id)])`; `assert len(descendentes) == len(set(descendentes))`; unitário em `test_deteccao_de_ciclo.py:64` | ✅ PASS |
| Edge Case | `identificadorPagina` de evento **publicado** ⇒ 422 | `tests/e2e/test_edicao_de_evento.py:184-186` — 422 + campo + `assert EventoRepository.por_id(evento.id).identificador_pagina == "ja-divulgado"`; contraprova (aprovado ⇒ 200) em `:200-201` | ✅ PASS |
| AD-008 | 403 `sem_permissao`, com precedência sobre 404 | `:255-257` (não-chair), `:268-269` (**inexistente + sem permissão ⇒ 403, não 404**), `:281-282` (inexistente + admin ⇒ 404), `:297-298` (inexistente + corpo inválido ⇒ 404, não 422) | ✅ PASS |

### API-15 — Trilhas

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | 200 com `id`, `eventoId`, `nome`, `descricao`, `ativa`, `submissoesVinculadas` | `tests/e2e/test_trilhas.py:61-64` (campos com valor) + `:89` (`submissoesVinculadas == 0`) e `:103` (`== 1`) | ✅ PASS |
| AC2 | 201, `ativa: true`, `submissoesVinculadas: 0` | `:121-125` — `assert corpo["ativa"] is True`; `assert corpo["submissoesVinculadas"] == 0` | ✅ PASS |
| AC3 | 422 `campos.nome` | `:151-154` | ✅ PASS |
| AC4 | 200 com `submissoesVinculadas` atualizado | `:201-205` (aplica e persiste) e `:237-241` (contagem no PATCH) | ✅ PASS |
| AC5 | desativar com submissões é **permitido**, devolve a contagem | `:237-241` — `assert resposta.status_code == 200`; `assert corpo["ativa"] is False`; `assert corpo["submissoesVinculadas"] == 1`; `assert db.session.get(Trilha, trilha.id).ativa is False` | ✅ PASS |
| AC6 | 404 `trilha_inexistente` | `:254-255`; e `:268-269` (inexistente + corpo inválido ⇒ 404) | ✅ PASS |
| AC7 | 422 `campos.nome` para nome repetido no mesmo evento | `:169-170` (criação), `:218-219` (edição); contraprova (outro evento ⇒ 201) em `:183-184` | ✅ PASS |
| AD-008 | 403 nas três operações | `:282-283`, `:295-296`, `:309-311` | ✅ PASS |

### API-16 — Chamadas, prorrogação e encerramento

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | 200 com as chamadas do evento | `tests/e2e/test_chamadas.py:44-47` + isolamento por evento em `:58` | ✅ PASS |
| AC2 | 201, `encerradaManualmente: false`, `versao: 1` | `:74-77` — `assert corpo["encerradaManualmente"] is False`; `assert corpo["versao"] == 1` | ✅ PASS |
| AC3 | 422 `campos.dataLimite` — criação **e** edição, `<=` | `:105-108` (anterior), `:121-122` (**igual** — a fronteira), `:136-138` (edição, com `versao == 1` intacta) | ✅ PASS |
| AC4 (D2) | 409 `conflito_de_versao` com a chamada atual em `atual` | `:159-163` — `assert corpo["atual"]["titulo"] == "Título Vigente"`; `assert corpo["atual"]["versao"] == 1`; estado intacto no banco | ✅ PASS |
| AC5 | `versao` +1 no PATCH bem-sucedido | `:183-184` — `assert corpo["versao"] == 2`; `assert db.session.get(Chamada, chamada.id).versao == 2` | ✅ PASS |
| AC6 | prorrogar para data posterior: atualiza, `versao` +1, 200 | `tests/e2e/test_prorrogacao_de_chamada.py:46-50` — `assert corpo["dataLimite"] == POSTERIOR`; `assert gravada.data_limite == datetime(2026, 3, 1, tzinfo=timezone.utc)`; `assert gravada.versao == 2` | ✅ PASS |
| AC7 | 422 `campos.dataLimite` — anterior, **igual**, ou ausente; nunca encurta | `:67-73` (anterior, com `data_limite`/`versao` intactas), `:87-89` (**igual**), `:101-103` (ausente) | ✅ PASS |
| AC8 | `encerradaManualmente: true`, `versao` +1, 200 | `:120-124` — `assert corpo["encerradaManualmente"] is True`; `assert corpo["versao"] == 2`; persistido | ✅ PASS |
| AC9 | 422 `campos.tamanhoMaximoMb` acima do teto | `tests/e2e/test_chamadas.py:203-204` (acima), `:236-237` (edição); **fronteira** em `:218-219` — `assert resposta.status_code == 201`; `assert resposta.get_json()["tamanhoMaximoMb"] == no_limite` | ✅ PASS |
| AC10 | 404 `chamada_inexistente` | `test_chamadas.py:250-251`, `:264-265`; `test_prorrogacao_de_chamada.py:137-138`, `:149-150`, `:159-160` | ✅ PASS |
| AD-008 | 403 em listar/criar/editar/prorrogar/encerrar | `test_chamadas.py:278-279`, `:289-290`, `:303-305`; `test_prorrogacao_de_chamada.py:176-178`, `:189-191` | ✅ PASS |

### API-17 — Critérios de avaliação

| AC | Desfecho definido pela spec | `arquivo:linha` + asserção | Resultado |
| -- | --------------------------- | -------------------------- | --------- |
| AC1 | 200 com `notaMinima`, `notaMaxima`, `peso`, `ordem`, `ativo`, `temNotas` | `tests/e2e/test_criterios.py:48-52` (valores exatos) + `:73` (`temNotas is False`) e `:85` (`is True`) | ✅ PASS |
| AC2 | 201, `ativo: true`, `temNotas: false` | `:101-107` — `assert corpo["ativo"] is True`; `assert corpo["temNotas"] is False` | ✅ PASS |
| AC3 | 422 `campos.notaMaxima` — criação e edição, `<=` | `:135-138` (menor), `:151-152` (**igual**), `:166-168` (edição, com valor gravado intacto) | ✅ PASS |
| AC4 | 422 `campos.peso` — criação e edição, `<= 0` | `:182-183` (zero), `:194-195` (negativo), `:207-209` (edição, com `peso == 1` intacto) | ✅ PASS |
| AC5 | **204 sem corpo** e linha removida | `tests/e2e/test_exclusao_de_criterio.py:31-32` — `assert resposta.status_code == 204`; **`assert resposta.get_data() == b""`**; `:42` — `assert db.session.get(CriterioAvaliacao, criterio.id) is None` | ✅ PASS |
| AC6 | 409 `criterio_com_notas` + `acaoSugerida: "desativar"` | `:60-65` — `assert corpo["codigo"] == "criterio_com_notas"`; **`assert corpo["acaoSugerida"] == "desativar"`** (valor); `:76` — linha preservada | ✅ PASS |
| AC7 | 404 `criterio_inexistente` | `test_criterios.py:302-303`, `:316-317`; `test_exclusao_de_criterio.py:88-89` | ✅ PASS |
| AC8 | `ordem` ausente ⇒ próxima posição livre **dentro daquele evento** | `test_criterios.py:244` (`== 1` em evento vazio), `:257` (`== 3`), `:278` (**não vaza entre eventos**: `== 1`), `:289` (informada é respeitada: `== 7`) | ✅ PASS |
| AD-008 | 403 em listar/criar/editar/excluir, incl. precedência sobre 404 | `test_criterios.py:330-331`, `:343-344`, `:357-359`; `test_exclusao_de_criterio.py:103-105`, **`:116-117`** (inexistente + sem permissão ⇒ 403) | ✅ PASS |

**Total**: **62 ACs/critérios rastreados** — 61 com `arquivo:linha` e valor conferido, **1 sem
evidência** (API-11 AC5b). **0 lacunas de precisão de spec** nas Fases 5+6: onde a spec nomeia
um código, um campo ou um valor, a asserção correspondente mira o valor, não a presença.

---

## Regra de payload / conjunção

Varredura de todo campo nomeado em corpo de resposta pelas ACs em escopo. Nenhum caso de
asserção que se contenta com presença de chave ou com a chamada da função:

- `situacao`, `versao`, `solicitanteId`, `decididoPorId`, `decididoEm`, `motivoRecusa`,
  `identificadorPagina`, `modeloDeAvaliacao`, `avaliadoresPorSubmissao`, `rebuttalHabilitado`,
  `maximoDeRodadas`, `prazoRebuttalDias`, `encerradaManualmente`, `dataLimite`, `tamanhoMaximoMb`,
  `ativa`, `submissoesVinculadas`, `ativo`, `temNotas`, `ordem`, `peso`, `notaMinima`,
  `notaMaxima`, `acaoSugerida`, `atual.{id,titulo,versao}` — **todos comparados por igualdade a
  um valor literal** (ou `is True` / `is False` para booleanos, evitando o truthiness frouxo).
- `campos.*` do 422 é o único caso legítimo de teste de pertinência (`"x" in corpo["campos"]`),
  porque a spec define o **nome do campo**, não a mensagem. Reforçado onde importa: AC4 de
  API-11 afirma também `"dataInicio" not in campos`, e AC6b afirma `"campos" not in corpo`.
- `correlacao` e `mensagem` são checados por presença — correto, a spec não fixa valor
  (`correlacao` é UUID por requisição por decisão registrada).

---

## Sensor de discriminação

Método: mutação aplicada ao arquivo real, cópia de segurança fora da árvore, subconjunto de
testes executado, arquivo restaurado imediatamente. Verificação de árvore limpa (`git status
--porcelain` vazio) após as rodadas e ao fim. **Nenhuma mutação permaneceu na árvore.**

| # | Arquivo:linha | Mutação | Testes mortos | Morto? |
| - | ------------- | ------- | ------------- | ------ |
| M1 | `app/modules/eventos/services/solicitacao.py:325-335` | **Travessia de detecção de ciclo apagada** (corpo do `while` trocado por `return`) — a mutação que **sobreviveu na Fase 5** | 4, incluindo **`test_edicao_de_evento.py::test_apontar_o_pai_para_um_descendente_do_proprio_evento_responde_422`** (e2e, via rota) + 3 unitários de `test_deteccao_de_ciclo.py` | ✅ **Morto** |
| M2 | `app/modules/eventos/services/evento.py:66` | `fila.append(filho_id)` → `pass` (a BFS vira busca de filhos diretos: sem netos) | `test_descendentes_de_evento.py` — árvore de 3 níveis e ciclo legado | ✅ Morto |
| M3 | `app/modules/eventos/services/evento.py:80` | Lock otimista do evento desligado (`if evento.versao != versao` → `if False`) | 409 `conflito_de_versao` + "não altera o evento" | ✅ Morto |
| M4 | `app/modules/eventos/services/evento.py:109` | `evento.versao += 1` → `+= 0` | incremento de versão + persistência | ✅ Morto |
| M5 | `app/modules/eventos/services/chamada.py:101` | Guarda de prorrogação removida (**prorrogar passa a poder encurtar prazo**) | data anterior **e** data igual (a fronteira `<=`) | ✅ Morto |
| M6 | `app/modules/eventos/services/chamada.py:124` | **Fronteira de `tamanhoMaximoMb`**: `>` → `>=` (off-by-one no teto) | `test_tamanho_maximo_no_limite_do_servidor_e_aceito` | ✅ Morto |
| M7 | `app/modules/eventos/services/criterio.py:129` | Campo derivado `temNotas` fixado em `False` | `test_tem_notas_e_verdadeiro_com_nota_registrada` | ✅ Morto |
| M8 | `app/modules/eventos/services/criterio.py:89` | Bloqueio de exclusão por notas desligado (`if False`) | 409 `criterio_com_notas` + linha preservada | ✅ Morto |
| M9 | `app/modules/eventos/services/trilha.py:75` | Campo derivado `submissoesVinculadas` fixado em `0` | contagem na listagem + contagem ao desativar | ✅ Morto |
| M10 | `app/modules/eventos/controllers/eventos.py:47` | **RBAC removido do `PATCH /eventos/{id}`** (`@exige_acao` → `@exige_autenticacao`) — ataca AD-008 e a precedência 403-antes-404 | 403 do não-chair **e** 403 em evento inexistente | ✅ Morto |
| M11 | `app/modules/eventos/controllers/solicitacoes.py:123-126` | **Precedência invertida**: corpo validado antes do estado (422 passaria na frente do 409) | `test_recusa_ja_decidida_e_sem_motivo_responde_409_e_nao_422` | ✅ Morto |
| M12 | `app/modules/eventos/services/solicitacao.py:141` | Guarda `solicitacao_ja_decidida` desligada | **8 testes** em 3 arquivos, incluindo a corrida de duas aprovações simultâneas | ✅ Morto |
| M13 | `app/modules/eventos/controllers/solicitacoes.py:50` | Checagem de dono da solicitação removida | `test_a_edicao_por_quem_nao_e_o_solicitante_responde_403` | ✅ Morto |

**Profundidade**: P0-full (13 mutações, acima do mínimo de 5, cobrindo todos os alvos de maior
risco nomeados no escopo).
**Resultado**: **13 injetadas, 13 mortas, 0 sobreviventes**.

### M1 — a sobrevivente da Fase 5 está morta

A Fase 5 registrou um mutante sobrevivente: a travessia de detecção de ciclo era inalcançável
por qualquer rota, e apagá-la inteira deixava os 165 testes e2e verdes. **Confirmado que a Fase 6
resolveu isso**: com a travessia apagada, `test_edicao_de_evento.py::test_apontar_o_pai_para_um_descendente_do_proprio_evento_responde_422`
falha — o consumidor real (`PATCH /eventos/{id}`, `app/modules/eventos/services/evento.py:99-103`)
exercita a função por HTTP, e não só os unitários. A AC foi movida para a operação onde é de fato
alcançável (API-14 AC9) e o teste e2e a ancora. **Não sobreviveu de novo.**

---

## Auditoria do conserto de `fixar()` (infraestrutura de teste)

`tests/e2e/apoio_de_eventos.py:79-89` passou a comitar o cenário (`db.session.commit()`, que sob
a fixture `sessao` é liberação de savepoint dentro da transação externa do teste, ainda desfeita
no fim por `tests/conftest.py:85-107`). Sem isso, uma requisição que termina em erro faz
`transacao()` desfazer a transação e leva junto o cenário apenas `flush`ado — asserções de
"o estado não mudou" encontrariam a linha ausente e provariam o desfecho errado.

**Varredura de resíduo — nenhum teste do intervalo prova o desfecho errado por cenário não fixado:**

1. **Fase 6** (`apoio_de_eventos.py`, `apoio_de_chamadas.py`, `apoio_de_criterios.py`): todos os
   cenários passam por `fixar()`. O único `db.session.flush()` restante,
   `tests/e2e/test_trilhas.py:43`, é intermediário (obter o `chamada.id` antes de inserir a
   `Submissao`) e é seguido por `fixar()` na linha 44 — não é resíduo.
2. **Fase 5** (`test_minhas_solicitacoes.py`, `test_recusa_de_solicitacao.py`,
   `test_aprovacao_de_solicitacao.py`, `test_solicitacoes_evento.py`): os helpers **não** comitam.
   Verificado empiricamente que isso **não** produz asserção vácua nesses arquivos: sob M12 e M13
   — as duas mutações que fazem exatamente o caminho de erro desses testes mudar de comportamento —
   as asserções de "o estado não mudou" (`test_a_edicao_de_solicitacao_ja_decidida_nao_altera_nada`,
   `test_a_edicao_por_quem_nao_e_o_solicitante_responde_403`) **falharam**, e falharam por
   comparação de valor, não por `AttributeError` em `None`. A linha sobrevive porque as recusas de
   estado e de autorização desses caminhos são levantadas **fora** de `transacao()`
   (`app/modules/eventos/controllers/solicitacoes.py:50` e `:123-126`), então não há `rollback()`
   para levar o cenário junto. **0 resíduos.**

---

## Qualidade de código

| Princípio | Status |
| --------- | ------ |
| Sem funcionalidade além do pedido | ✅ |
| Sem abstração para uso único | ✅ — services por agregado, sem camada de "manager" genérica |
| Sem "flexibilidade" desnecessária | ✅ |
| Só arquivos necessários tocados | ✅ — 40 arquivos, todos em `app/modules/eventos`, `app/core`, `tests` e `.specs` |
| Não "melhorou" código alheio | ✅ |
| Segue os padrões existentes | ✅ — controller fino, service com a regra, repository com a consulta; AD-019 respeitado (nenhum `commit()` em repository) |
| Testes mapeiam ACs, não a implementação | ✅ — cada arquivo de teste tem comentários `# ACn — ...` ancorando o bloco |
| Checagem ancorada na spec (valor, não presença) | ✅ — ver seção de payload |
| Cobertura por camada (domínio 1:1; rotas feliz+borda+erro) | ✅ — toda rota em escopo tem 2xx, 4xx de validação, 403, 404 e 401 |
| Todo teste mapeia a uma AC / edge case / "Done when" | ✅ — nenhum teste órfão encontrado nos 20 arquivos do intervalo |
| Diretriz de projeto documentada seguida | ✅ — AD-008, AD-009, AD-012, AD-014 D2 e AD-019 conferidas uma a uma |

**Ressalva menor (não é AC)**: o docstring de `app/modules/eventos/controllers/eventos.py:50-55`
afirma "depois o 409 de versão; só então o corpo é validado", mas o código (linhas 64-66) valida
o corpo **antes** de `exigir_versao`. Nenhuma AC define esse desfecho combinado (corpo inválido +
versão obsoleta), então não é falha — mas o comentário descreve uma ordem que o código não tem.
Vale corrigir o comentário ou o código, para que o próximo leitor não confie na promessa errada.

---

## Lacuna ordenada por gravidade

### L2 (Fases 5+6) — Blocker: API-11 AC5 aceita evento pai **não aprovado**

- **AC**: API-11 AC5 — "WHEN `eventoPaiId` aponta para um evento inexistente **ou não aprovado**
  THEN a API SHALL responder 422 com `campos.eventoPaiId` preenchido."
- **Evidência de cobertura**: **nenhuma**. Busca feita em toda `tests/` por `pendente_aprovacao`,
  `nao_aprovado` e por construção de evento pai em outra situação: o único helper que cria pai,
  `tests/e2e/test_solicitacoes_evento.py:47-54`, fixa `situacao="aprovado"`. A metade
  "não aprovado" da AC nunca é exercitada.
- **Defeito de comportamento confirmado**: `app/modules/eventos/services/solicitacao.py:318-320`
  recusa apenas `pai is None`; a situação do pai nunca é consultada.

  ```python
  pai = EventoRepository.por_id(evento_pai_id)
  if pai is None:
      raise ErroDeValidacao({"eventoPaiId": MENSAGEM_DE_PAI_INEXISTENTE})
  ```

  `pendente_aprovacao` é estado real e alcançável do `evento_situacao_enum`
  (`app/modules/enums.py:19-25`).
- **Prova empírica** (sonda descartável, criada, executada e **removida**; árvore verificada
  limpa depois): `POST /api/solicitacoes-evento` com `eventoPaiId` apontando para um evento em
  `situacao="pendente_aprovacao"` respondeu **201**, ecoando o `eventoPaiId` no corpo, onde a
  spec exige **422** com `campos.eventoPaiId`.
- **Impacto**: uma solicitação pode nascer pendurada numa hierarquia que ainda não foi aprovada;
  se o pai for recusado, a árvore fica com aresta para um evento que nunca existirá como aprovado.
- **Conserto** (para outro agente — o verificador não corrige): acrescentar em
  `validar_evento_pai` a recusa de `pai.situacao` fora do conjunto aprovado, e um teste e2e em
  `tests/e2e/test_solicitacoes_evento.py` que crie o pai em `pendente_aprovacao` e afirme
  `422` + `"eventoPaiId" in campos`. Vale também cobrir a mesma regra em `PATCH /eventos/{id}`,
  que reusa a mesma função.
- **Prioridade**: **Blocker** — é AC de P1 com defeito de comportamento reproduzido, não apenas
  falta de teste.

**Nota sobre L1 (Fase 5)**: a lacuna L1 do relatório anterior (o desfecho de editar solicitação
já decidida, sem decisão de spec) **foi fechada no intervalo**: a spec ganhou API-11 AC7 com
`409 solicitacao_ja_decidida`, o teste existe em `tests/e2e/test_minhas_solicitacoes.py:110-124`,
e o mutante correspondente (M12) está morto.

---

## Atualização de rastreabilidade

| Requisito | Status anterior | Novo status |
| --------- | --------------- | ----------- |
| API-11 | Pending | ❌ **Needs Fix** — AC1..AC4, AC5a, AC6..AC8 verificadas; **AC5b falha** |
| API-12 | Pending | ✅ Verified (AC1..AC8 + AC6b) |
| API-13 | Pending | ✅ Verified (AC1..AC6 + 2 edge cases) |
| API-14 | Pending | ✅ Verified (AC1..AC9 + 2 edge cases) |
| API-15 | Pending | ✅ Verified (AC1..AC7) |
| API-16 | Pending | ✅ Verified (AC1..AC10) |
| API-17 | Pending | ✅ Verified (AC1..AC8) |

---

### Resumo — Fases 5+6

- **Veredito**: ❌ **FAIL** por uma lacuna (L2), Blocker, com defeito reproduzido.
- **Checagem ancorada na spec**: **61/62** ACs com desfecho conferido contra o valor que a spec
  define; **1** sem evidência e com comportamento errado; **0** lacunas de precisão de spec.
- **Gate**: pytest **509 passed / 0 failed**, exit **0** · ruff exit **0** · `flask db upgrade` exit **0**.
- **Sensor**: **13 mutações, 13 mortas, 0 sobreviventes** (profundidade P0-full).
- **Sobrevivente da Fase 5**: **morta** — a travessia de ciclo é alcançável por `PATCH /eventos/{id}`
  e um teste e2e a mata.
- **Conserto de `fixar()`**: auditado; **nenhum** teste do intervalo prova o desfecho errado por
  cenário não fixado.
- **Árvore**: **limpa** (`git status --porcelain` vazio), sem mutação residual, suíte restaurada
  em 509 passed.
