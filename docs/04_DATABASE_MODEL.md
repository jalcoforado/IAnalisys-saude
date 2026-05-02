# Modelo de Dados

## Estrutura

```
STAGING → CORE → ANALYTICS
```

---

## FOUNDATION (migrations 0001–0002)

```
tenants          — clínicas (id CHAR(36) UUID)
roles            — papéis: saas_admin, tenant_admin, dentist, receptionist, financial, viewer
users            — usuários com bcrypt password + is_saas_admin
user_tenants     — relacionamento N:N usuário ↔ tenant com papel
```

---

## STAGING (migration 0005, substitui 0003)

Dados brutos das APIs. **Nunca usar diretamente** nos dashboards — a camada que dashboards/IA consomem é CORE/ANALYTICS.

### Princípio: record-level com idempotência

A migration 0003 original guardava 1 linha por requisição (snapshot do intervalo). Foi descartada na 0005, que adota **1 linha por registro real** com `UNIQUE(tenant_id, external_id)`. Re-rodar o mesmo período não duplica — só atualiza `raw_data` e `synced_at` via `INSERT ... ON DUPLICATE KEY UPDATE`.

### Schema uniforme para todas as 15 tabelas `stg_cc_*`

```
id                   BIGINT PK autoincrement
tenant_id            CHAR(36) FK → tenants.id
external_id          VARCHAR(64)        -- PK na origem (Clinicorp)
external_updated_at  DATETIME NULL      -- LastChange_Date / Modified / z_LastChange_Date
raw_data             JSON               -- payload bruto (audit trail para a IA)
synced_at            DATETIME
sync_job_id          BIGINT NULL FK → sync_jobs.id
UNIQUE (tenant_id, external_id)
INDEX  (tenant_id, external_updated_at)
```

### Clinicorp — 15 tabelas

**Estáticas (8 — sem período):**

| Tabela | Origem | PK na origem |
|---|---|---|
| `stg_cc_business` | `/business/list` | `id` |
| `stg_cc_users` | `/security/list_users` | `id` |
| `stg_cc_professionals` | `/professional/list_all_professionals` | `id` |
| `stg_cc_specialties` | `/procedures/list_specialties` | `id` |
| `stg_cc_procedures` | `/procedures/list` | `id` |
| `stg_cc_appointment_categories` | `/appointment/list_categories` | `id` |
| `stg_cc_appointment_statuses` | `/appointment/status_list` | `id` |
| `stg_cc_crm_campaigns` | `/crm/list_active_campaigns` | `Name` |

**Transacionais (6 — por mês):**

| Tabela | Origem | PK | Updated_at |
|---|---|---|---|
| `stg_cc_appointments` | `/appointment/list` | `id` | `ModifiedDate` |
| `stg_cc_estimates` *(raw_data inclui ProcedureList nested)* | `/estimates/list` | `TreatmentId` | `LastChange_Date` |
| `stg_cc_payments` | `/payment/list` | `id` | `z_LastChange_Date` |
| `stg_cc_invoices` | `/financial/list_invoices` | `InvoiceId` | — |
| `stg_cc_receipts` | `/financial/list_receipt` | `id` | — |
| `stg_cc_summary_entries` | `/financial/list_summary` (`values[]`) | `id` | — |

**Agregada (1 — por mês, payload de 10 endpoints):**

| Tabela | Origem | PK |
|---|---|---|
| `stg_cc_kpis_monthly` | 10 endpoints agregados em paralelo | `'YYYY-MM-01'` |

Os 10 endpoints da kpis_monthly: `cash_flow`, `payments_aggregated`, `financial_summary`, `average_installments`, `appointment_info`, `estimates_conversion`, `expertise_revenue`, `patient_estimates`, `misses_goals`, `sales_goals`.

### Conta Azul

| Tabela | Conteúdo |
|---|---|
| `contaazul_tokens` | Access + refresh token por tenant (único por tenant) |

### Controle de execução

| Tabela | Conteúdo |
|---|---|
| `sync_jobs` | Rastreamento por execução: `entity`, `period_from/to DATE`, `status`, `records_fetched/inserted/updated`, `errors_count`, `duration_ms`, `error_message` |
| `sync_checkpoints` | Estado por (tenant, source, entity): último período sincronizado, contagem real em staging, status |

---

## CORE (pendente — PR-5)

Tabelas relacionais limpas, materializadas a partir de STAGING. Tipos coercidos (DATETIME, DECIMAL, BOOLEAN), `is_deleted` normalizado, `external_id` mantido como chave lógica para auditoria → staging.

### Cadastros (8)

```
core_business              — unidades da clínica
core_users                 — usuários Clinicorp (≠ users do auth)
core_professionals         — profissionais
core_specialties           — especialidades
core_procedures            — procedimentos (com price_list)
core_appointment_categories
core_appointment_statuses
core_crm_campaigns
```

### Eventos (6)

```
core_appointments          — agendamentos
core_estimates             — orçamentos (header)
core_estimate_procedures   — procedimentos do orçamento (line items)
core_payments              — pagamentos
core_invoices              — faturas
core_receipts              — recibos
core_summary_entries       — lançamentos contábeis (CREDIT/DEBIT)
```

### Derivado

```
core_patients              — extraído de PatientId em appointments + estimates + payments
                             (Clinicorp não tem /patient/list)
```

**Decisão arquitetural:** sem FK rígida entre `core_*`. Integridade lógica via `external_id`. Permite re-cargas em qualquer ordem.

---

## ANALYTICS (pendente)

```
fato_financeiro    — aggregados financeiros por período/tenant
fato_agenda        — aggregados de agendamentos
fato_orcamentos    — aggregados de orçamentos
dim_tempo          — calendário dia/semana/mês
dim_profissional   — profissionais ativos por tenant
dim_paciente       — pacientes ativos por tenant
```

---

## Regras

* sempre usar `tenant_id` — nunca queries sem filtro de tenant
* nunca usar staging direto nos dashboards
* métricas devem ser calculadas nas tabelas analytics

## Métricas base

**Faturamento:**
```
sum(recebimentos) from fato_financeiro
```

**Inadimplência:**
```
vencidos / total from fato_financeiro
```

**Conversão:**
```
aprovados / criados from fato_orcamentos
```

**Absenteísmo:**
```
faltas / agendamentos from fato_agenda
```

**Ticket Médio:**
```
faturamento / consultas (fato_financeiro + fato_agenda)
```
