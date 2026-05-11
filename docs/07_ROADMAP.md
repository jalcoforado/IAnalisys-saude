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

### FASE 4 — Pipeline de dados (Conta Azul) 🟢 (4a-4f ✅ · Show no Financeiro Fases 1+2 + Ondas 1+2 ✅ entregues 2026-05-09)

**Objetivo:** Dados financeiros reais entram no banco, separados do Clinicorp. Conta Azul é fonte canônica do realizado bancário (entradas + saídas + categorias). Clinicorp continua como fonte canônica do vínculo paciente↔consulta↔valor.

#### 🚀 Plano "Show no Financeiro" — 4 fases (definido 2026-05-09)

Após exploração de 7 endpoints CA prioritários (catálogo completo em `docs/11_CONTAAZUL_ENDPOINTS_CATALOG.md` — atualizado com payloads reais, formatos de parâmetro descobertos e pegadinhas):

**Fase 1 — Saldo Bancário** ✅ entregue 2026-05-09
- [x] Migration 0029 — 3 staging (`stg_ca_contas_financeiras`, `stg_ca_saldos_atuais`, `stg_ca_saldos_iniciais`) + 1 core (`core_ca_contas_financeiras`)
- [x] Cliente CA: `list_contas_financeiras`, `get_saldo_atual`, `list_saldos_iniciais`
- [x] Sync `sync_saldos_bancarios` — 3 jobs encadeados; saldo atual em paralelo via `asyncio.gather` (semaphore=4 + retry no 429)
- [x] Saldo inicial em **chamadas mensais** — API CA limita janela em 365 dias (descoberto no smoke; 13 meses dão 400)
- [x] Promo `transform_contas_financeiras` — junta staging contas + saldos atuais em core
- [x] Endpoint `POST /sync/contaazul/saldos` + `POST /transform/contaazul/saldos`
- [x] `/financeiro/overview` enriquecido com bloco `saldos_bancarios` (total + breakdown por conta)
- [x] Card "Saldo bancário" no topo do dashboard `/financeiro` (hero + lista de contas com tipo/banco)
- **Smoke Parente (10 contas reais):** saldo total ativas = -R$ 85.241,90 (negativo puxado pelo "COFRE PARENTE ODONTOLOGIA"); 17 saldos iniciais 12m sincronizados

**Fase 2 — DRE Estruturada** ✅ entregue 2026-05-09
- [x] Migration 0030 — `stg_ca_categorias_dre` + `core_ca_categorias_dre` (achatado, com nivel/parent/root) + `core_ca_dre_links` (N:N DRE↔categoria_financeira)
- [x] Cliente CA: `list_categorias_dre`
- [x] Sync registrado como `categorias_dre` em STATIC_ENTITIES (1 chamada)
- [x] Promo `transform_categorias_dre` — recursiva, achata `subitens[]` em N rows com pai/nivel; popula links N:N (delete + insert idempotente)
- [x] `/financeiro/overview` ganha bloco `dre` com 8 grupos raiz que têm código (totalizadores sem código são linhas calculadas, omitidos)
- [x] Card "DRE estruturada" no dashboard — colapsável, barras horizontais, drill subgrupos
- [x] Tela `/admin/sync` lista `categorias_dre` em Cadastros estáticos CA
- [x] Página `/financeiro` reformulada no padrão `PageContainer + PageHeader + PageFooter + PeriodSelector` (gap=6, eyebrow CONTA AZUL)
- **Smoke Parente abr/26:** 16 raízes → 32 nós, 120 links, R$ 229k classificados (98%) · R$ 2k não classificados (1%)
- **Observação:** Parente classifica receitas em "07.1 Entradas Não Operacionais" (R$ 24k) em vez de "01 Receitas Operacionais" — config do CA dela, código está correto.

**Onda 1 — Saldo bancário fix + Scope banner + Histórico** ✅ entregue 2026-05-09
- [x] `_is_banco_real()` filtra CAIXINHA / NAO_BANCO (cofres contábeis) do total bancário — saldo real Parente passou de **-R$ 85k → +R$ 188k** (cofre PARENTE ODONTOLOGIA tinha -R$ 234k contábil distorcendo)
- [x] `SaldosBancariosBlock` separa `saldo_bancos` vs `saldo_caixinhas` + qtd
- [x] Card "Saldo bancário" virou hero + drawer pra caixinhas/inativas
- [x] `ScopeBanner` no topo do `/financeiro` explica que receitas via PIX/cartão (Clinicorp) não passam pelo CA — direciona pra `/analise/financeiro`
- [x] `sync_historical_contaazul(year_start=2020)` varre todos os meses 2020+ pras 2 transacionais — botão "Carga histórica completa" em `/admin/sync` (Onda 1, indigo)

**Onda 2 — Detalhar baixas + Encargos + Métodos pagamento** ✅ entregue 2026-05-09
- [x] Migration 0031 — `stg_ca_parcelas_detalhe` + `core_ca_baixas` (data_pagamento real, método, conta destino, conciliado, juros/multa/desconto)
- [x] Cliente CA: `get_parcela_detalhe(parcela_id)` (`/v1/financeiro/contas-pagar-receber/parcelas/{id}`)
- [x] `sync_baixas_parcelas(only_missing=True)` itera parcelas pagas em `core_ca_parcelas` que ainda não têm baixa em `core_ca_baixas`; semaphore=3 + retry 429
- [x] Promo `transform_baixas` explode `baixas[]` (uma parcela pode ter N baixas)
- [x] Botão "Detalhar baixas — Onda 2" em `/admin/sync` (purple, badge "pode demorar")
- [x] `/financeiro/overview` ganhou bloco `metodos_pagamento` (PIX/Boleto/Cartão/...) + `conciliacao` (% reconciliado + top contas destino)
- [x] **Encargos:** `FinanceiroKpis.encargos_entradas/saidas` somam `juros + multa - desconto` de `core_ca_baixas` filtrando por `data_vencimento` (alinha com `fato_caixa.year_month_key`); `FinanceiroPage` mostra footer `+ R$ X em juros/multa · R$ Y c/ encargos` nos KpiCards Saídas/Entradas quando `|encargos| > 0`. `valor_pago_rateado` da `fato_caixa` continua "limpo" (sem encargos) pra preservar coluna estável; encargos são contabilizados separados.

**Validação contra PDFs do Conta Azul (abr/26)** ✅ 2026-05-09
- **Saídas pagas:** PDF R$ 233.146 = `fato_caixa.saidas` R$ 231.874 + encargos R$ 1.272 (juros + multa só vindos de `/parcelas/{id}`) — fechou em **R$ 0,00**
- **A pagar (em aberto vencendo no mês):** PDF 134 parcelas R$ 73.246,74 ≈ IAnalisys 134 parcelas distintas R$ 73.246,93 — diferença **R$ 0,19** (arredondamento)
- Todas as 134 do PDF estão "Atrasado" — `is_vencido=1` casa 100%
- **Não temos:** coluna "Conta bancária" (origem prevista do pagamento) por parcela. Disponível em `parcela.conta_financeira_id` se quiser futuro card "previsão de saída por banco".

**Fase 3 — Transferências**
- Sync `/v1/financeiro/transferencias` (12 em abr/26 Parente)
- Separa transferências internas das receitas/despesas — corrige distorção do fluxo

**Fase 4 — Vendas detalhadas + Match CC↔CA** (= PR-16 do roadmap antigo)
- Sync `/v1/venda/busca` + itens
- Match orçamento CC aprovado ↔ venda CA registrada → coluna "Match CA" no drill-down

#### Alinhamento de data em `fato_caixa` ✅ confirmado 2026-05-10

`year_month_key` em `data_vencimento` é a forma correta. Validado contra 2 PDFs nativos do CA (abr/26): Saídas R$ 0 gap, A pagar R$ 0,19 (arredondamento). Onda 2 confirmou que 98% das parcelas pagas em DESPESA caem no próprio mês de vencimento — trocar pra `data_pagamento` mudaria <2%. Ver memória `project_fato_caixa_data_alignment.md`.

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

**Sub-PR 4f: Tela `/financeiro` (Fase 6.2)** ✅ entregue 2026-05-04 (parcial — pendência abaixo)
- 3 Heroes (Entradas verde / Saídas vermelho / Saldo azul-ou-vermelho) com MoM
- 4 KPIs: A receber, A pagar, Inadimplência %, Saldo previsto (saldo + a receber - a pagar)
- Gráfico Evolução 12 meses (barras Entradas+Saídas + linha Saldo)
- Top 5 receitas + Top 5 despesas + Pie status mix (pago/em aberto/vencido)
- Tabela centros de custo (entradas/saídas/saldo por unidade)
- Backend: `GET /financeiro/overview?year&month` em `financeiro_service.py` com 5 funções agregadoras
- Sem drill-down (PR-15 Etapa 2 stand-by — Pedro quer re-design pra "relatório auditável")

**Alinhamento de data ✅ confirmado 2026-05-10**
- `fato_caixa.year_month_key` em `data_vencimento` é a forma correta — bate com o relatório nativo do CA (PDFs abr/26 fecharam em R$ 0 / R$ 0,19 de gap)
- A queixa original ("entradas baixas em Mar-Mai/26") era escopo, não modelagem: receitas Parente vão via Clinicorp, não passam pelo CA. Resolvido com `ScopeBanner` no `/financeiro`.
- Onda 2 trouxe `data_pagamento` real em `core_ca_baixas` — 98% paga no próprio mês de vencimento, mudança seria irrelevante.
- Bug correlato corrigido durante smoke-test: `_status_mix` esbarrava no `ONLY_FULL_GROUP_BY` (MySQL strict) — encapsulado em subquery

**Sub-PR 15: Drill-down auditável dos KPIs**

**Etapa 1** ✅ (2026-05-04) — drawer slide-in nos 6 KPIs principais (faturamento + 5 KpiCards)
- Endpoint genérico `GET /dashboard/executivo/itens?kpi=<id>&year&month` reusa a MESMA WHERE clause do `dashboard_service.py` — total do drawer === valor do KPI (auditoria built-in)
- 6 builders no service: faturamento, consultas, absenteismo, conversao, ticket_medio, pacientes_ativos
- Componente `KpiDrillDown` parametrizável (drawer ~50% tela, ESC fecha, footer mostra "bate" verde se cumulativo, "indicador percentual/médio" se ratio)
- Card clicável + ícone `↗` cinza claro no canto superior direito (sem poluir UX existente)
- Smoke-test Out/2025: faturamento R$ 336.492,56 / 716 linhas, consultas 946, pacientes ativos 1.941, conversão 58,32%, absenteísmo 8,07% — todos auditados ✅

**Etapa 2** ✅ (resolvida via Sub-PR 20 — entregue 2026-05-09)

Substituída pelos drill-downs específicos dos 3 dashs segmentados, que cobrem auditoria com qualidade superior à proposta original:
- `/analise/financeiro` — modal "Auditar" no card Prazos (250 orçamentos, 5 status, parcelas com 4 fases Clinicorp expansíveis), card Custo de Adquirência com decomposição por forma
- `/analise/comercial` — Saúde da agenda (5 desfechos), tooltips ricos no Funil/Conversão/Evolução
- `/analise/pacientes` — Para Resgatar (top 15 LTV em risco com telefone), Orçamentos em decisão (top 20 FOLLOWUP/OPEN), Top LTV, Novos do mês com status

O dashboard executivo legado foi extinto (Sub-PR 20e), e com ele o drawer da Etapa 1.

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
- **Botão "sincronizar mês corrente inteiro"** (decisão 2026-05-05): clicar no nome do mês = sync de todas as entidades transacionais do mês de uma vez (em vez de uma a uma)

---

### Sub-PR 17 — Cockpit Operacional na HomePage (decidido 2026-05-05)

**Contexto:** HomePage atual mostra atalhos pros menus (redundante com sidebar) e link de conexão CA. Substituir por **cockpit operacional personalizado por role do usuário** com dados acionáveis do dia.

**Personalização por role** (já existem no DB: `commercial`, `financial`, `manager`, `operations`, `tenant_admin`, `saas_admin`):

| Card | operations | financial | commercial | manager | tenant_admin |
|---|:-:|:-:|:-:|:-:|:-:|
| Agenda do dia (com fallback próximos 7d) | ✅ | | | ✅ | ✅ |
| Recall (heurística por histórico) | ✅ | | ✅ | ✅ | ✅ |
| Orçamentos aprovados parados (30-90d) | | | ✅ | ✅ | ✅ |
| Inadimplência crítica (>60d, >R$500) | | ✅ | | ✅ | ✅ |
| Resumo do dia (entradas/saídas previstas) | | ✅ | | ✅ | ✅ |
| Top profissionais semana | | | ✅ | ✅ | ✅ |

**Sub-PR 17a — Cockpit determinístico** ✅ (entregue 2026-05-05)
- Backend: `app/services/home_service.py` com 6 builders + orquestrador
- Endpoint `GET /home/dashboard` decide cards pelo `user.role` (sem nova permission)
- Frontend: substitui `HomePage.tsx` com grid de cards condicionais — UI rica
- **Heurística de recall**: para cada paciente ativo, calcula intervalo médio + dias desde última. Elegível se `dias_desde_última > intervalo_médio × 1.3` E sem agenda futura. Top 20 ordenado por atraso × LTV.

**Sub-PR 18 — Sync de pacientes (PII)** ✅ (entregue 2026-05-05)
- 18a: `stg_cc_patients_details` + sync iterativa via `/patient/get` (Clinicorp não tem `/patient/list`)
  - Throttle 0.6s + chunks 50 + timeout duro 25s `asyncio.wait_for`
  - Background task asyncio.create_task (sobrevive timeout HTTP do uvicorn)
  - Final: 3476/3811 pacientes (91%) — restante deu rate limit, retomável via skip_existing
- 18b: ícones idade (Baby/User/UserCog) + cor por gênero (heurística por nome PT-BR pq API não retorna)
- 18c: extração da matriz da HomePage pra rota dedicada `/agenda` (componentes em `modules/agenda/`)
- 18d: status do appointment (CONFIRMED, ARRIVED, IN_SESSION, CHECKOUT, MISSED, LATE, CALL, PENDING_MATERIAL) + category_group (consulta/retorno/manutencao/procedimento/reabilitacao/ortodontia/bloqueio/outro) — Insights por status no banner + categoria
- 18e: seletor Hoje/Amanhã/Depois (limite gerencial +2d) — endpoint `/home/agenda?date=YYYY-MM-DD`
  - Bug fix: `EntitySpec.allows_future` — appointments era capado em hoje no sync
- 18f: **Camada 1 — Capacidade & Encaixe** (gerencial)
  - P95 dos últimos 90d (clínica + por prof) — evita outlier de feirão
  - Encaixes 30-90min com filtro de janela típica do prof (P5/P95 dos horários históricos)
  - `duration_minutes` calculado de fromTime/toTime (Clinicorp não preenche `ProceduresDuration`)
- 18g: **Camada 2 — Risco de no-show** (tático)
  - `risco = baseline × (1-peso) + taxa_pessoal × peso`, peso = min(1, n/5)
  - Bumps: +20% 1ª consulta, +15% sem CONFIRMED, +10% histórico de LATE
  - Badge no chip da matriz (amarelo ≥30%, vermelho ≥50%) + RiskCard com top 6 alto risco
- 18i: **Visão estratégica do dono** (HomePage `manager`/`tenant_admin`/`saas_admin`)
  - Endpoint `/home/agenda-strategic` consolida 3 dias (Hoje + Amanhã + Depois)
  - 3 colunas com KPIs por dia + agregados 3d (consultas, faltas esperadas, encaixe)
  - Top 5 pacientes a confirmar (consolidado) + top 5 profs ociosos
  - Roles não-DONO continuam com `AgendaSummaryCard` compacto

**Bug fixes incidentais:**
- Timezone do tenant em `home_service` (UTC do servidor → BRT via ZoneInfo) — agenda sumia depois das 21h BRT
- `_period_bounds` força `to_date <= hoje` (corretíssimo pra payments/invoices, errado pra appointments) — flag `allows_future`
- `raw_data` JSON do MySQL via `text()` vinha como string, transform fazia `isinstance(dict)` → falso → details_map vazio. `json.loads` no início corrige.

**Limitações conhecidas (sem solução do nosso lado):**
- Clinicorp **não expõe endpoint** pra bloqueios/compromissos (testado /commitment, /block, /unavailability, /compromisso, /event etc — todos 404). Aparecem só no UI deles. Heurística de janela típica (P5/P95 do histórico) cobre ~80%; bloqueios pontuais escapam. Solução futura: cadastro local de disponibilidade (proposto e adiado).

**Sub-PR 17b — IA Layer narrativa** ✅ (entregue 2026-05-06)
- `anthropic==0.40.0` SDK + `ANTHROPIC_API_KEY` no `.env` (chave reaproveitada do `claude_key.php` do v1 PHP)
- Modelo padrão **Haiku 4.5** (`claude-haiku-4-5-20251001`) — barato, ~$0.001/chamada, ~2s
- `app/services/ai_service.py` com prompt engineering pt-BR + cache Redis 5min (chave hasheada do payload)
- Endpoint `POST /home/agenda/ai-summary` recebe `StrategicOverview` + nome da clínica, devolve prosa
- `AINarrative` no topo do `AgendaInsightsCard` — botão "Gerar análise IA" (manual, não auto, pra controlar custo)
- Smoke-test produção 2026-05-06 deu prosa acionável com nomes próprios reais ("Priorize ligar para Márcio, Ana Mannuela e Maria Vitoria nas próximas 2 horas...")

**Sub-PR 18.5 — Tags operacionais (Aguardado vaga, Encaixe etc)** ✅ (entregue 2026-05-06)
- Descobrimento: Clinicorp tem subsistema de **tags/AppointmentMarkers** no payload do appointment que estávamos ignorando. 1.679 tags em 8 classes detectadas em produção (Parente).
- **Camada A — bug fix label**: `ARRIVED: 'Em espera'` → `'Chegou'` (evita confusão com tag "Aguardado vaga")
- **Camada B — Lista de espera & tags na matriz**:
  - Migration 0025: `core_appointment_tags` + 7 flags `has_*` em `fato_agenda` desnormalizadas
  - `transform_appointment_tags`: extrai do array `tags` em `stg_cc_appointments.raw_data` + classifica em 8 classes (waitlist/encaixe/remarcar/lembrete/orcamento_pendente/retorno_pendente/financeiro_conferido/outro)
  - `_waitlist` builder + `WaitlistSection` em `AgendaSection` (janela ±7/+14 dias)
  - `WaitlistCard` em `/agenda` ao lado do `CapacityCard`
  - Bolinhas coloridas no rodapé do chip da matriz (até 3 + indicador "+N")
  - Tooltip rico com tag classificada + nome cru
  - `StrategicAgendaCard` na HomePage do dono ganhou pílulas "X na fila" / "Y encaixes"
- **Camada C — Pendências operacionais (DONO)**:
  - `_pendencias_operacionais` agrega 4 buckets (orcamento/retorno/remarcar/lembrete), top 5 mais antigos por bucket
  - `PendenciasCard` ocupando linha inteira na HomePage do dono
  - Smoke-test Parente: **804 pendências** reveladas (454 orçamentos a contatar, alguns com 800+ dias)

**Pendentes adicionais (Camadas 3+):**
- Tempo/eficiência (modal por categoria, hoje vs típico) — adiado por ter ganho marginal
- Predição de fechamento do período (% atendimento/falta vs média móvel 30d) — depois das primeiras semanas em produção
- Cadastro local de disponibilidade do prof (heurística P5/P95 cobre ~80%) — adiado

---

### Sub-PR 19 — Sincronização automática (planejado 2026-05-06, ainda não implementado)

**Motivação:** hoje todas as syncs (CC + CA) são acionadas manualmente pelo botão "Reconstruir" em `/admin/sync`. Pra colocar em produção precisamos disparar de forma agendada por entidade, com periodicidade alinhada à volatilidade real de cada uma. **Não bloqueia release inicial** mas é pré-requisito pra "esquecer" o painel de sync.

**Inventário de entidades (volume Parente 2026-05-06):**

| Provider | Entidade | Volume | Volatilidade | Tier |
|---|---|---|---|---|
| CC | appointments | 16.5k | Alta (status muda durante o dia) | T1 (15min) |
| CC | appointment_tags | 1.7k | Alta (vem junto com appointments) | T1 (junto) |
| CA | contas_receber | 4.0k | Alta (delta sync já existe) | T1 (15min) |
| CA | contas_pagar | 3.5k | Alta (delta sync já existe) | T1 (15min) |
| CC | estimates | 5.7k | Média | T2 (1h) |
| CC | payments | 12.4k | Média | T2 (1h) |
| CC | invoices | 55 | Média-baixa | T2 (1h) |
| CC | receipts | 69 | Média-baixa | T2 (1h) |
| CC | summary_entries | 30k | Média-baixa | T3 (diário) |
| CC | patients_details | 3.7k | Baixa (incremental) | T3 (diário) |
| CC | kpis_monthly | 22 | Baixa | T3 (diário) |
| CC | business/users/professionals/specialties/procedures/categories/statuses/campaigns | 1–386 | Baixa | T3 (diário) |
| CA | pessoas/produtos/servicos/vendedores/categorias/centros_custo | 7–1.4k | Baixa | T3 (diário) |

**Tiers de execução:**

| Tier | Frequência | Janela | Entidades | Duração estimada |
|---|---|---|---|---|
| **T1** | A cada 15min | 24/7 | CC appointments + tags · CA contas_receber/pagar (delta 1h) | ~30s |
| **T2** | 1× por hora | 24/7 (no minuto :05) | CC estimates · payments · invoices · receipts (mês corrente) | ~1min |
| **T3** | 1× por dia | 04:00 BRT | Tudo de baixa volatilidade + mês anterior reload completo | 5–10min |
| **T4** | 1× por semana | Domingo 03:00 BRT | Full reload últimos 3 meses (catch-all definitivo) + cleanup `sync_jobs` antigos | 20–30min |

**Pipeline pós-sync (encadeado, sempre):**
1. `transform_clinicorp/all` ou `transform_contaazul/all` (idempotente)
2. `analytics/rebuild/all` (1.13s pra tudo)

**Tecnologia recomendada:** APScheduler embutido no FastAPI
- ✅ Sem broker novo, mesmo processo
- ✅ Persistente em Redis (sobrevive restart via JobStoreRedis)
- ✅ Lock automático (`max_instances=1` evita overlap)
- ⚠️ Single-process — quando crescer pra N tenants em workers separados, migrar pra Celery beat

**Salvaguardas obrigatórias:**
- `sync_jobs` table já existe — todo job grava status/erro/duração
- Lock por entidade via Redis SETNX TTL 60min — não roda 2× a mesma sync
- Retry exponencial em 429/5xx (2/4/8/16s) — já temos no client CC
- Janela de execução: T3/T4 só rodam 02:00–06:00 BRT (não competem com T1/T2)
- Kill switch por feature flag (`SCHEDULER_ENABLED=false` no .env desliga tudo)
- Job grava `last_success_at` por entidade pra UI mostrar "atrasado há 30min"

**Ordem de implementação sugerida (incremental):**
1. **PR-19a** — APScheduler + lock Redis + sync_jobs upgrade + **só Tier 1** (CC appointments + CA delta). Cobre 80% do valor: agenda fresca pro dono.
2. **PR-19b** — Tier 2 (CC eventos comerciais).
3. **PR-19c** — Tier 3 (cadastros + mês anterior reload).
4. **PR-19d** — Tier 4 (full reload semanal) + kill switch UI.
5. **PR-19e** — Painel `/admin/sync` ganha "Próxima execução: 14:30" + "Última: 14:15 (sucesso, 28s)" por entidade.

**Decisões pendentes pra discutir antes de codar:**
- Tier 1 a cada 15min é agressivo? Talvez 30min seja suficiente — depende de quanto o dono quer vê-lo "tempo real"
- T4 full reload semanal é redundante se T3 já recarrega o mês anterior — talvez só faça sentido se descobrirmos que CC retroage mais que 30 dias
- Multi-tenant: se forem >5 tenants, T1 rodando 4×/h × N tenants pode estourar rate limit do CC. Plano: priorizar tenants ativos, throttle global

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

### Sub-PR 20 — Dashboards segmentados (Análise) — 2026-05-07

**Estratégia:** dashboard executivo (`/dashboard`) será EXTINTO após criação de 3 dashboards segmentados sob menu **ANÁLISE**, cada um com narrativa própria + IA dedicada. Sobreposições intencionais entre Comercial e Pacientes (ex: "novos × recorrentes" em ambos com perspectivas diferentes).

#### Sub-PR 20b — `/analise/financeiro` ✅ (entregue 2026-05-07)

Foco: relatório estratégico-tático para o DONO, perspectiva de R$.
- 4 KPIs: Faturamento (orçamentos aprovados) · Conversão por valor (alinhado Clinicorp) · Ticket médio · Recebido — todos com MoM/YoY/sparkline 12m, projeção quando mês parcial
- Funil orçamentos com conversão por valor E por contagem
- Mix pagamento, top atendentes (registrantes), top médicos (executantes via distribuição proporcional), top categorias (especialidades)
- Banner único de mês parcial (em vez de poluir cards)
- Inadimplência MOVIDA pra `/financeiro` (Fluxo de Caixa) — mais pertinente lá
- **Insights via IA com botão sob demanda** (Claude Haiku 4.5) com prompt que entende mês parcial e usa projeção
- Sem insights hardcoded (Pedro removeu — IA cobre melhor)

#### Sub-PR 20c — `/analise/comercial` ✅ (entregue 2026-05-07)

Foco: operação comercial — volume, conversão, demanda, ocupação, mix.
Pergunta-guia: "como está rodando a máquina de vendas?"
- 5 KPIs: Consultas executadas · Absenteísmo (`is_inverse`) · Ticket por consulta · Conversão consulta→orçamento · Pacientes únicos
- Funil POR PACIENTE: consulta → com orçamento → aprovado (taxas + tempo médio em dias)
- Top procedimentos executados (`core_estimate_procedures.executed=1`)
- Top especialidades em demanda (procedimentos por specialty_id)
- Top profissionais por VOLUME de consultas (não R$)
- Mix de categorias com MoM via projeção
- Operacional: encaixes, retorno pendente, para remarcar, perda potencial em cancelamentos
- Service em `analise_comercial_service.py` reusa helpers de `analise_financeiro_service` (não duplica)
- IA com botão sob demanda (POST `/analise/comercial/ai-insights`) — prompt de operações
- Header azul/índigo (financeiro=verde) pra distinguir visualmente

#### Sub-PR 20b+ — Validações com cliente (Parente, abr/2026) — 2026-05-08

Sessão de auditoria com Pedro confrontando números do dashboard com PDFs/planilhas reais. Achados e correções:

**Card Recebido (Caixa) — Sub-PR 20b**
- Bug: card mostrava R$ 373k vs R$ 497k real do PDF Clinicorp. Causa: filtrava por `fato_financeiro.year_month_key` (= `COALESCE(payment_date, due_date)`).
- Fix: trocar fonte para `core_summary_entries(type=DEBIT, post_type=RECEIVED)` filtrado por `year/month`. Líquido bate centavo a centavo (diff R$ 0,11 em abr/26).
- Adicionado `RecebidoBreakdown` (líquido + bruto + taxas) e card `CustoAdquirenciaCard` com fatiamento heurístico por forma de pagamento (taxas Crédito 5,0% / Débito 0,9% / Boleto 0,4% calibradas com planilha real, erro < 0,5pp por forma).
- Memória: `reference_clinicorp_recebido_mapping.md`, `reference_clinicorp_taxa_por_forma.md`.

**Card Mix de Meios de Pagamento — Sub-PR 20b**
- REMOVIDO. Custo de Adquirência cobre a mesma informação com mais densidade.

**Card Prazos de Recebimento — Sub-PR 20b**
- Achado: `valor_total` (soma de `core_payments`) ≠ Faturamento (header `core_estimates`). Gap de 23,7% em abr/26 (R$ 410k vs R$ 313k).
- Causa raiz: Clinicorp gera plano em PARTES (entrada primeiro, demais parcelas conforme paciente paga). 7 orçamentos sem nenhuma parcela; nos 243 com parcelas, soma fica menor que header.
- Solução (caminho A): manter cálculo + adicionar painel "Cobertura do plano de pagamento" com barra empilhada (lançado vs pendente) e nota explicativa.
- Schema: `PrazoRecebimentoSection` ganhou `faturamento_aprovado`, `qtd_sem_parcelas`, `valor_sem_parcelas`.
- Memória: `reference_clinicorp_payment_plan_partial.md`.

**Refator profundo do dashboard comercial — Sub-PR 20c**

Migration `0026_fato_agenda_status_flags.py` + builder + service. Decompõe agendamentos em 5 desfechos via `core_appointment_statuses.type`:

| Flag | Origem | Significado |
|---|---|---|
| `is_efetiva` | CHECKOUT | Paciente atendido (base de tops) |
| `is_falta` | MISSED | Paciente faltou (absenteísmo clínico) |
| `is_indefinida` | NULL não-cancelado | Recepção não atualizou |

Decomposição abr/26: 691 efetivas + 75 faltas + 87 canceladas + 94 indefinidas + 5 outros = 952 total.

**Mudanças nos KPIs** (todos os títulos descritivos, sem abreviação):

| KPI | Antes | Agora |
|---|---|---|
| Consultas atendidas | 865 (`is_canceled=0`) | **691** (CHECKOUT) |
| Absenteísmo (faltas) | 9,1% (cancel/total) | **9,8%** (faltas / efetivas+faltas) |
| ~~Ticket / Consulta~~ | rateio artificial | **REMOVIDO** (duplicava visão financeira) |
| Conversão em orçamento | 36,2% (orçs ÷ consultas) | **42,8%** (pacientes que aprovaram ÷ pacientes atendidos) |
| Pacientes atendidos | 581 (qualquer status) | **442** (só CHECKOUT) |

**Funil Comercial** — todos os 3 níveis 100% por PACIENTE (era misturado evento/paciente). `total_consultas` entra só como contexto ("691 consultas em 442 pacientes"). Conversão Total bate com KPI.

**Cards e tooltips novos**:
- `SaudeAgendaCard` — barra empilhada + 5 cartões coloridos com decomposição mensal
- `ConversaoBreakdown` (5 categorias: aprovou no mês / em decisão / em tratamento / avulso / histórico antigo) com tooltip
- `KpiCardEnriched.helpTooltip` (prop opcional com HelpCircle)
- Tooltips ricos no Funil e na Evolução
- Evolution chart 12m reformatado para barra empilhada com 4 desfechos + legenda clicável (toggle de séries)
- Mix Categorias agora filtra `is_efetiva=1` (não mostra cancelado/falta por categoria)

**Padrão estabelecido**: cardinalidade não pode ser misturada. Quando contar gente, tudo conta gente. Quando contar evento, tudo conta evento. Não dividir um pelo outro.

Memória de referência: `project_agenda_status_flags.md`.

#### Sub-PR 20d — `/analise/pacientes` ✅ (entregue 2026-05-09)

Foco: retenção e oportunidade — descobrir QUEM remarcar, resgatar, fidelizar.
Pergunta-guia: "quem eu deveria estar ligando?"

**Entregue (Parente abr/26):**
- 4 KPIs: Pacientes ativos (1.140 — visita <90d) · Recorrência (86,4%) · LTV médio (R$ 3.142) · Em risco (841, `is_inverse`)
- Saúde da base (5 buckets: ativo/em risco/inativo/perdido/sem visita)
- Curva ABC sobre LTV (Pareto: A 80% / B 15% / C 5%)
- Novos × Recorrentes ENRIQUECIDO (R$ aprovado + ticket por grupo) — insight: novos chegam com ticket 2x maior em Parente
- Evolution 12m (barras empilhadas novos × recorrentes)
- ⚡ **Para Resgatar** — top 15 LTV em 90-365d (em risco/inativo) com telefone — diferencial estratégico
- ⚡ **Orçamentos em decisão** — top 20 FOLLOWUP/OPEN nos últimos 60d (janela ancorada em hoje, ignora filtro de mês)
- Top LTV (10 maiores) + Novos do mês (20 com status orçamento)
- Banner "Mês em andamento" padronizado (sky/CalendarClock) em todos os 3 dashs

**Pegadinha resolvida**: KPI "Pacientes ativos" usa `days_since_last_seen < 90` (não `is_active=1` que retorna 1986 — inclui 90-180d). Bate com bucket "Ativo".

**Performance**: TOTAL endpoint = 270ms após migration `0027_pacientes_perf_indexes` (era 48s antes — falta de índice em `fato_financeiro(patient_external_id)` + GROUP BY antes de LIMIT no `_top_ltv`).

**Drill-down do paciente** ✅ (entregue 2026-05-09):
- Endpoint `GET /analise/pacientes/{pid}/historico` (~8ms — 4 queries leves)
- Drawer slide-in lateral 60% à direita (ESC fecha)
- Header: nome + bucket + telefone + email + gênero + idade
- 4 mini-métricas: LTV · Consultas (efetivas) · Orçamentos (aprovados) · Pendente em decisão
- Rastros: 1ª visita · última visita · ticket médio
- Top 20 consultas (data · profissional · categoria · desfecho colorido com 5 estados)
- Top 10 orçamentos (data · profissional · valor · status colorido)
- Nomes clicáveis nos 4 cards (Para Resgatar · Orçamentos em decisão · Top LTV · Novos do mês), aparência de texto comum com hover:underline (sem cor de link)

**Pendente para futuro (não bloqueante):**
- Módulo de mídia social / nichos (Frente A: HowDidMeet · Frente B: personas · Frente C: ROI por canal)

**KPIs principais (5)**: Pacientes ativos · LTV médio · Taxa de recorrência · Novos no mês · Pacientes em risco

**Listas acionáveis (o coração desse dashboard)**:
- 🔁 Para REMARCAR — retorno pendente / orçamento aprovado sem nova consulta
- 🆘 Para RESGATAR — inativos 180-365d ranqueados por LTV
- 💎 Top 10 LTV (clientes A — proteger)
- ⚠️ Em risco de churn (90-180d sem voltar, LTV alto)
- 🌱 Novos do mês — virão recorrentes? acompanhar

**Análise de coorte**: Curva ABC · Churn buckets (Ativo/Risco/Inativo/Perdido) com R$ em risco · Novos×Recorrentes mensal · Gap médio de retorno

**Drill-down**: clique no paciente → drawer com histórico (consultas, orçamentos, pagamentos, próximas ações)

**Módulo de mídia social / nichos (parte do 20d)** — usar os dados de paciente pra alimentar campanhas:

*Frente A — Captura de origem (diagnóstico)*
- Card "Como o paciente conheceu a clínica" lendo `HowDidMeet` e `IndicationSource` do `appointment/list` (raw_data em STAGING).
- Realidade hoje: 22 de 20.718 appointments preenchidos (0,1%) — valores ricos quando preenchem (Facebook, Instagram, Google, Indicação).
- Card mostra: % de captura + breakdown dos preenchidos + CTA "treinar recepção a preencher → libera ROI por canal". Choque visual pra forçar a conversa com o dono.
- Dependência: nenhuma — campos já vêm no payload, só precisa promover do staging pro core (`core_appointments.how_did_meet`, `core_appointments.indication_source`) e plotar.

*Frente B — Personas e nichos (alto valor mesmo sem `HowDidMeet` preenchido)*
- **Faixa etária × gênero × procedimento favorito** → personas pra criativos de Meta Ads (ex: "mulheres 35-50 que fizeram clareamento → ad de lente de contato dental").
- **Top procedimentos por ticket × volume** → qual nicho merece verba (ortodontia, implante, harmonização).
- **Pacientes inativos por procedimento** → arquivo CSV exportável pra Lookalike Audience no Meta (sem precisar de `HowDidMeet`).
- **Padrão de horário/dia de agendamento de novos pacientes** → quando rodar campanha (sex 18h vs ter 10h).
- IA narrativa: "seu nicho mais lucrativo é ortodontia adulta (R$ X / paciente, ciclo Y meses); persona dominante é mulher 28-40, recomendo Reels de antes-depois".

*Frente C — ROI por canal (futuro, depende da Frente A pegar tração)*
- Quando preenchimento de `HowDidMeet` chegar a >40%, montar dashboard de "Canal → R$ aprovado / R$ pago / consultas" pra calcular CAC implícito por canal e comparar com gasto de ads (input manual ou integração futura com Meta Ads API).

#### Sub-PR 20e — Extinção do dashboard executivo legado ✅ (entregue 2026-05-09)

Removido após 20d:
- Frontend: `modules/dashboard/`, `services/dashboard.service.ts`, item de menu "Visão Consolidada (legado)", rota `/dashboard` em `App.tsx`
- Backend: `routes/dashboard.py`, `services/dashboard_service.py`, `services/dashboard_drilldown_service.py`, `schemas/dashboard_drilldown.py` + include_router
- Mantido: `schemas/dashboard.py` e `types/dashboard.ts` reduzidos só ao `PeriodInfo` (usado por Fluxo de Caixa). Pode ser movido para `common.py/.ts` em limpeza futura.

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

#### Persona — SonIA (alinhado 2026-05-10)

A IA do sistema é personificada como **SonIA** — grafia destacando `IA` (Sôn**IA**) para reforçar a natureza de Inteligência Artificial. Avatar humano criado por Pedro (Nano Banana), mulher profissional sobre fundo com dashboards holográficos azuis.

**Assets de imagem** (`frontend/src/assets/sonia/`):
- [ ] `sonia-default.png` — neutra/sorrindo (sem watermark) — versão padrão
- [ ] `sonia-thinking.png` — pensando (mão no queixo, olhar lateral)
- [ ] `sonia-alert.png` — atenta/séria (alertas críticos, KPIs vermelhos)
- [ ] `sonia-happy.png` — comemorando (metas batidas, sucesso)
- [ ] `sonia-curious.png` — curiosa/convidativa (sugestões proativas)
- [ ] Exportar todas em `.webp` para reduzir bundle

**Hierarquia de uso na UI**:
1. **FAB persistente** (canto inferior direito, ~56px circular) — sempre presente, abre chat lateral.
2. **Cards de Insight** — avatar 24-28px à esquerda do título: "💬 **SonIA** notou que...". Aplica em Cockpit, Agenda Inteligente, drill-downs de KPI.
3. **Drawer/Modal narrativo** — quando IA explica análise complexa: foto maior (64-80px) + balão de fala. Acionado por "Explicar mais".
4. **Estados especiais**:
   - Loading IA → avatar `thinking` + animação suave (pulso).
   - Empty state → "SonIA ainda está aprendendo sobre este mês..." com `default` em tom suave.
   - Sucesso → `happy` com micro-animação.
   - Alerta crítico → `alert` no toast/banner.

**Estilização do nome**:
- `Sôn` em neutro (text-neutral-900)
- `IA` em destaque (text-primary-700, font-bold, tracking-wider)
- Componente reutilizável `<SonIABrand />` para uso consistente em headers, cards e tooltips.

**Status (2026-05-10 — fim de dia)**: SonIA MVP completo entregue.

**Componentes prontos** em `frontend/src/components/sonia/`:
- `SonIAContext` (provider + hook + open/setOpen exposto)
- `SonIAAnalyzers.ts` (analyze() entry point)
- `SonIAAvatar` (mood + size xs..2xl + ring + pulse)
- `SonIABrand` (texto Sôn**IA** estilizado)
- `SonIAFab` (avatar 2xl "se debruçando" + auto-close 6s na saudação)
- `SonIAInsightBanner` (banner narrativo na HomePage)
- `partialMonth.ts` (helper pra páginas sem `is_partial` do backend)

**Cobertura de páginas** (heurística front, sem LLM ainda):
- ✅ HomePage — banner + saudação automática (1× sessão, auto-fecha 6s)
- ✅ /agenda — confirmados, faltas, riscos, encaixe
- ✅ /analise/financeiro — faturamento, conversão, ticket, recebido
- ✅ /analise/comercial — consultas, absenteísmo, conversão, pacientes únicos
- ✅ /financeiro — entradas, saídas, saldo, inadimplência, encargos
- ✅ /financeiro/dre — receita, custos, despesas, resultado, margem
- ✅ /pacientes — ativos, recorrência, LTV, em risco, resgate
- ✅ /pacientes/captacao — % preenchimento, canais, top indicadores
- ❌ /admin/*, /empresa/*, /configuracoes — IA não atua (decisão Pedro)

**Mês corrente (parcial)**: SonIA suprime MoM% (que viraria alerta enganoso "caiu 70%!") e mostra valor parcial + projeção no ritmo atual. Headline: "Olhei o que temos de {mês} até agora." Alertas absolutos (inadimplência alta, saldo negativo, absenteísmo alto) continuam válidos.

**Limpeza concluída** (cards antigos de "IA narrativa" removidos):
- `AIInsightsSection` violeta de /analise/financeiro
- `AIInsightsSection` violeta de /analise/comercial
- `AINarrative` ("Gerar análise IA dos próximos 3 dias") de /agenda
- `BannerChoque` ("⚡ você está perdendo dado de marketing") de /pacientes/captacao

**Próximos passos (Fase 7)**:
- Plugar LLM real no FAB — endpoint `/ai/insight?page=...` com Sonnet 4.6
- Página dedicada `/sonia` (chat conversacional multi-turn) com Opus 4.7
- Recortar fundo dos PNGs via remove.bg + variar visual quando avatar grande
- Cache por sessão (mesmo page + filtros = mesmo insight por 5min)

**Pendências de UI conhecidas (não-bloqueantes)**:
- Avatares ainda têm fundo (escritório + hologramas) e marca d'água ✦ do Gemini no canto. Pedro adiou recorte transparente.

**Princípio**: SonIA é a "voz" da IA — toda saída de IA narrativa (Cockpit, Agenda, alertas, chat) é apresentada como vinda dela. Cria continuidade emocional e identidade de marca; usuário desenvolve relação com o assistente.

#### Arquitetura SonIA (decisão 2026-05-10)

Duas superfícies distintas, mesma persona:

| Superfície | Escopo | Modelo recomendado | Status |
|---|---|---|---|
| **FAB contextual** (canto inferior direito, sempre presente) | Insight rápido sobre a página atual (1 KPI block, ~5-15 métricas). Clique = "varredura" + observação. | **Claude Sonnet 4.6** (~US$ 0,016/insight) | ✅ Estrutura pronta, heurística front · LLM pendente (Fase 7) |
| **Página `/sonia`** (a criar) | Agente conversacional pleno, multi-turn, análise cross-página, histórico de conversa. | **Claude Opus 4.7 (1M ctx)** | ⏳ Adiada para depois — escopo robusto, depende de AI Gateway |
| Tarefas triviais (resumir 1 frase, classificar) | Sub-rotinas internas | **Haiku 4.5** ou **DeepSeek-Chat** | n/a |

**Regra crítica:** Haiku **não** deve fazer análise de números — ele alucina em raciocínio analítico. Sonnet é o piso para qualquer insight com KPIs.

#### Limpeza de "IA narrativa" das páginas (2026-05-10)

Decisão: remover seções de "Gerar com IA" embutidas em páginas — toda IA narrativa centraliza no FAB da SonIA. Páginas voltam ao papel de dashboard puro.

Removidos:
- `AIInsightsSection` em `/analise/financeiro` (card violeta com botão "Gerar com IA")
- `AIInsightsSection` em `/analise/comercial`
- `AINarrative` em `/agenda` (bloco "Gerar análise IA dos próximos 3 dias")
- `BannerChoque` em `/pacientes/captacao` (alerta editorial estático)

Mantidos (NÃO são IA narrativa, são dashboard operacional): `CapacityCard`, `RiskCard`, `WaitlistCard`, todos os `Top*Card`, `FunilCard`, `SaudeAgendaCard`, `MixCategoriasCard`, `OperacionalCard`, `SaudeBaseCard`, `CurvaAbcCard`, `ParaResgatarCard`, `OrcamentosPendentesCard`, `TreineRecepcaoCard`, KPI insights estáticos. Esses são VISUALIZAÇÕES — produto, não comentário.

#### Tom de voz canônico da SonIA

Personalidade: mulher de ~30 anos, **doce, discreta, cordial e gentil**. Reflete a pessoa real homenageada.

- Cumprimento sempre: "Oi, {nome}." em vez de "{nome}," seco
- Verbos suaves: "notei", "reparei", "encontrei", "selecionei", "achei", "queria te mostrar"
- Sugere, não manda: "que tal", "se quiser", "quem sabe", "podemos"
- Sem jargão corporativo: "régua de cobrança" → "olhar com calma"; "pipeline destravar" → "retomar essas conversas"
- Alertas críticos: séria mas calma, nunca alarmista
- Self-reference: "Pode contar comigo", "Sempre por perto"

Detalhe em `feedback_pedro_decisoes` e `project_sonia_persona` (memória).

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
