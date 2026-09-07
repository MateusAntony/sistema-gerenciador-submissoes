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
