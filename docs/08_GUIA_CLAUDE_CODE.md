# Guia Prático — Claude Code no IAnalisys Saúde

## Princípio geral

Uma conversa = uma tarefa coesa.
Não misture backend + frontend + banco na mesma sessão, a não ser que sejam inseparáveis.

---

## Estratégia de contexto

### Quando usar uma conversa só

Tarefas que cruzam camadas mas são **uma funcionalidade fechada**:

- "Implementar login" → envolve model, repository, service, rota, schema e frontend
- "Criar módulo financeiro" → endpoint + hook + página

Nesse caso, comece com a skill que domina a tarefa:

```
/backend-python implemente o endpoint POST /auth/login com service e repository.
Depois vou pedir o frontend na mesma conversa.
```

---

### Quando separar em conversas diferentes

Use conversas separadas quando as partes são **independentes**:

| Conversa | Escopo |
|---|---|
| Conversa A | Criar tabela + migration (mysql-architect) |
| Conversa B | Criar repository + service + rota (backend-python) |
| Conversa C | Criar hook + página + componentes (frontend-react) |

Isso evita que o Claude perca foco ou misture contextos.

---

## Estrutura de um bom prompt

```
/skill-name [contexto do projeto] + [o que fazer] + [restrições] + [o que NÃO fazer]
```

### Exemplos reais para este projeto

**Backend — rota nova:**
```
/backend-python
Fase 2 do roadmap (docs/07_ROADMAP.md).
Crie o endpoint GET /api/v1/auth/me.
Deve usar a dependency get_current_user (ainda não existe, crie também).
Retornar: id, email, full_name, tenant_id, role.
Não implementar ainda: refresh token, permissões por papel.
```

**Frontend — módulo novo:**
```
/frontend-react
Criar o módulo Financeiro (src/modules/financeiro/).
KPIs: Entradas, Saídas, Saldo, por forma de pagamento.
Usar TanStack Query. Consumir GET /api/v1/financeiro/kpis.
Seguir paleta do design system (docs/08).
Não criar os gráficos ainda, só os cards de KPI.
```

**Banco — nova tabela:**
```
/mysql-architect
Criar tabela stg_appointments para staging de agendamentos da Clinicorp.
Campos necessários: tenant_id, external_id, appointment_date, professional_id,
patient_id, status, raw_data JSON, synced_at.
Gerar migration Alembic. Criar model SQLAlchemy. Registrar em models/__init__.py.
```

**IA — nova query do catálogo:**
```
/ai-engineer
Adicionar ao catálogo semântico a query get_ticket_medio(tenant_id, from, to).
Deve buscar de fato_financeiro + fato_agenda.
Registrar tokens. Respeitar limite do tenant.
Não implementar o classificador ainda.
```

---

## Fluxo recomendado por fase

### Fase 2 — Autenticação

```
1. /mysql-architect  → migration: campo is_saas_admin em users
2. /backend-python   → security/password.py + security/jwt.py
3. /backend-python   → repository/user_repository.py
4. /backend-python   → service/auth_service.py + rota /auth/login + /auth/me
5. /frontend-react   → AuthContext + useAuth + LoginPage + PrivateRoute
```

### Fase 3 — Pipeline Clinicorp

```
1. /mysql-architect  → tabelas stg_appointments, stg_patients, stg_budgets
2. /mysql-architect  → tabelas core_appointments, core_patients, core_budgets
3. /backend-python   → integrations/clinicorp/client.py
4. /backend-python   → workers/clinicorp_sync.py
5. /backend-python   → transformação staging → core
```

### Fase 6 — Dashboards

```
Para cada módulo (financeiro, agendamentos, orçamentos...):
1. /backend-python   → endpoint /api/v1/{modulo}/kpis
2. /frontend-react   → hook use{Modulo}KPIs
3. /frontend-react   → componentes de card + página do módulo
```

---

## Como passar contexto entre conversas

Quando iniciar uma nova conversa que depende de trabalho anterior, referencie:

```
/backend-python
Continuando a Fase 2 do docs/07_ROADMAP.md.
O model User já existe em app/models/user.py.
O UserTenant já existe em app/models/user_tenant.py.
O get_db já existe em app/db/session.py.
Agora crie o auth_service.py...
```

Claude Code lê os arquivos do projeto — não precisa copiar o código, só indicar onde está.

---

## Comandos úteis no dia a dia

| Situação | O que fazer |
|---|---|
| Iniciar nova feature | Leia o roadmap (`docs/07_ROADMAP.md`) antes de pedir |
| Dúvida de arquitetura | Referencie o doc correto na pasta `docs/` |
| Revisão de código | `/simplify` — revisa e melhora o que foi gerado |
| Algo não ficou certo | Descreva o problema na mesma conversa antes de abrir outra |
| Feature grande | Quebre em sub-tarefas e use uma conversa por sub-tarefa |

---

## O que nunca fazer num prompt

- Não pedir backend + frontend + banco junto sem uma skill definindo o escopo
- Não omitir onde os arquivos existentes estão ("crie do zero" quando já existe base)
- Não pedir "faça tudo do módulo X" sem especificar o que é o mínimo aceitável
- Não pedir algo fora da fase atual sem avisar que está pulando fase

---

## Template de prompt (copie e adapte)

```
/[skill]
Contexto: [fase atual, o que já existe]
Objetivo: [o que criar/modificar]
Arquivos envolvidos: [caminhos relevantes já existentes]
Restrições: [o que NÃO fazer, o que está fora do escopo]
Resultado esperado: [como saber que está pronto]
```

### Exemplo preenchido

```
/backend-python
Contexto: Fase 2 — autenticação. Models User/Tenant/Role já existem.
Objetivo: criar UserRepository com métodos get_by_email e get_by_id.
Arquivos envolvidos: app/models/user.py, app/db/session.py
Restrições: não implementar cache Redis ainda, não criar endpoint.
Resultado esperado: repository testável, sem SQL direto, filtrando por tenant_id.
```

---

## Skills disponíveis neste projeto

| Comando | Quando usar |
|---|---|
| `/backend-python` | Rotas, services, repositories, models, schemas, workers |
| `/frontend-react` | Componentes, páginas, hooks, services de API, módulos |
| `/mysql-architect` | Tabelas, migrations, índices, modelagem de dados |
| `/ai-engineer` | AI Gateway, catálogo semântico, roteamento de modelo, logs de IA |
