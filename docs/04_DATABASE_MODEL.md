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

## STAGING (migration 0003–0004)

Dados brutos das APIs. Nunca usar diretamente nos dashboards.

### Clinicorp

| Tabela | Conteúdo |
|---|---|
| `stg_appointments` | Agendamentos brutos |
| `stg_estimates` | Orçamentos brutos |
| `stg_cash_flow` | Fluxo de caixa bruto |
| `stg_payments` | Pagamentos brutos |
| `stg_analytics` | Analytics gerais brutos |
| `stg_financial_summary` | Resumo financeiro bruto |
| `stg_estimates_conversion` | Conversão de orçamentos bruta |

Todas as tabelas stg_* têm o mesmo schema:
```
id             BIGINT PK autoincrement
tenant_id      CHAR(36) FK → tenants.id
ref_date_from  VARCHAR(10)  -- YYYY-MM-DD
ref_date_to    VARCHAR(10)  -- YYYY-MM-DD
raw_data       JSON
synced_at      DATETIME
INDEX (tenant_id, ref_date_from, ref_date_to)
```

### Conta Azul

| Tabela | Conteúdo |
|---|---|
| `contaazul_tokens` | Access + refresh token por tenant (único por tenant) |

### Controle de sync

| Tabela | Conteúdo |
|---|---|
| `sync_jobs` | Rastreamento de execuções: status, timestamps, records_fetched, error_message |

---

## CORE (pendente)

```
core_appointments         — agendamentos limpos
core_patients             — pacientes limpos
core_budgets              — orçamentos limpos
core_professionals        — profissionais limpos
core_financial_transactions — transações unificadas Clinicorp + Conta Azul
```

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
