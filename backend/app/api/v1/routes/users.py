"""
Endpoints administrativos de usuários do tenant.

GET    /users           — lista usuários ativos+inativos do tenant
POST   /users/invite    — cria usuário e envia convite por email
PATCH  /users/{id}      — edita full_name, role, is_active
DELETE /users/{id}      — desativa (is_active = false)
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.models.role import Role
from app.models.tenant import Tenant
from app.models.user import User
from app.models.user_tenant import UserTenant
from app.schemas.auth import UserMe
from app.schemas.user_admin import (
    UserActionResponse,
    UserInviteRequest,
    UserListItem,
    UserUpdateRequest,
)
from app.security.password import hash_password
from app.services.password_reset_service import create_invite_token


router = APIRouter(prefix="/users", tags=["users"])


PROTECTED_ROLES_REASSIGN = {"saas_admin"}  # role saas_admin nunca atribuível via UI do tenant


async def _list_tenant_users(db: AsyncSession, tenant_id: str) -> list[UserListItem]:
    result = await db.execute(
        select(User, UserTenant, Role)
        .join(UserTenant, UserTenant.user_id == User.id)
        .join(Role, Role.id == UserTenant.role_id)
        .where(UserTenant.tenant_id == tenant_id, User.deleted_at.is_(None))
        .order_by(User.full_name)
    )
    out: list[UserListItem] = []
    for user, ut, role in result.all():
        out.append(UserListItem(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active and ut.is_active,
            role_id=role.id,
            role_name=role.name,
        ))
    return out


async def _get_user_membership(
    db: AsyncSession, user_id: str, tenant_id: str
) -> tuple[User, UserTenant]:
    result = await db.execute(
        select(User, UserTenant)
        .join(UserTenant, UserTenant.user_id == User.id)
        .where(
            User.id == user_id,
            UserTenant.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
        .options(joinedload(UserTenant.role))
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Usuário não encontrado neste tenant.")
    return row[0], row[1]


@router.get("", response_model=list[UserListItem])
async def list_users(
    current_user: UserMe = Depends(requires("usuarios.read")),
    db: AsyncSession = Depends(get_db),
) -> list[UserListItem]:
    return await _list_tenant_users(db, current_user.tenant_id)


@router.post("/invite", response_model=UserActionResponse, status_code=201)
async def invite_user(
    payload: UserInviteRequest,
    current_user: UserMe = Depends(requires("usuarios.invite")),
    db: AsyncSession = Depends(get_db),
) -> UserActionResponse:
    tenant_id = current_user.tenant_id

    # Valida role
    role = (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=400, detail="Role inválida.")
    if role.name in PROTECTED_ROLES_REASSIGN:
        raise HTTPException(
            status_code=400,
            detail=f"A role '{role.name}' não pode ser atribuída via UI.",
        )

    # Tenant pra mensagem do email
    tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one_or_none()
    tenant_name = tenant.legal_name or tenant.name if tenant else "sua clínica"

    # Email já existe?
    existing = (
        await db.execute(select(User).where(User.email == payload.email, User.deleted_at.is_(None)))
    ).scalar_one_or_none()

    if existing:
        # Já é membro deste tenant?
        already_member = (
            await db.execute(
                select(UserTenant).where(
                    UserTenant.user_id == existing.id,
                    UserTenant.tenant_id == tenant_id,
                )
            )
        ).scalar_one_or_none()
        if already_member:
            raise HTTPException(status_code=409, detail="Este email já é membro do tenant.")

        # Existe em outro tenant — adiciona membership só, sem reset de senha
        db.add(UserTenant(
            user_id=existing.id,
            tenant_id=tenant_id,
            role_id=payload.role_id,
            is_active=True,
        ))
        await db.commit()
        return UserActionResponse(
            id=existing.id,
            message=f"Usuário {existing.email} adicionado ao tenant. Ele já tem senha cadastrada.",
        )

    # Cria usuário novo com senha placeholder (substituída pelo fluxo de invite)
    placeholder_pwd = hash_password(secrets.token_hex(16))
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=placeholder_pwd,
        is_active=True,
        is_saas_admin=False,
    )
    db.add(user)
    await db.flush()  # gera o id

    db.add(UserTenant(
        user_id=user.id,
        tenant_id=tenant_id,
        role_id=payload.role_id,
        is_active=True,
    ))
    await db.commit()

    # Token de convite + email
    await create_invite_token(db, user=user, tenant_name=tenant_name)

    return UserActionResponse(
        id=user.id,
        message=f"Convite enviado para {user.email}. Link válido por 72 horas.",
    )


@router.patch("/{user_id}", response_model=UserActionResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    current_user: UserMe = Depends(requires("usuarios.edit")),
    db: AsyncSession = Depends(get_db),
) -> UserActionResponse:
    if user_id == current_user.id:
        # Tenant_admin não pode alterar a própria role/status — evita lock-out
        if payload.role_id is not None or payload.is_active is False:
            raise HTTPException(
                status_code=400,
                detail="Você não pode alterar sua própria role ou se desativar.",
            )

    user, ut = await _get_user_membership(db, user_id, current_user.tenant_id)

    # saas_admin externos não podem ser editados via UI do tenant
    if user.is_saas_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuários SaaS Admin não podem ser editados aqui.",
        )

    if payload.full_name is not None:
        user.full_name = payload.full_name

    if payload.role_id is not None:
        role = (await db.execute(select(Role).where(Role.id == payload.role_id))).scalar_one_or_none()
        if not role:
            raise HTTPException(status_code=400, detail="Role inválida.")
        if role.name in PROTECTED_ROLES_REASSIGN:
            raise HTTPException(
                status_code=400,
                detail=f"A role '{role.name}' não pode ser atribuída via UI.",
            )
        ut.role_id = role.id

    if payload.is_active is not None:
        ut.is_active = payload.is_active
        # Se for o único tenant do user, espelhar em users.is_active também
        # Por simplicidade, mantemos os 2 sincronizados.
        user.is_active = payload.is_active

    await db.commit()
    return UserActionResponse(id=user.id, message="Usuário atualizado.")


@router.delete("/{user_id}", response_model=UserActionResponse)
async def deactivate_user(
    user_id: str,
    current_user: UserMe = Depends(requires("usuarios.deactivate")),
    db: AsyncSession = Depends(get_db),
) -> UserActionResponse:
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Você não pode se desativar.")

    user, ut = await _get_user_membership(db, user_id, current_user.tenant_id)

    if user.is_saas_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SaaS Admin não pode ser desativado aqui.",
        )

    ut.is_active = False
    user.is_active = False
    await db.commit()
    return UserActionResponse(id=user.id, message="Usuário desativado.")
