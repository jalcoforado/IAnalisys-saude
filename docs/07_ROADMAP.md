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

### FASE 3 — Pipeline de dados (Clinicorp) ✅ (parcial — staging completo)

**Objetivo:** Dados da Clinicorp entram no banco, limpos e organizados.

#### Integração ✅

- [x] Client HTTP para Clinicorp API (`app/integrations/clinicorp/client.py`) — 17 endpoints
- [x] Worker de sync (`app/integrations/clinicorp/sync_service.py`)
- [x] Tabelas staging (migration 0003, todos com tenant_id):
  - `stg_appointments` — agendamentos
  - `stg_estimates` — orçamentos
  - `stg_cash_flow` — fluxo de caixa
  - `stg_payments` — pagamentos
  - `stg_analytics` — analytics gerais
  - `stg_financial_summary` — resumo financeiro
  - `stg_estimates_conversion` — conversão de orçamentos
- [x] `sync_jobs` — rastreamento de status (pending/running/success/error)
- [x] `POST /sync/clinicorp` — dispara sync manual
- [x] `GET /sync/status` — lista últimos jobs do tenant

#### Pendente

- [ ] Transformação staging → core (core_appointments, core_patients, etc.)
- [ ] Sync incremental com delta por updated_at
- [ ] APScheduler para sync automático

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

**Fase 5 — Camada Analytics** ou **Fase 6 — Frontend React**

### Opção A — Fase 5 (Analytics)
Transformar dados de staging em tabelas fato/dim para IA e dashboards:
- `fato_financeiro`, `fato_agenda`, `fato_orcamentos`
- `dim_tempo`, `dim_profissional`, `dim_paciente`
- Workers de transformação por tenant

### Opção B — Fase 6 (Frontend React)
Replicar o dashboard PHP (SIG 2026) em React com TanStack Query:
- Login + AuthContext
- Dashboard Executivo (Visão Geral)
- Módulo Financeiro
- Módulo Agendamentos
- Módulo Comercial (Orçamentos)

### Estado atual do banco (migrations aplicadas)
| ID | Descrição |
|---|---|
| 0001 | initial_schema (tenants, roles, users, user_tenants + seed 6 papéis) |
| 0002 | add_is_saas_admin_to_users |
| 0003 | add_staging_and_sync_jobs (7 stg_* + sync_jobs) |
| 0004 | add_contaazul_tokens |
