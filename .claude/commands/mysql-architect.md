Você está modelando o banco de dados do IAnalisys Saúde.

## Stack
MySQL 8.0, SQLAlchemy 2.x async, Alembic para migrations.

## Arquitetura de camadas

```
staging/   → dados brutos das APIs (Clinicorp, Conta Azul) — nunca lidos pelo frontend
core/      → dados limpos e normalizados — fonte para analytics
analytics/ → tabelas fato e dimensão — fonte para dashboards e IA
```

## Regras invioláveis

- **Toda tabela** de negócio deve ter `tenant_id VARCHAR(36) NOT NULL INDEX`
- **Nunca** criar tabela sem tenant_id (exceto: roles, dim_tempo)
- **Nunca** acessar staging direto em dashboard ou IA — passar por core
- **Sempre** criar índice em: tenant_id, FK columns, campos de filtro (date, status)
- **Sempre** usar soft delete (`deleted_at`) em entidades principais
- Usar `VARCHAR(36)` para UUIDs (compatibilidade MySQL)
- Usar `DATETIME(timezone=True)` nos timestamps
- Toda migration tem `upgrade()` e `downgrade()`

## Camada Staging (dados brutos)

Prefixo `stg_`. Armazena o JSON/dados como vieram da API.
Campos obrigatórios: `tenant_id`, `external_id`, `raw_data JSON`, `synced_at`, `source`.

## Camada Core (dados limpos)

Prefixo `core_` ou sem prefixo (entidades principais). Dados normalizados.
Exemplos: `appointments`, `patients`, `budgets`, `financial_transactions`.
Campos obrigatórios: `tenant_id`, `id`, `created_at`, `updated_at`.

## Camada Analytics (agregados)

Tabelas fato: `fato_financeiro`, `fato_agenda`, `fato_orcamentos`
Dimensões: `dim_tempo`, `dim_profissional`, `dim_paciente`

Métricas oficiais (não inventar outras):
- Faturamento: `sum(valor_recebido)`
- Inadimplência: `sum(valor_vencido) / sum(valor_total)`
- Conversão: `count(status='aprovado') / count(*)`
- Absenteísmo: `count(status='falta') / count(*)`
- Ticket médio: `sum(valor_recebido) / count(distinct appointment_id)`

## Padrão de migration

```python
def upgrade() -> None:
    op.create_table(
        'nome_tabela',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tenant_id', sa.String(36), nullable=False),
        # ... demais colunas
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_nome_tabela_tenant_id', 'nome_tabela', ['tenant_id'])
```

## O que não fazer

- Não criar tabela analytics sem partir de dados core validados
- Não criar JOIN pesado em tempo real para dashboard — usar fato pré-calculado
- Não repetir colunas de negócio em staging (staging é espelho bruto)
- Não esquecer de declarar o model em `app/models/__init__.py`

## Referências do projeto
- Modelo de dados: docs/04_DATABASE_MODEL.md
- Multi-tenant: docs/03_MULTI_TENANT_MODEL.md
