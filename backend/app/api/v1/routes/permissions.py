"""
Endpoints de RBAC: catálogo de permissions, roles do tenant e matriz editável.

GET /permissions               — catálogo completo (read-only)
GET /roles                     — roles + permissions atuais no tenant
PUT /roles/{role_id}/permissions — substitui matriz da role pra esse tenant
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.models.permission import Permission, RolePermission
from app.models.role import Role
from app.schemas.auth import UserMe
from app.schemas.permission import (
    GenericMessage,
    PermissionResponse,
    RoleWithPermissionsResponse,
    UpdateRolePermissionsRequest,
)


router = APIRouter(tags=["rbac"])


# ROLES protegidas — não podem ter permissões editadas via UI
# saas_admin: bypass total no código, não faz sentido editar
# tenant_admin: dono do tenant precisa ter tudo, evitar lock-out
PROTECTED_ROLES = {"saas_admin", "tenant_admin"}


@router.get("/permissions", response_model=list[PermissionResponse])
async def list_permissions(
    _: UserMe = Depends(requires("empresa.permissions.manage")),
    db: AsyncSession = Depends(get_db),
) -> list[PermissionResponse]:
    """Catálogo completo (ordenado por módulo, depois code)."""
    result = await db.execute(
        select(Permission).order_by(Permission.module, Permission.code)
    )
    perms = result.scalars().all()
    return [PermissionResponse.model_validate(p) for p in perms]


@router.get("/roles", response_model=list[RoleWithPermissionsResponse])
async def list_roles_with_permissions(
    current_user: UserMe = Depends(requires("empresa.permissions.manage")),
    db: AsyncSession = Depends(get_db),
) -> list[RoleWithPermissionsResponse]:
    """Roles existentes + permissions atribuídas a cada uma NO TENANT do user logado."""
    tenant_id = current_user.tenant_id

    roles_result = await db.execute(select(Role).order_by(Role.name))
    roles = roles_result.scalars().all()

    matrix_result = await db.execute(
        select(RolePermission.role_id, Permission.code)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(RolePermission.tenant_id == tenant_id)
    )
    by_role: dict[str, list[str]] = {}
    for role_id, code in matrix_result.all():
        by_role.setdefault(role_id, []).append(code)

    return [
        RoleWithPermissionsResponse(
            id=r.id,
            name=r.name,
            description=r.description,
            permissions=sorted(by_role.get(r.id, [])),
        )
        for r in roles
    ]


@router.put("/roles/{role_id}/permissions", response_model=GenericMessage)
async def update_role_permissions(
    role_id: str,
    payload: UpdateRolePermissionsRequest,
    current_user: UserMe = Depends(requires("empresa.permissions.manage")),
    db: AsyncSession = Depends(get_db),
) -> GenericMessage:
    """Substitui a matriz da role no tenant logado."""
    tenant_id = current_user.tenant_id

    # Valida role
    role = (await db.execute(select(Role).where(Role.id == role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role não encontrada.")

    if role.name in PROTECTED_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A role '{role.name}' não pode ter permissões alteradas.",
        )

    # Resolve codes -> ids (silenciando codes desconhecidos por hora)
    if payload.permission_codes:
        result = await db.execute(
            select(Permission.id).where(Permission.code.in_(payload.permission_codes))
        )
        permission_ids = list(result.scalars().all())
    else:
        permission_ids = []

    # Apaga e regrava matriz da role nesse tenant
    await db.execute(
        delete(RolePermission).where(
            RolePermission.tenant_id == tenant_id,
            RolePermission.role_id == role_id,
        )
    )
    for pid in permission_ids:
        db.add(RolePermission(
            tenant_id=tenant_id,
            role_id=role_id,
            permission_id=pid,
        ))
    await db.commit()

    return GenericMessage(message=f"Matriz da role '{role.name}' atualizada com {len(permission_ids)} permissões.")
