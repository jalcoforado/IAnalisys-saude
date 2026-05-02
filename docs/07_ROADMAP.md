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

#### Pendente

- [ ] **PR-3** — sync `kpis_monthly` (10 endpoints agregados em paralelo via `asyncio.gather`)
- [ ] **PR-4** — Tela `/admin/sync` no React (heatmap por mês × entidade, disparo manual, log de execução)
- [ ] **PR-5** — Transformação staging → core (`core_appointments`, `core_estimates`, `core_payments`, `core_patients` extraído de eventos, etc.)
- [ ] Sync incremental com delta por `external_updated_at` (campos disponíveis: `LastChange_Date`, `z_LastChange_Date`, `ModifiedDate`)
- [ ] APScheduler para sync automático recorrente
- [ ] Decisão sobre pacientes: **escolhido extrair de eventos** (não há `/patient/list` na Clinicorp) — implementação em PR-5

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

### FASE 5 — Camada Analytics

**Objetivo:** Dados prontos para dashboards e IA, sem SQL livre.

#### Tabelas fato

- [ ] `fato_financeiro` — aggregados por período/tenant
- [ ] `fato_agenda` — aggregados de agendamentos
- [ ] `fato_orcamentos` — aggregados de orçamentos

#### Dimensões

- [ ] `dim_tempo` — calendário com granularidade dia/semana/mês
- [ ] `dim_profissional` — profissionais ativos por tenant
- [ ] `dim_paciente` — pacientes ativos por tenant

#### Métricas oficiais (fonte: docs/04_DATABASE_MODEL.md)

| Métrica | Fórmula | Tabela |
|---|---|---|
| Faturamento | sum(recebimentos) | fato_financeiro |
| Inadimplência | vencidos / total | fato_financeiro |
| Conversão | aprovados / criados | fato_orcamentos |
| Absenteísmo | faltas / agendamentos | fato_agenda |
| Ticket Médio | faturamento / consultas | fato_financeiro + fato_agenda |

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

#### 6.6 — Módulo Administração

- CRUD de usuários do tenant
- Configurações do tenant (logo, timezone, moeda)
- Configuração de integrações (Clinicorp, Conta Azul)
- Limites de IA
- Logs de sync

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

**Próximo: PR-3** — sync de KPIs mensais agregados.

### Backlog ordenado da Fase 3 (sync Clinicorp)

| PR | Status | Entrega |
|---|---|---|
| PR-1 | ✅ commit `b4e4a5d` | Migration 0005, schema record-level, sync estático |
| PR-2 | ✅ commit `b4e4a5d` | Sync transacional por mês (6 entidades) |
| **PR-3** | 🔜 **próximo** | `stg_cc_kpis_monthly`: 10 endpoints agregados em paralelo (`asyncio.gather`) |
| PR-4 | pendente | Tela `/admin/sync` no React: heatmap mês × entidade, disparo manual, log |
| PR-5 | pendente | Migration 0006 + workers staging → CORE |

### Após PR-5: caminho para a IA

- **Fase 5 (Analytics)** — fato_*/dim_* a partir do CORE → IA consulta SQL controlado, sem queries livres
- **Fase 6 (Dashboards)** — Dashboard Executivo + Financeiro + Agendamentos + Comercial em React
- **Fase 7 (AI Gateway)** — Claude/DeepSeek com prompt caching, controle de tokens por tenant

### Estado atual do banco (migrations aplicadas)
| ID | Descrição |
|---|---|
| 0001 | initial_schema (tenants, roles, users, user_tenants + seed 6 papéis) |
| 0002 | add_is_saas_admin_to_users |
| 0003 | (drop em 0005) staging snapshot por intervalo — descartada |
| 0004 | add_contaazul_tokens |
| 0005 | redesign_staging — 15 stg_cc_* record-level + sync_checkpoints + sync_jobs v2 |
