# Roadmap — IAnalisys Saúde

## Sistema de referência analisado

**URL:** https://fprime.analisys.info/parente/  
**Stack atual:** PHP monolítico, single-tenant, sem IA, sem Conta Azul  
**Status:** Funcional, dados reais da Clinicorp API, sem autenticação robusta

O sistema atual (SIG 2026) é a versão 1 — single-tenant, sem IA, sem controle de acesso por papel, 
sem dados financeiros integrados. O IAnalisys Saúde é a versão SaaS, multi-tenant, com IA e 
arquitetura profissional.

---

## O que o sistema atual entrega

### Módulos existentes (8 abas)

| Aba | KPIs atuais | Visualizações |
|---|---|---|
| Visão Geral | Entradas, Saídas, Saldo, Consultas, Absenteísmo, Ticket Médio | Gráfico de barras por dia, comparativo financeiro |
| Financeiro | Entradas/Saídas realizadas vs previsão, Saldo Líquido, por forma de pagamento | Realizado vs Previsão, Por Forma de Pagamento |
| Agendamentos | Total, Confirmadas (%), Faltas (%), Canceladas (%) | Consultas por dia, por profissional |
| Pacientes | Aniversariantes do período | Lista simples |
| Orçamentos | Valor Total, Ticket Médio, Aprovados (% conversão) | Top Procedimentos, Lista de orçamentos |
| Vendas | Conversão de Orçamentos, Receita por Especialidade | Gráficos de conversão |
| CRM | Campanhas Ativas | Vazio no momento |
| Operacional | Metas de Vendas, Falhas de Metas | Vazio no momento |

### Limitações do sistema atual

- Single-tenant (hardcoded para Parente Odontologia)
- PHP sem arquitetura em camadas
- Sem autenticação por papéis
- Sem integração Conta Azul (apenas Clinicorp)
- Sem IA
- Sem pipeline de dados (acessa API diretamente na view)
- Sem histórico acumulado (cada consulta vai direto à API)
- Sem controle de tokens ou custos
- Sem LGPD

---

## O que o IAnalisys Saúde precisa entregar

### Princípio de ouro

> Tudo que o sistema atual faz, o IAnalisys faz melhor.
> Mais: multi-tenant, IA, Conta Azul, papéis, pipeline de dados, LGPD.

---

## Fases de desenvolvimento

---

### FASE 1 — Fundação (concluída)

**Objetivo:** Base técnica sólida, sem lógica de negócio.

- [x] Estrutura de pastas (backend + frontend)
- [x] Docker Compose (MySQL, Redis, backend, frontend)
- [x] FastAPI rodando com rota /health
- [x] SQLAlchemy async configurado
- [x] Alembic configurado
- [x] Models: Tenant, User, Role, UserTenant
- [x] Migration inicial com seed de papéis
- [x] .env.example, README, docs

---

### FASE 2 — Autenticação e Multi-tenant ✅ (concluída)

**Objetivo:** Usuário consegue fazer login, sistema sabe de qual tenant ele é.

#### Backend

- [x] `POST /auth/login` — retorna JWT
- [x] `POST /auth/refresh` — renova token
- [x] `GET /auth/me` — dados do usuário logado
- [x] Dependency `get_current_user` com tenant_id
- [x] Hash de senha com bcrypt
- [x] Controle de papéis (saas_admin vs tenant roles)

#### Schemas Pydantic

- [x] UserLogin, UserMe
- [x] TokenResponse

#### Banco

- [x] `is_saas_admin` adicionado ao model User (migration 0002)

#### Frontend auth ✅ (concluído)

- [x] Página de login (React) — `modules/auth/LoginPage.tsx`
- [x] Context de autenticação — `modules/auth/AuthContext.tsx`
- [x] Hook `useAuth`
- [x] Proteção de rotas — `components/common/PrivateRoute.tsx`

#### Pendente — Recuperação de senha (PR-12 — próximo)

- [ ] Migration `password_reset_tokens` (user_id, token_hash, expires_at, used_at)
- [ ] Endpoints `POST /auth/password-reset/{request,confirm}`
- [ ] Service de email via SMTP Gmail (app password no `.env`)
- [ ] Páginas `/auth/recuperar-senha` e `/auth/redefinir-senha?token=...`
- [ ] Link "Esqueci minha senha" no `LoginPage`
- [ ] Migrar para Sendgrid/Resend/Mailgun em produção (Gmail tem limite 500/dia)

---

### FASE 3 — Pipeline de dados (Clinicorp) ✅ (staging completo, record-level)

**Objetivo:** Dados da Clinicorp entram no banco, limpos e organizados.

#### Decisões de arquitetura (atualizado em 2026-05-02)

A migration 0003 (snapshot por intervalo) foi **descartada** e substituída pela 0005:
- Schema antigo guardava 1 linha por requisição com JSON do intervalo inteiro — sem dedup, sem delta.
- Schema novo guarda **1 linha por registro real**, com `UNIQUE(tenant_id, external_id)` → upsert idempotente via `INSERT ... ON DUPLICATE KEY UPDATE`.
- Re-rodar o mesmo período nunca duplica; só atualiza `raw_data` e `synced_at`.
- Auditabilidade preservada (raw_data JSON intacto) → futura IA pode citar a origem do dado.

#### Integração — Client + 23 endpoints ✅

- [x] `ClinicorpClient` (`app/integrations/clinicorp/client.py`):
  - 9 cadastros estáticos (sem período): business, users, professionals, specialties, procedures, appointment_categories, appointment_statuses, chairs, crm_campaigns
  - 6 transacionais (por período): appointments, estimates, payments, invoices, receipts, summary
  - 8 agregados (para kpis_monthly futuro): cash_flow, payments_aggregated, average_installments, appointment_info, estimates_conversion, expertise_revenue, patient_estimates, misses_goals, sales_goals, analytics

#### Staging redesenhado (migration 0005) ✅

15 tabelas `stg_cc_*` com schema uniforme:

| Estáticas (8) | Transacionais (6) | Agregada (1) |
|---|---|---|
| stg_cc_business | stg_cc_appointments | stg_cc_kpis_monthly *(reservada — PR-3)* |
| stg_cc_users | stg_cc_estimates *(JSON inclui ProcedureList)* | |
| stg_cc_professionals | stg_cc_payments | |
| stg_cc_specialties | stg_cc_invoices | |
| stg_cc_procedures | stg_cc_receipts | |
| stg_cc_appointment_categories | stg_cc_summary_entries *(lançamentos contábeis)* | |
| stg_cc_appointment_statuses | | |
| stg_cc_crm_campaigns | | |

Todas têm: `id BIGINT PK`, `tenant_id`, `external_id`, `external_updated_at`, `raw_data JSON`, `synced_at`, `sync_job_id`, `UNIQUE(tenant_id, external_id)`.

#### Controle de execução ✅

- [x] `sync_jobs` recriada com schema completo: `entity`, `period_from/to DATE`, `started_at/finished_at/duration_ms`, `records_fetched/inserted/updated`, `errors_count`, `error_message`
- [x] `sync_checkpoints` (PK = tenant + source + entity): rastreia `last_period_from/to`, `last_synced_at`, `status`, `total_records` (contagem real em staging)

#### Endpoints ✅

- [x] `POST /api/v1/sync/clinicorp/static` — sincroniza as 8 entidades estáticas em sequência
- [x] `POST /api/v1/sync/clinicorp/transactional` body `{entity, year, month}` — 1 entidade / 1 mês
- [x] `POST /api/v1/sync/clinicorp/transactional/batch` body `{year, month, entities?}` — N entidades / 1 mês
- [x] `GET /api/v1/sync/jobs` — últimos N jobs (filtro opcional por entidade)
- [x] `GET /api/v1/sync/checkpoints` — estado atual por entidade

#### Smoke-test (2026-05-02) ✅

8.499 registros importados com dados reais da Parente Odontologia:
- Cadastros estáticos: 745 registros (8 entidades)
- Abril/2024 (parcial): 4.312 registros
- Abril+Maio/2026: 4.162 registros
- Idempotência confirmada: re-rodar = 0 inserts, todos os registros viram updates

#### Concluído (PR-3 a PR-5c)

- [x] **PR-3** — `stg_cc_kpis_monthly` com 10 endpoints agregados em `asyncio.gather` (commit `41fb4d0`)
- [x] **PR-4** — Tela `/admin/sync` em React com heatmap mês × entidade (commit `aa99b36`)
- [x] **Fix** — filtro `year` em `/sync/jobs` para o heatmap não perder histórico (commit `c408ba5`)
- [x] **PR-5a** — CORE cadastros: 8 tabelas + `core_patients` reservada, mappers genéricos (commit `3fb20e8`)
- [x] **PR-5b** — CORE eventos: 7 tabelas (incl. `core_estimate_procedures` nested), 30.663 records transformados (commit `e5c1089`)
- [x] **PR-5c** — `core_patients` extraído via UNION SQL dos eventos, 2.341 pacientes únicos (commit `85d4b28`)

#### Concluído (continuação)

- [x] **PR-9c** — Botão "Reconstruir CORE+ANALYTICS" na tela `/admin/sync` (orquestra `transform/all` + `analytics/rebuild/all`, ~25s, idempotente)

#### Pendente

- [ ] Sync incremental com delta por `external_updated_at` (campos: `LastChange_Date`, `z_LastChange_Date`, `ModifiedDate`)
- [ ] APScheduler para sync automático recorrente

---

### FASE 4 — Pipeline de dados (Conta Azul) 🟡 (4a/4b/4c ✅ done · 4d/4e/4f pendentes)

**Objetivo:** Dados financeiros reais entram no banco, separados do Clinicorp. Conta Azul é fonte canônica do realizado bancário (entradas + saídas + categorias). Clinicorp continua como fonte canônica do vínculo paciente↔consulta↔valor.

#### OAuth e conexão ✅

- [x] OAuth 2.0 Authorization Code Flow (Cognito-backed)
- [x] `contaazul_tokens` — token por tenant (migration 0004), unique constraint tenant_id
- [x] Endpoints `/contaazul/{status,auth,callback,refresh,disconnect}`

#### Endpoints reais validados em produção (memória `reference_contaazul_v1.md`)

> **NOTA IMPORTANTE:** o `client.py` atual da V2 lista endpoints incorretos (`accounts_receivable`, `financial_movements` etc.). Os endpoints REAIS começam com `/v1/...` apesar do base ser `api-v2.contaazul.com`. Vamos descartar o que está no client.py e refazer baseado no v1 PHP.

| Endpoint | Volume Parente | Função |
|---|---:|---|
| `GET /v1/financeiro/eventos-financeiros/contas-a-receber/buscar` | 530 | Receitas |
| `GET /v1/financeiro/eventos-financeiros/contas-a-pagar/buscar` | 631 | Despesas (Clinicorp não tem!) |
| `GET /v1/pessoas` | 1.389 | Clientes + fornecedores (perfis array) |
| `GET /v1/produtos` | 961 | Estoque + custo médio |
| `GET /v1/servico` | 10 | Serviços odontológicos |
| `GET /v1/venda/vendedores` | 6 | Match com profissional |

**Pegadinhas conhecidas** (em `reference_contaazul_v1.md`):
- Convenção de wrapper inconsistente (`{itens, itens_totais}` vs `{items, totalItems}` vs array puro)
- `status_traduzido` já vem em PT-BR
- Totalizadores `{pago, vencido, vence_hoje, pendente, aberto}` agregados pela API no payload de eventos
- `perfis` é array — pessoa pode ser cliente E fornecedor

#### Plano de execução — divisão em sub-PRs

**Sub-PR 4a: Refazer `client.py` + smoke-test dos 6 endpoints** ✅ `fdf08cb`
- Endpoints reais `/v1/...` validados em produção
- `_REQUIRED_JSON_HEADERS` (Content-Type + Accept obrigatórios pra evitar 401 do gateway)
- Param de paginação corrigido: `tamanho_pagina` (não `limite` — v1 PHP nunca trazia mais de 10 itens por causa disso)
- Tratamento explícito de `429 Rate limit` com mensagem clara
- `backend/scripts/smoke_test_contaazul.py` reproduz hits nos 6 endpoints

**Sub-PR 4b: Migration 0015 — staging Conta Azul** ✅ `fdf08cb`
- 6 tabelas `stg_ca_*` (pessoas, produtos, servicos, vendedores, contas_receber, contas_pagar)
- Schema mínimo: id BigInt PK, tenant_id, external_id, external_updated_at, raw_data JSON, synced_at, sync_job_id
- UNIQUE(tenant_id, external_id) pra idempotência via INSERT...ON DUPLICATE KEY UPDATE
- Models em `app/models/staging_contaazul.py` com helper `_staging_columns()`

**Sub-PR 4c: Sync workers + endpoints + tela** ✅ `fdf08cb`
- `app/integrations/contaazul/sync_service.py` (espelho do Clinicorp): `_get_authenticated_client` com refresh automático se expirar em <60s, `_paginate_static` com `tamanho_pagina=200`, `_upsert_records` em batches de 500
- `sync_all_static` (4 estáticos) + `sync_transactional_batch(year, month)` (receber + pagar)
- Endpoints `POST /sync/contaazul/{static,financial}` + `/sync/jobs?source=` + `/sync/checkpoints?source=` filtros
- Frontend: `SyncProviderPanel` parametrizado (config por source) + `SyncPage` refatorado com tabs (Clinicorp · Conta Azul) — UI 100% idêntica entre os dois

**Hotfixes 2026-05-04** ✅ `ebe323c`
- **Rate limit retry/backoff** no `client.py`: até 3 tentativas com espera 12s/36s, respeita `Retry-After`, HTTP client reusa conexão. Descoberto durante smoke-test que CA estoura quota em ~24 chamadas seguidas (não 50-100).
- **Pause distribui carga**: 0.4s entre páginas, 1s entre entidades estáticas no `sync_service.py`.
- **Tenant_id no state OAuth**: `oauth.py` ganhou `encode_state`/`decode_state` (base64url). Callback resolve tenant via state em vez de exigir `?tenant_id=` na query, redireciona pra `/admin/sync?contaazul=conectado` em sucesso.
- **App CA NOVO criado** (`client_id=67p7o6b8ptaanl3fs5uhoavpif`) com `redirect_uri=https://fprime.analisys.info/v2_callback.php` (proxy PHP). Isolado do v1 PHP — fim da disputa pelo refresh_token. App antigo deprecated.

**Sub-PR 4c+ Extensões pós-compactação 2026-05-04** ✅ `9bac0bc` (8 PRs adicionais)

Sessão de ~6h após pause/compact descobriu/corrigiu múltiplos bugs e adicionou features.

1. **🔥 Bug crítico de paginação** — `/v1/pessoas` ignorava `offset` e devolvia mesma página em loop infinito (script de bypass fez 237k chamadas com sempre os mesmos 200 IDs únicos). Causa: nosso código usava `offset`, mas a API exige **`pagina`** (1-indexed) + `tamanho_pagina`. Corrigido em `client.py:107` (`list_pessoas`) e `client.py:134` (`list_produtos`); `sync_service._paginate_static` usa `pagina += 1`.
2. **Bug `limite=` → `tamanho_pagina=`** nas transacionais — `_paginate_transactional` chamava método com kwarg errado, teria estourado `TypeError` na primeira chamada. Já com paginação real (não chamada única).
3. **Migration 0016** — 2 novas estáticas: `stg_ca_categorias` (145 registros — RECEITA/DESPESA com hierarquia pai/filho + DRE) e `stg_ca_centros_custo` (Parente não usa, 0 registros — esquema pronto). Ambas adicionadas ao `STATIC_ENTITIES` do sync_service e ao `CA_STATIC_ENTITIES`/`ENTITY_LABELS` do frontend.
4. **Rota `POST /sync/contaazul/transactional`** — permite sync individual de UMA célula no heatmap (mesma UX do CC). Antes só batch mensal. Plugada no `CONTAAZUL_CONFIG.syncEntityMonth` do frontend.
5. **Catálogo de endpoints CA v2** — `docs/11_CONTAAZUL_ENDPOINTS_CATALOG.md` cobre os 9 módulos da API (24+ endpoints), com prioridade por endpoint, casos de uso, pegadinhas. Memória `reference_contaazul_endpoints_catalog.md` aponta pra ele. **Consultar antes de implementar endpoint CA novo.** Inconsistência registrada: usamos `/v1/servico` (singular, legado/alias) vs doc oficial `/v1/servicos` (plural).
6. **Migration 0017 — empresa conectada** — 5 colunas em `contaazul_tokens` (`empresa_documento`, `empresa_razao_social`, `empresa_nome_fantasia`, `empresa_data_fundacao`, `empresa_email`) populadas via `GET /v1/pessoas/conta-conectada` no callback OAuth (best-effort, falha não derruba callback) + backfill no `/refresh` se vazio. Schema `ContaAzulStatusResponse` retorna esses 5 campos. Frontend tem `<ContaAzulConnectedBanner />` (banner verde sticky no topo da aba CA, só aparece quando conectado) com nome fantasia + CNPJ formatado + email. Backfill já feito no token atual da Parente.
7. **🚀 Delta sync** — em vez de usar `/v1/financeiro/eventos-financeiros/alteracoes` (que retorna só IDs e exigiria N+1 chamadas pra detalhar), descobri que **a busca normal de contas-receber/pagar aceita `data_alteracao_de`/`ate`** como filtro. Implementação: `client.list_contas_*` ganhou esses params opcionais; `sync_service.sync_alteracoes_recentes(hours_back)` faz **2 chamadas** (1× receber + 1× pagar) com janela de vencimento ampla (2010→2050) + filtro `data_alteracao` da janela escolhida. Mesmo schema da listagem normal, upsert idempotente no mesmo staging. Não atualiza checkpoint (delta sync não representa "estado final do mês"). Rota `POST /sync/contaazul/alteracoes`. Frontend tem banner azul "Atualizar mudanças" com select 1h/6h/24h/3d/7d/30d. Smoke-test 24h: 1.7s, 11 registros (4 receber + 7 pagar).
8. **Volumes finais Parente populados em staging:**

| Tabela | Total |
|---|---:|
| `stg_ca_pessoas` | 1.498 |
| `stg_ca_produtos` | 1.043 |
| `stg_ca_servicos` | 10 |
| `stg_ca_vendedores` | 8 |
| `stg_ca_categorias` | 145 |
| `stg_ca_centros_custo` | 0 (Parente não usa) |
| `stg_ca_contas_receber` (abr/2026) | 245 |
| `stg_ca_contas_pagar` (abr/2026) | 335 |

**Decisão arquitetural confirmada (não-codificada ainda):** seguiremos as 3 camadas (CORE + DIM + FATO) para o CA também, mesmo padrão do CC. Sem CORE, dashboard/IA ficam dependentes do JSON aninhado e inconsistente do CA. Sem DIM/FATO, KPIs ficam lentos e incomparáveis com CC.

**Sub-PR 4d: Migration 0018 — CORE Conta Azul** (~1d)
- `core_ca_eventos_financeiros` (unifica pagar+receber com `tipo` discriminator — RECEITA/DESPESA)
- `core_ca_pessoas` (cliente + fornecedor unificado, **CPF/CNPJ permite cross-link com `core_patients` do CC** ⭐)
- `core_ca_categorias` (com `categoria_pai_id` explícito pra hierarquia + `entrada_dre`)
- `core_ca_centros_custo`
- `core_ca_produtos`, `core_ca_servicos`, `core_ca_vendedores`
- Possivelmente `core_ca_rateio` se a maioria das parcelas tiver rateio múltiplo (validar distribuição real no staging antes de decidir; senão desnormaliza inline em eventos_financeiros)
- Transform staging → core idempotente

**Sub-PR 4e: Migration 0019 — Analytics CA** (~1d)
- Reusar `dim_tempo` (já existe) ✅
- Novas: `dim_pessoa_ca`, `dim_categoria_ca`, `dim_centro_custo_ca`
- `fato_caixa` (1 linha por parcela): métricas (`valor_total`, `valor_pago`, `valor_em_aberto`, `dias_atraso`, `is_pago`/`is_vencido`/`is_em_aberto`), 3 dimensões temporais (`vencimento`, `competencia`, `pagamento`)
- `fato_financeiro` (Clinicorp) **mantém** — visão complementar (performance comercial)
- Builders SQL puros INSERT...SELECT...ON DUPLICATE KEY UPDATE
- Endpoint `/analytics/rebuild/contaazul`

**Sub-PR 4f: Tela `/financeiro` (Fase 6.2)** (~1.5d)
- Dashboard com KPIs do `fato_caixa`: entradas/saídas realizadas vs previstas, saldo líquido, inadimplência %, top categorias de despesa
- Gráficos: Realizado vs Previsto mensal, evolução saldo acumulado, distribuição por categoria
- Tabela: faturas com status (pago/pendente/vencido) + filtros
- Permission `financeiro.read` + `financeiro.export` (já no catálogo)
- Aplica os 5 passos do checklist obrigatório de novo módulo
- Já nasce com drill-down do PR-15 ativo em todos os KPIs

**Sub-PR 15 (NOVO, decidido 2026-05-04): Drill-down auditável dos KPIs** (~3-4d, depois de 14d/14e)

> Decisão arquitetural: cada número do dashboard tem rastreabilidade até a linha de origem. Resolve a pergunta "esse R$ 369.205 está certo?" sem precisar saber nome de tabela/campo. Substitui a ideia inicial de "Smart Report genérico" (rejeitada por UX fraca e baixa rastreabilidade).

**Como funciona:**
- Cada endpoint do dashboard ganha um endpoint paralelo `/{kpi}/itens` que retorna as linhas que entraram no cálculo (mesma query, sem o agregador)
- Total no footer do drawer **tem que bater com o KPI** — auditoria built-in
- Cada linha mostra `external_id` (deep-link pro ERP) + botão "ver JSON staging" pra debug profundo

**Princípios de UX (decididos com Pedro):**
- ❌ Sem botão extra nos cards — não polui visual atual
- ✅ Card inteiro clicável (cursor pointer + hover sutil)
- ✅ Único indicador: pequeno ícone `↗` em cinza claro no canto superior direito
- ✅ Drawer slide-in da direita (~50% da tela), dashboard continua visível atrás. Não modal centralizado.
- ✅ Componente `KpiDrillDown` parametrizável reutilizável em todos os KPIs

**Implementa pra Clinicorp primeiro** (já populado) — auditável imediatamente o R$ 369.205 e demais KPIs do `/dashboard/executivo`.

**Sub-PR 16 (NOVO): Match Clinicorp ↔ CA dentro do drill-down** (~2-3d, depois de 15)

Quando `fato_caixa` (Conta Azul) estiver populado, drill-downs de KPIs financeiros ganham coluna **"Match CA"** com 4 estados:
- ✅ **Em ambos** — chave bate (CPF + valor + data ≈)
- ⚠️ **Só Clinicorp** — venda registrada mas dinheiro não entrou no CA
- ⚠️ **Só CA** — entrada bancária sem registro Clinicorp
- ⚠️ **Divergente** — match parcial mas valor/data diferentes

Pedro abre o ERP só nas linhas marcadas com ⚠️. Vira a ferramenta principal de validação cruzada entre os dois sistemas.

**Backlog pós-Fase 4 (não bloqueia):**
- Sync incremental (hoje será full sync mês a mês como Clinicorp)
- APScheduler pra automação noturna

---

### FASE 5 — Camada Analytics ✅ (concluída)

**Objetivo:** Dados prontos para dashboards e IA, sem SQL livre.

#### Star schema completo (3 dim + 3 fato) ✅

| PR | Entrega | Commit |
|---|---|---|
| **PR-6** | `dim_tempo` (calendário 2019-2030, 4.383 dias) — universal sem tenant_id | `1caa927` |
| **PR-7** | `dim_paciente` (com `is_active`/`days_since_last_seen`) + `dim_profissional` | `f604fd1` |
| **PR-8** | `fato_agenda` + `fato_orcamentos` (status → flags) + `fato_financeiro` | `36aea39` |

#### Builders (SQL puro INSERT...SELECT...ON DUPLICATE KEY UPDATE) ✅

- [x] `build_dim_tempo` — proceduralmente, sem CORE como fonte
- [x] `build_dim_paciente` — DATEDIFF p/ days_since_last_seen, threshold 180 dias p/ is_active
- [x] `build_dim_profissional` — espelho de `core_professionals`
- [x] `build_fato_agenda`, `build_fato_orcamentos`, `build_fato_financeiro`
- [x] `build_all_dimensions`, `build_all_facts`, `build_all_analytics`

#### Endpoints ✅

- [x] `POST /api/v1/analytics/rebuild/dim_tempo` body `{start_year, end_year}`
- [x] `POST /api/v1/analytics/rebuild/dim_paciente`, `/dim_profissional`, `/dimensions`
- [x] `POST /api/v1/analytics/rebuild/fato_agenda`, `/fato_orcamentos`, `/fato_financeiro`, `/facts`
- [x] `POST /api/v1/analytics/rebuild/all` — dim + fatos em sequência (1.13s)
- [x] `GET /api/v1/analytics/status` — counts das 6 tabelas

#### Métricas validadas (smoke-test 2026-05-03)

| Métrica | Fórmula real | Resultado em produção |
|---|---|---|
| Faturamento abr/2026 | `SUM(amount) WHERE is_received=1 AND year_month_key='2026-04'` em `fato_financeiro` | **R$ 369.204,66** (480 pagamentos) |
| Conversão orçamentos | `SUM(is_approved)/COUNT(*)` em `fato_orcamentos` | **45,0%** — R$ 1.808.770,60 aprovados |
| Absenteísmo mensal | `SUM(is_canceled)/COUNT(*)` em `fato_agenda` GROUP BY year_month_key | **9-14% por mês** (consistente) |
| Top profissional | JOIN `fato_agenda` + `dim_profissional` GROUP BY name | **ERICO PARENTE** — 1.785 atendimentos |

#### Volumetria final do star schema

| Tabela | Registros |
|---|---:|
| dim_tempo | 4.383 |
| dim_paciente | 2.341 (1.660 ativos) |
| dim_profissional | 13 |
| fato_agenda | 5.191 |
| fato_orcamentos | 2.332 |
| fato_financeiro | 4.828 |
| **Total** | **19.088** |

---

### FASE 6 — Dashboards (6.1 ✅ · 6.6 parcial · demais ⏳)

**Objetivo:** Replicar e superar o sistema atual com dados reais.

Cada módulo abaixo equivale a uma aba do sistema atual, reimplementada em React.

#### 6.1 — Dashboard Executivo ✅ (concluído — PR-9 + PR-9b + PR-9c)

Entregue com escopo expandido vs original:
- 6 KPIs Hero (faturamento, consultas, absenteísmo, conversão, ticket, pacientes ativos) com MoM **e** YoY explícitos
- Funil comercial (orçados → aprovados/followup/abertos/recusados) com pipeline em R$
- Inadimplência (recebido vs a receber)
- Mix de pagamento (donut por forma)
- Top 5 profissionais com medalhas (🏆🥈🥉) + barras normalizadas
- Top 5 categorias de consulta com cor por absenteísmo
- Comparação YoY destacada
- Pacientes: **Curva ABC** (Pareto), **buckets de churn** (ativo/em risco/inativo/perdido), Top 10 LTV, novos × recorrentes
- Evolução 12 meses (barras + linha eixo duplo)
- Padrão visual documentado em `docs/10_DESIGN_DASHBOARDS.md`

#### 6.2 — Módulo Financeiro

KPIs:
- Entradas / Saídas realizadas e previstas
- Saldo Líquido
- Por forma de pagamento (Dinheiro, Cartão, Convênio, Pix)
- Inadimplência (%)

Gráficos:
- Realizado vs Previsão mensal
- Distribuição por forma de pagamento (pizza)
- Evolução de saldo acumulado (linha)

Tabela:
- Faturas com status (pago, pendente, vencido)
- Filtro por status, forma de pagamento, data

#### 6.3 — Módulo Agendamentos (Operacional)

KPIs:
- Total de consultas
- Confirmadas (%)
- Faltas (%)
- Canceladas (%)

Gráficos:
- Consultas por dia (linha)
- Por profissional (barras horizontais)
- Taxa de absenteísmo por mês (tendência)

Tabela:
- Consultas com status, paciente, profissional, data/hora

#### 6.4 — Módulo Comercial (Orçamentos + Vendas)

KPIs:
- Valor Total de Orçamentos
- Ticket Médio
- Taxa de Conversão (aprovados / criados)
- Receita por Especialidade

Gráficos:
- Funil de conversão (orçamentos → aprovados → pagos)
- Top Procedimentos por volume e receita
- Receita por Especialidade (pizza)

Tabela:
- Orçamentos com status, paciente, valor, data

#### 6.5 — Módulo Pacientes

KPIs:
- Total de pacientes ativos
- Novos no período
- Aniversariantes do mês

Tabela:
- Pacientes com último agendamento, status, contato

#### 6.6 — Módulo Administração / Configurações da Empresa

White-label: cada tenant personaliza identidade visual e dados operacionais.
Tela única `/empresa/configuracoes` com seções abaixo. Apenas usuários com
`role == 'admin'` podem editar.

**6.6.1 — Identidade Visual** ✅ (PR-11)
- [x] Logo principal (PNG/SVG/JPEG/WebP, max 1MB) — aplicado dinâmico na BrandBar
- [x] Favicon (.ico ou PNG, max 200KB) — aplicado em `<link rel="icon">` em runtime
- [x] Cor primária da marca (hex via color picker)
- [x] Cor secundária (opcional)
- [x] Imagem de fundo da tela de login (opcional)
- [x] Storage: volume Docker `./uploads:/app/uploads` servido via FastAPI StaticFiles

**6.6.2 — Dados da Empresa** ✅ (PR-11)
- [x] Nome fantasia, Razão social, CNPJ
- [x] Endereço completo (CEP, logradouro, cidade, UF)
- [x] Telefone, WhatsApp, E-mail, Site

**6.6.3 — Regional** (Fase 2, PR futuro)
- Fuso horário (default America/Sao_Paulo)
- Locale (pt-BR / en-US / es-ES)
- Moeda exibida (BRL / USD)
- Formato de data e número

**6.6.4 — Notificações** (Fase 2)
- E-mail "remetente" + display name
- SMTP customizado (opcional, default = gateway)
- Número WhatsApp Business + token Evolution API
- Templates editáveis (confirmação, lembrete, aniversário)

**6.6.5 — Operacional** (Fase 2)
- Horário de funcionamento por dia da semana
- Feriados nacionais + customizados do tenant
- Categorias de procedimento personalizadas
- Alíquota fiscal padrão

**6.6.6 — Integrações** (Fase 3)
- API key Clinicorp (já existe — só consolidar UI)
- Conta Azul (futuro)
- Stripe / gateway de pagamento (futuro)
- Webhook URL para eventos do sistema

**6.6.7 — Segurança** (Fase 3)
- Política de senha (min length, complexidade)
- 2FA habilitado por usuário ou obrigatório no tenant
- Timeout de sessão
- IPs/domínios permitidos para login (allowlist)

**6.6.8 — Usuários e Permissões** (Fase 3)
- Lista de usuários do tenant
- Convidar novo (envia link por e-mail)
- Roles: admin, gestor, dentista, recepcionista
- Histórico de últimos acessos

**6.6.9 — Plano SaaS** (futuro, só `is_saas_admin`)
- Plano atual e próximo vencimento
- Histórico de uso (consultas IA, storage, syncs)
- Upgrade/downgrade
- Faturas e forma de pagamento

**6.6.10 — Auditoria & LGPD** (futuro)
- Log de ações sensíveis (mudança de role, exclusão de paciente)
- Exportar todos os dados do tenant (GDPR/LGPD compliance)
- Solicitação de exclusão de paciente (anonimização)

**Decisões já tomadas:**
- Storage de imagens: volume Docker em `/uploads/{tenant_id}/{kind}.ext`
  servido como estático pelo backend. Migra pra S3/R2 em PR-13+ sem mudar API.
- Distinção firme: `/configuracoes` = preferências PESSOAIS do usuário
  (tema, layout, idioma); `/empresa/configuracoes` = identidade e operação
  do TENANT.
- Logo e favicon aplicados dinamicamente: BrandBar troca SVG placeholder
  por `<img>` se tenant tem logo customizado; favicon via `<link rel="icon">`
  manipulado em runtime no `index.html`.

---

### FASE 7 — AI Gateway + Assistente IA

**Objetivo:** Usuário pergunta, sistema responde com dados reais, controlados.

#### AI Gateway (backend)

- [ ] Roteador de modelo: perguntas simples → DeepSeek, análise executiva → Claude
- [ ] Pré-processamento: classifica a pergunta
- [ ] Query engine: monta query controlada em fato_*/dim_*
- [ ] Injeção de contexto: injeta dados reais no prompt
- [ ] Pós-processamento: formata resposta
- [ ] Controle de tokens: debita do limite do tenant
- [ ] Log de uso: `ai_usage_logs` com tokens_in, tokens_out, custo, modelo

#### Tipos de perguntas suportadas (MVP)

| Pergunta | Dados necessários | Modelo |
|---|---|---|
| "Qual o faturamento de abril?" | fato_financeiro | DeepSeek |
| "Como está minha inadimplência?" | fato_financeiro | DeepSeek |
| "Quais profissionais têm mais faltas?" | fato_agenda + dim_profissional | DeepSeek |
| "Analise a performance do mês" | todos os fatos | Claude |
| "Compare este mês com o anterior" | fato_financeiro + dim_tempo | Claude |

#### Frontend — Assistente IA

- [ ] Chat interface com histórico por sessão
- [ ] Indicador de tokens consumidos vs limite
- [ ] Card de resposta com: valor, explicação, período, fonte (doc 06)
- [ ] Botão "Explicar mais" → aprofunda com Claude

---

### FASE 8 — Admin SaaS

**Objetivo:** Gerenciar múltiplos tenants como plataforma.

- [ ] Listagem de tenants com status, uso de IA, última sync
- [ ] Criação de novo tenant
- [ ] Configuração de limites de tokens por tenant
- [ ] Logs globais de uso de IA
- [ ] Onboarding de nova clínica

---

## Mapeamento: sistema atual → IAnalisys

| Elemento do SIG 2026 | IAnalisys Saúde | Melhoria |
|---|---|---|
| Login simples | JWT + papéis + multi-tenant | Auth profissional |
| Clinicorp direto na view | staging → core → analytics | Pipeline real |
| Sem Conta Azul | Integração completa | Dados financeiros reais |
| PHP sem camadas | FastAPI + services + repositories | Arquitetura limpa |
| Single-tenant | Multi-tenant com isolamento | SaaS real |
| Sem IA | AI Gateway com Claude + DeepSeek | Análise inteligente |
| Sem controle de custo | Tokens por tenant com logs | Sustentabilidade |
| Sem LGPD | Soft delete, audit log, dados por tenant | Compliance |
| CRM vazio | Fora do MVP | Fase futura |
| Metas vazias | Operacional expandido | Fase futura |

---

## Ordem de implementação recomendada

```
Fase 1 ✅ → Fase 2 ✅ → Fase 3 ✅ (staging) → Fase 4 ✅ (OAuth) → Fase 5 → Fase 6 → Fase 7 → Fase 8
```

**Justificativa:**
- Fase 2 antes de tudo: sem auth, nada pode ir para produção
- Fase 3 antes da 4: Clinicorp é a fonte principal de dados operacionais
- Fase 5 parcial junto com Fase 3: analytics precisa ser construído enquanto os dados chegam
- Fase 6.1+6.2 antes da IA: a IA precisa de dados para responder
- Fase 7 depois dos dashboards: garante que os dados estejam corretos antes de expô-los via IA
- Conta Azul (Fase 4) pode rodar em paralelo com os dashboards

---

## Próxima ação imediata

**PR-12 — Recuperação de senha (Gmail SMTP)** — implementado, em smoke-test pelo Pedro (commit pendente após validação).

**PR-13 — RBAC granular + CRUD de usuários (DECIDIDO em 2026-05-03)**

Decisão estratégica: fazer ANTES dos demais módulos (Pacientes, Agenda, Clínico, Financeiro, IA), pra que cada módulo novo já nasça protegido. Custo estimado ~2-3 dias; retrofit depois custaria ~1 semana de trabalho mecânico em ~50 endpoints + ~30 telas.

Granularidade do PR-13: **simples** (`modulo.read` + `modulo.write` por módulo). Refinamento (`export`, sub-permissions) vira PR futuro conforme cada módulo amadurece.

Pós-PR-13, decidir entre:
- Fase 4 Conta Azul completo — staging + transform + unificação financeira
- Fase 6.2 Módulo Financeiro — só com Clinicorp (sem despesas)
- Fase 3 sync incremental + APScheduler — automação operacional

### PR-13 — Plano detalhado

**Tabelas (migration 0013):**
- `permissions` (id, code, label, module, description) — catálogo de permissões granulares
- `role_permissions` (role_id, permission_id) — many-to-many editável

**Catálogo inicial (~22 codes em 8 módulos):**
- `dashboard.read`
- `pacientes.read/write/export`
- `agenda.read/write`
- `clinico.read/write`
- `financeiro.read/write/export`
- `sync.run`, `analytics.rebuild`
- `usuarios.read/invite/edit/deactivate`
- `empresa.settings.read/write`, `empresa.permissions.manage`
- `ia.use/config`

**Matriz default:**
- `tenant_admin` = todas
- `manager` = quase tudo, exceto `sync.run`, `analytics.rebuild`, `empresa.permissions.manage`, `usuarios.invite/edit/deactivate`, `ia.config`
- `financial` = `dashboard.read` + `financeiro.*` + `pacientes.read/export` + `empresa.settings.read` + `ia.use`
- `commercial` = `dashboard.read` + `pacientes.read/write/export` + `agenda.*` + `empresa.settings.read` + `ia.use`
- `operations` = `pacientes.read/write` + `agenda.*` + `clinico.*`
- `saas_admin` = bypass total (não passa por permission_check)

**Endpoints novos:**
- `GET /api/v1/permissions` — catálogo
- `GET /api/v1/roles` — roles + permissions atuais
- `PUT /api/v1/roles/{role_id}/permissions` — atualiza matriz da role (escopo do tenant)
- `GET /api/v1/users` — lista usuários do tenant
- `POST /api/v1/users/invite` — cria usuário + envia email "defina sua senha"
- `PATCH /api/v1/users/{id}` — edita nome, role, is_active
- `DELETE /api/v1/users/{id}` — soft-delete (is_active = false)

**Convite reaproveita PR-12:** adicionar coluna `purpose VARCHAR(20) DEFAULT 'reset'` em `password_reset_tokens` — `purpose='invite'` muda só o template do email; consumo do token usa o mesmo `ResetPasswordPage`.

**Backend — dependency `requires()`** (`app/api/v1/dependencies/permissions.py`):
```python
def requires(*codes: str):
    async def _dep(user: UserMe = Depends(get_current_user)) -> UserMe:
        if user.is_saas_admin:
            return user
        if not set(codes).issubset(user.permissions):
            raise HTTPException(403, f"Faltam permissões: {set(codes) - set(user.permissions)}")
        return user
    return _dep
```

**Frontend — primitivos:**
- Hook `usePermissions()` com `has`, `hasAny`, `hasAll`
- Componente `<Can permission="...">…</Can>` esconde botões/seções
- Wrapper `<RequirePermission permission="...">` no `App.tsx` redireciona pra `/forbidden`
- `permission` em cada item de `menus.ts` filtra menu

**Telas novas em `/empresa/`:**
- `/empresa/usuarios` — lista (nome, email, role, status) + botão "Convidar" + edit/desativar inline
- `/empresa/permissoes` — matriz role × permission editável (checkbox grid agrupado por módulo) + botão "Restaurar padrão"

**Sub-commits (5):**
1. Migration 0013 + seed catálogo + matriz default + coluna `purpose` em `password_reset_tokens`
2. `requires()` dependency + integração nas rotas existentes (tenant, sync, analytics, dashboard) + `/auth/me` devolvendo `permissions: string[]`
3. Frontend primitives: `usePermissions` + `<Can>` + `<RequirePermission>` + filtro no `menus.ts`
4. Endpoints `/permissions` e `/roles` + tela `/empresa/permissoes`
5. Endpoints `/users` + tela `/empresa/usuarios` + fluxo de convite via email

### PR-13 — Decisões já tomadas

- **Permissions são por tenant** (cada tenant tem suas linhas em `role_permissions`), não globais — uma clínica pode permitir export e outra não, sem afetar
- **Roles são fixas** no PR-13 (as 6 atuais). Roles customizáveis por tenant viram PR futuro se houver demanda
- **Convite por email apenas** (sem opção "criar usuário com senha temporária visível na UI"). Reaproveita Gmail SMTP do PR-12
- **Granularidade simples primeiro** (`read`/`write`). `export` só onde foi pedido (financeiro, pacientes). Granularidade fina (sub-módulos) vira PR depois
- **Dashboard executivo atual = `dashboard.read`** (visão geral da diretoria, não-segregada). Quando vierem dashboards específicos, ficam em `dashboard.financeiro.read` / `dashboard.comercial.read`. O dropdown "Dashboards" mostrará só os que o usuário tem permissão

### ⚠️ REGRA OBRIGATÓRIA — Toda página/módulo novo passa pelo checklist de permissões

**Sem exceção. Sem deploy se algum dos 5 passos foi pulado.** Decidido em 2026-05-03 e gravado aqui pra que ninguém esqueça.

**Decisão arquitetural casada (2026-05-03):** o sistema é **estritamente read-only sobre dados clínicos**. Pacientes, agenda, clínico e financeiro entram via APIs (Clinicorp + Conta Azul) e nunca são editados aqui. Logo, o catálogo NÃO contém `modulo.write` para esses 4 módulos. Escrita só existe nos módulos administrativos: usuários, empresa, sync, IA. A migration 0014 removeu os writes legados.

Catálogo final (19 codes em 8 módulos):
- `dashboard.read`
- `pacientes.read`, `pacientes.export`
- `agenda.read`, `agenda.export`
- `clinico.read`
- `financeiro.read`, `financeiro.export`
- `sync.run`, `analytics.rebuild`
- `usuarios.read`, `usuarios.invite`, `usuarios.edit`, `usuarios.deactivate`
- `empresa.settings.read`, `empresa.settings.write`, `empresa.permissions.manage`
- `ia.use`, `ia.config`

#### Checklist obrigatório (5 passos) — toda página nova ou módulo novo

1. **Declarar permission no catálogo** — migration nova com `INSERT INTO permissions ...`. Use `modulo.read` (+`.export` se houver botão de baixar) e ações administrativas específicas se aplicável (ex: `modulo.config`). NÃO crie `.write` para módulos que só consomem dados sincronizados.

2. **Proteger endpoint** com `Depends(requires("modulo.action"))` — sem isso o endpoint fica aberto a qualquer usuário logado. PR review deve barrar endpoint sem `requires()`.

3. **Adicionar item de menu** em `menus.ts` com campo `permission: 'modulo.read'`. Sem isso, o item aparece pra todo mundo independente da role.

4. **Wrapper `<RequirePermission>`** na rota do `App.tsx`. Defesa em profundidade — usuário pode digitar URL direto e burlar o filtro de menu.

5. **`<Can>` em botões e seções** dentro da página. Esconde ações que o usuário logado não pode disparar. Faz a UX consistente com o backend.

#### Como o `tenant_admin` cuida da matriz

Após os 5 passos, `tenant_admin` da clínica abre `/empresa/permissoes` e marca/desmarca a nova permission por role conforme a operação dele. Sem deploy, sem TI.

#### Como o seed inicial decide a matriz pra novos tenants

Quando um novo tenant é criado (futuro endpoint de Admin SaaS), uma matriz default é replicada por role — assim a clínica nova já vem com configuração razoável e edita só o que destoar.

### Backlog consolidado (cronologia 2026-05-02 → 2026-05-03)

| PR | Status | Entrega | Commit |
|---|---|---|---|
| PR-1 | ✅ | Migration 0005, schema record-level, sync estático | `b4e4a5d` |
| PR-2 | ✅ | Sync transacional por mês (6 entidades) | `b4e4a5d` |
| PR-3 | ✅ | Sync KPIs mensais agregados (10 endpoints em paralelo) | `41fb4d0` |
| PR-4 | ✅ | Tela `/admin/sync` em React (heatmap, status, log live) | `aa99b36` |
| Fix  | ✅ | Filtro `year` no `/sync/jobs` (heatmap não perdia mais histórico) | `c408ba5` |
| PR-5a | ✅ | Migration 0006 + CORE cadastros (8 tabelas + patients reservada) | `3fb20e8` |
| PR-5b | ✅ | Migration 0007 + CORE eventos (7 tabelas, 30.663 records) | `e5c1089` |
| PR-5c | ✅ | `core_patients` extraído via UNION (2.341 únicos, 0,39s) | `85d4b28` |
| PR-6 | ✅ | Migration 0008 + `dim_tempo` (calendário 2019-2030) | `1caa927` |
| PR-7 | ✅ | Migration 0009 + `dim_paciente` + `dim_profissional` | `f604fd1` |
| PR-8 | ✅ | Migration 0010 + 3 fatos + endpoint orquestrador `rebuild/all` | `36aea39` |
| PR-9a | ✅ | Endpoint `/dashboard/executivo` (KPIs + evolução 12 meses) | `ebb391a` |
| PR-9b | ✅ | Backend expandido (funil + inadimplência + mix + top + YoY + pacientes ABC/churn/LTV) | `504bd55` |
| PR-9 (frontend) | ✅ | Página `/dashboard` com 4 seções, gráficos recharts, ranking com medalhas, ilustrações SVG | `0c7072c` |
| PR-9c | ✅ | Botão "Reconstruir CORE+ANALYTICS" na SyncPage (orquestra pipeline) | `0c7072c` |
| PR-10 | ✅ | AppShell de 2 barras (BrandBar branca + MenuBar configurável) + SettingsContext + PageTitleContext + página `/configuracoes` | `918b60d` |
| PR-11 | ✅ | Configurações da empresa em `/empresa/configuracoes` — logo/favicon/login_bg + dados + endereço + cores. TenantContext aplica dinamicamente | `f810b8b` |
| **PR-12** | ✅ | Recuperação de senha via email (Gmail SMTP) + login só com email |
| **PR-13** | ✅ | RBAC granular: `permissions` + `role_permissions` + matriz UI + CRUD usuários + convite | `93e6872` |
| **0014** | ✅ | Catálogo revisado: remove 4 writes (sistema read-only), adiciona `agenda.export` (19 codes) | `cf93dc3` |
| **PR-14a/b/c** | ✅ | Conta Azul pipeline staging: client refeito + migration 0015 (6 tabelas stg_ca_*) + sync_service + endpoints + UI com tabs | `fdf08cb` |
| **Hotfix CA** | ✅ | Rate limit retry/backoff + tenant_id no state OAuth + app NOVO CA isolado do v1 | `ebe323c` |

### PR-9 (Fase 6.1) — Dashboard Executivo

**Escopo proposto:**
- Página `/dashboard` em React (substitui ou complementa a HomePage)
- 6 cards de KPI lendo dos fatos: Faturamento mês, Consultas mês, Absenteísmo, Conversão, Ticket Médio, Pacientes ativos
- 1 gráfico de evolução mensal (faturamento + consultas)
- Filtro de período (mês/trimestre/ano)
- Backend: criar `/api/v1/dashboard/executivo?period=...` que devolve um JSON pronto pra renderizar (não SQL livre)

### Caminho até a IA

- **PR-9** ✅ — Dashboard Executivo (Fase 6.1)
- **PR-10** ✅ — AppShell + 2 barras (foundation visual)
- **PR-11** ✅ — Configurações da empresa (Fase 6.6 — Identidade + Dados)
- **PR-12** ✅ — Reset de senha via email + login só com email
- **PR-13** ✅ — RBAC granular + CRUD de usuários + convite
- **PR-14a/b/c** ✅ — Conta Azul pipeline staging (client + migration + sync workers + UI tabs)
- **Hotfix CA** ✅ — Rate limit retry + state OAuth + app novo isolado
- **Smoke-test e2e CA** ← próximo (Pedro, quando quota recuperar)
- **PR-14d** — Migration 0016 CORE Conta Azul + transform staging→core idempotente. **Só inicia depois do staging populado** (decisão Pedro 2026-05-04 — não desenhar CORE no escuro)
- **PR-14e** — Migration 0017 Analytics (`fato_caixa` + `dim_categoria` + `dim_centro_custo`)
- **PR-15 (NOVO)** — Drill-down auditável dos KPIs do dashboard, padrão visual zero-poluição (card clicável, drawer lateral, total bate com KPI)
- **PR-16 (NOVO)** — Match Clinicorp ↔ CA dentro do drill-down (4 estados de reconciliação)
- **PR-14f** — Tela `/financeiro` (Fase 6.2) — primeiro módulo aplicando o checklist obrigatório de 5 passos, já com drill-down do PR-15
- **Fase 7** — AI Gateway (Claude + DeepSeek com prompt caching, controle de tokens por tenant, log de uso)
- **Fase 7** — AI Gateway (Claude + DeepSeek com prompt caching, controle de tokens por tenant, log de uso)
  IA consultará as tabelas `fato_*` via SQL controlado, sem queries livres.

### Estado atual do banco (migrations aplicadas)
| ID | Descrição |
|---|---|
| 0001 | initial_schema (tenants, roles, users, user_tenants + seed 6 papéis) |
| 0002 | add_is_saas_admin_to_users |
| 0003 | (drop em 0005) staging snapshot por intervalo — descartada |
| 0004 | add_contaazul_tokens |
| 0005 | redesign_staging — 15 stg_cc_* record-level + sync_checkpoints + sync_jobs v2 |
| 0006 | core layer cadastros — 8 tabelas + core_patients reservada |
| 0007 | core layer eventos — 7 tabelas (incl. core_estimate_procedures nested) |
| 0008 | analytics layer — dim_tempo (calendário universal sem tenant_id) |
| 0009 | analytics layer — dim_paciente + dim_profissional |
| 0010 | analytics layer — fato_agenda + fato_orcamentos + fato_financeiro |
| 0011 | tenant settings — branding (favicon, login_bg, primary/secondary color) + dados empresa (CNPJ, contato, endereço) |
| 0012 | password_reset_tokens (token_hash SHA-256, TTL 1h, single-use, purpose) |
| 0013 | RBAC: permissions (22 codes) + role_permissions (matriz por tenant) |
| 0014 | RBAC read-only revision: remove 4 writes (pacientes/agenda/clinico/financeiro), adiciona agenda.export — 19 codes finais |
| 0015 | staging Conta Azul: 6 tabelas stg_ca_* (pessoas, produtos, servicos, vendedores, contas_receber, contas_pagar) |

### Volumetria atual (smoke-test 2026-05-02 com Parente Odontologia)

8.499 registros importados em staging:
- **Cadastros estáticos** (8 entidades): 745 registros — business 1, users 31, professionals 13, specialties 14, procedures 386, appointment_categories 85, appointment_statuses 8, crm_campaigns 207
- **Mensal — abril/2024 (parcial)**: 4.312 registros (appointments 1.296 + payments 839 + summary 2.177)
- **Mensal — abril+maio/2026**: 4.162 registros (appointments 968 + estimates 407 + payments 858 + invoices 1 + receipts 0 + summary 1.928)
- **KPIs mensais**: 1 linha (abril/2026, 10/10 endpoints ok)

Idempotência confirmada em todos os PRs (re-execução = 0 inserts, todos updates).

### Volumetria esperada Conta Azul Parente (validada via API ao vivo 2026-05-04)

| Entidade | Volume | Notas |
|---|---:|---|
| Pessoas | ~1.508 | clientes + fornecedores juntos (perfis array) |
| Produtos | ~1.043 | inclui `contagem_agregacao` e `integracao_ecommerce_ativada` |
| Serviços | 10 | usa wrapper `{itens_totais, itens}` (singular!) |
| Vendedores | 8 | array puro sem wrapper |
| Contas Receber jan-abr/2026 | 1.670 | R$ 777k total · R$ 716k em aberto |
| Contas Pagar jan-abr/2026 | 1.521 | R$ 1.368k total · R$ 244k em aberto |

⚠️ Smoke-test e2e via UI ainda **pendente** (rate limit foi atingido durante validação 2026-05-04, recupera em ~1h). Pipeline completo, falta só validar no browser.
