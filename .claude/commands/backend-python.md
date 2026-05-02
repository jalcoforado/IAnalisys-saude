Você está desenvolvendo o backend do IAnalisys Saúde.

## Stack
Python 3.12, FastAPI, SQLAlchemy async (2.x), Alembic, MySQL 8, Redis, Pydantic v2.

## Arquitetura obrigatória

```
api/v1/routes/     → recebe request, valida schema, chama service
api/v1/dependencies/ → get_current_user, get_tenant, get_db
services/          → regras de negócio, orquestra repositories
repositories/      → único ponto de acesso ao banco (SQLAlchemy)
models/            → SQLAlchemy ORM models
schemas/           → Pydantic request/response
```

## Regras invioláveis

- **Nunca** colocar lógica de negócio em rotas
- **Nunca** acessar banco fora de repository
- **Nunca** usar SQL string livre — sempre ORM ou queries controladas
- **Sempre** usar `tenant_id` em toda query de dados de negócio
- **Sempre** tipar tudo: Pydantic schemas nas rotas, Mapped[] nos models
- **Sempre** usar `async/await` — o engine é async (aiomysql)
- Services recebem `db: AsyncSession` e `tenant_id: str` como parâmetros
- Repositories recebem `db: AsyncSession` e filtram por `tenant_id`

## Multi-tenant

O tenant_id é resolvido no middleware/dependency, **nunca** pelo frontend.
Toda query de dado de negócio deve ter `.where(Model.tenant_id == tenant_id)`.

## Padrão de arquivo

```python
# repositories/exemplo_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.exemplo import Exemplo

async def get_by_tenant(db: AsyncSession, tenant_id: str) -> list[Exemplo]:
    result = await db.execute(
        select(Exemplo).where(Exemplo.tenant_id == tenant_id)
    )
    return result.scalars().all()
```

## O que não fazer

- Não acessar `app.db` direto na rota
- Não misturar lógica de integração com lógica de negócio
- Não criar endpoint sem considerar autenticação futura
- Não ignorar soft delete (checar `deleted_at IS NULL`)
- Não criar migration sem rodar `alembic revision`

## Referências do projeto
- Arquitetura: docs/02_ARCHITECTURE.md
- Multi-tenant: docs/03_MULTI_TENANT_MODEL.md
- Banco: docs/04_DATABASE_MODEL.md
