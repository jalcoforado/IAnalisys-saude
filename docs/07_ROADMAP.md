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

#### Pendente (frontend auth)

- [ ] Página de login (React)
- [ ] Context de autenticação (AuthContext)
- [ ] Hook `useAuth`
- [ ] Proteção de rotas (PrivateRoute)

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

#### Pendente

- [ ] Sync incremental com delta por `external_updated_at` (campos: `LastChange_Date`, `z_LastChange_Date`, `ModifiedDate`)
- [ ] APScheduler para sync automático recorrente
- [ ] Seção "Rebuild CORE/Analytics" na tela `/admin/sync` (PR-9)

---

### FASE 4 — Pipeline de dados (Conta Azul) ✅ (parcial — OAuth completo)

**Objetivo:** Dados financeiros reais entram no banco, separados do Clinicorp.

#### OAuth e conexão ✅

- [x] OAuth 2.0 Authorization Code Flow (Cognito-backed)
- [x] `contaazul_tokens` — token por tenant (migration 0004), unique constraint tenant_id
- [x] `GET /contaazul/status` — status da conexão (ativo/expirado/desconectado)
- [x] `GET /contaazul/auth` — gera URL de autorização
- [x] `GET /contaazul/callback` — recebe code, salva access+refresh token
- [x] `POST /contaazul/refresh` — renova token via refresh_token
- [x] `DELETE /contaazul/disconnect` — remove token do tenant
- [x] Client HTTP (`app/integrations/contaazul/client.py`): accounts_receivable, accounts_payable, financial_movements, sales, customers, company

#### Pendente

- [ ] Worker de sync (similar ao Clinicorp)
- [ ] Tabelas staging: `stg_contaazul_receivable`, `stg_contaazul_payable`, etc.
- [ ] Transformação staging → core (`core_financial_transactions`)
- [ ] Unificação financeira Clinicorp + Conta Azul

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

### FASE 6 — Dashboards

**Objetivo:** Replicar e superar o sistema atual com dados reais.

Cada módulo abaixo equivale a uma aba do sistema atual, reimplementada em React.

#### 6.1 — Dashboard Executivo (Visão Geral)

KPIs:
- Entradas Realizadas vs Previsão
- Saídas Realizadas vs Previsão
- Saldo do Período
- Total de Consultas
- Taxa de Absenteísmo
- Ticket Médio

Gráficos:
- Evolução financeira diária (barras)
- Realizado vs Previsão (comparativo)
- Consultas por dia (linha)

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

**6.6.1 — Identidade Visual** (Fase 1, PR-11)
- Logo principal (PNG/SVG, max 1MB)
- Favicon (.ico ou PNG, max 200KB)
- Cor primária da marca (hex via color picker)
- Cor secundária (opcional)
- Imagem de fundo da tela de login (opcional)

**6.6.2 — Dados da Empresa** (Fase 1, PR-11)
- Nome fantasia, Razão social, CNPJ
- Endereço completo (CEP, logradouro, cidade, UF)
- Telefone, WhatsApp, E-mail, Site

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

**Próximo: Fase 6.1** — Dashboard Executivo em React consumindo os fatos.

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
| **PR-9** | 🔜 **próximo** | Fase 6.1 — Dashboard Executivo em React |

### PR-9 (Fase 6.1) — Dashboard Executivo

**Escopo proposto:**
- Página `/dashboard` em React (substitui ou complementa a HomePage)
- 6 cards de KPI lendo dos fatos: Faturamento mês, Consultas mês, Absenteísmo, Conversão, Ticket Médio, Pacientes ativos
- 1 gráfico de evolução mensal (faturamento + consultas)
- Filtro de período (mês/trimestre/ano)
- Backend: criar `/api/v1/dashboard/executivo?period=...` que devolve um JSON pronto pra renderizar (não SQL livre)

### Caminho até a IA

- **PR-9** — Dashboard Executivo (Fase 6.1) ← próximo
- **PR-10..13** — Módulo Financeiro, Agendamentos, Comercial, Pacientes (Fase 6.2-6.5)
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

### Volumetria atual (smoke-test 2026-05-02 com Parente Odontologia)

8.499 registros importados em staging:
- **Cadastros estáticos** (8 entidades): 745 registros — business 1, users 31, professionals 13, specialties 14, procedures 386, appointment_categories 85, appointment_statuses 8, crm_campaigns 207
- **Mensal — abril/2024 (parcial)**: 4.312 registros (appointments 1.296 + payments 839 + summary 2.177)
- **Mensal — abril+maio/2026**: 4.162 registros (appointments 968 + estimates 407 + payments 858 + invoices 1 + receipts 0 + summary 1.928)
- **KPIs mensais**: 1 linha (abril/2026, 10/10 endpoints ok)

Idempotência confirmada em todos os PRs (re-execução = 0 inserts, todos updates).
