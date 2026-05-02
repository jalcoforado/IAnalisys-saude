from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.models.user_tenant import UserTenant


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    return result.scalar_one_or_none()


async def get_active_tenant_membership(
    db: AsyncSession, user_id: str, tenant_id: str
) -> UserTenant | None:
    """Retorna a associação ativa do usuário com o tenant, incluindo o papel."""
    result = await db.execute(
        select(UserTenant)
        .options(joinedload(UserTenant.role))
        .where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == tenant_id,
            UserTenant.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
