"""Repository do layout customizado do "Meu IAnalisys" (My-Analisys).

Operações:
- get_layout(tenant_id, user_id)            → linha ou None
- upsert_layout(tenant_id, user_id, items)  → linha atualizada, version++

A camada de route faz o commit — repository só usa flush.
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_home_layout import UserHomeLayout


async def get_layout(
    db: AsyncSession, tenant_id: str, user_id: str
) -> UserHomeLayout | None:
    q = await db.execute(
        select(UserHomeLayout).where(
            UserHomeLayout.tenant_id == tenant_id,
            UserHomeLayout.user_id == user_id,
        )
    )
    return q.scalar_one_or_none()


async def upsert_layout(
    db: AsyncSession,
    tenant_id: str,
    user_id: str,
    items: list[dict[str, Any]],
) -> UserHomeLayout:
    existing = await get_layout(db, tenant_id, user_id)
    if existing is not None:
        existing.layout_json = items
        existing.version = existing.version + 1
        await db.flush()
        await db.refresh(existing)
        return existing
    new = UserHomeLayout(
        tenant_id=tenant_id,
        user_id=user_id,
        layout_json=items,
        version=1,
    )
    db.add(new)
    await db.flush()
    await db.refresh(new)
    return new
