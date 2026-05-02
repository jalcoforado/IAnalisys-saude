# Integrações

## Fontes

* **Clinicorp** — dados operacionais (agendamentos, orçamentos, pacientes, financeiro)
* **Conta Azul** — dados financeiros (contas a pagar/receber, movimentações, vendas)

## Fluxo

```
API Externa → Worker de Sync → Staging → Core → Analytics → Dashboard / IA
```

---

## Clinicorp

### Autenticação

Basic Auth (API_USER + API_TOKEN). Credenciais estáticas por tenant.

### Configuração (env vars)

```
CLINICORP_API_URL=https://api.clinicorp.com/rest/v1
CLINICORP_API_USER=...
CLINICORP_API_TOKEN=...
CLINICORP_SUBSCRIBER_ID=...
CLINICORP_BUSINESS_ID=...
```

### Endpoints implementados (`app/integrations/clinicorp/client.py`)

| Método | Endpoint | Destino staging |
|---|---|---|
| get_appointments | /agenda/consultas | stg_appointments |
| get_estimates | /orcamentos | stg_estimates |
| get_cash_flow | /financeiro/fluxo-de-caixa | stg_cash_flow |
| get_payments | /financeiro/recebimentos | stg_payments |
| get_analytics | /analytics | stg_analytics |
| get_financial_summary | /financeiro/resumo | stg_financial_summary |
| get_estimates_conversion | /orcamentos/conversao | stg_estimates_conversion |

### Worker de sync (`app/integrations/clinicorp/sync_service.py`)

```python
await run_clinicorp_sync(db, tenant_id, from_date, to_date) -> SyncJob
```

- Cria `sync_job` com status `running`
- Busca todos os 7 endpoints em paralelo
- Salva raw JSON no staging (substituição: delete + insert por range)
- Atualiza job para `success` ou `error`

### Rotas de API

```
POST /api/v1/sync/clinicorp    — dispara sync manual (requer auth)
GET  /api/v1/sync/status       — lista últimos jobs do tenant
```

---

## Conta Azul

### Autenticação

OAuth 2.0 Authorization Code Flow (AWS Cognito). Token por tenant — access_token (1h) + refresh_token.

### Configuração (env vars)

```
CONTAAZUL_CLIENT_ID=...
CONTAAZUL_CLIENT_SECRET=...
CONTAAZUL_REDIRECT_URI=http://localhost:8000/api/v1/contaazul/callback
```

### URLs OAuth

```
Auth URL:   https://auth.contaazul.com/login
Token URL:  https://auth.contaazul.com/oauth2/token
Scope:      openid profile aws.cognito.signin.user.admin
```

### Endpoints do client (`app/integrations/contaazul/client.py`)

Base URL: `https://api.contaazul.com/v2`

| Método | Endpoint CA | Descrição |
|---|---|---|
| get_accounts_receivable | /accounts-receivable | Contas a receber |
| get_accounts_payable | /accounts-payable | Contas a pagar |
| get_financial_movements | /financial-movements | Movimentações |
| get_sales | /sales | Vendas/NFs emitidas |
| get_customers | /customers | Clientes |
| get_company | /company | Dados da empresa |

### Rotas de API

```
GET    /api/v1/contaazul/status      — status conexão (ativo/expirado/desconectado)
GET    /api/v1/contaazul/auth        — gera URL OAuth para redirecionar usuário
GET    /api/v1/contaazul/callback    — recebe code, salva token (usado pelo Conta Azul)
POST   /api/v1/contaazul/refresh     — renova token via refresh_token
DELETE /api/v1/contaazul/disconnect  — remove token do tenant
```

### Armazenamento de token

Tabela `contaazul_tokens` — unique constraint em `tenant_id`.
Upsert via delete + insert no callback.

---

## Regras gerais

* credenciais nunca expostas em logs
* tokens nunca retornados em responses de API
* sync registrado em `sync_jobs` com status, timestamps e contagem de registros
* erro de API externa = status `error` no sync_job, sistema continua operando
* retry manual disponível via `POST /sync/clinicorp`

## Frequência recomendada (a implementar com APScheduler)

| Fonte | Dado | Frequência |
|---|---|---|
| Clinicorp | agendamentos | 30 min |
| Clinicorp | orçamentos/financeiro | 1h |
| Conta Azul | financeiro | 1h |
