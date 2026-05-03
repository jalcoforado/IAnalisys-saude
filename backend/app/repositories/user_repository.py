from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.user import User
from app.models.user_tenant import UserTenant
from app.models.permission import Permission, RolePermission


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


async def list_active_memberships(
    db: AsyncSession, user_id: str
) -> list[UserTenant]:
    result = await db.execute(
        select(UserTenant)
        .options(joinedload(UserTenant.role))
        .where(
            UserTenant.user_id == user_id,
            UserTenant.is_active.is_(True),
        )
    )
    return list(result.scalars().all())


async def list_permission_codes(
    db: AsyncSession, tenant_id: str, role_id: str
) -> list[str]:
    """Retorna codes de permissions atribuídos à role nesse tenant."""
    result = await db.execute(
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == role_id,
        )
    )
    return list(result.scalars().all())


async def list_all_permission_codes(db: AsyncSession) -> list[str]:
    """Catálogo completo (usado pra dar 'tudo' a saas_admin sem matriz)."""
    result = await db.execute(select(Permission.code))
    return list(result.scalars().all())
