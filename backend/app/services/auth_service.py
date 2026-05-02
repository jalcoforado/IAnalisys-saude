from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import user_repository
from app.security.password import verify_password
from app.security.jwt import create_access_token
from app.schemas.auth import TokenResponse, UserMe


class AuthError(Exception):
    pass


async def login(
    db: AsyncSession,
    email: str,
    password: str,
    tenant_id: str,
) -> TokenResponse:
    user = await user_repository.get_by_email(db, email)

    if not user or not verify_password(password, user.hashed_password):
        raise AuthError("Credenciais inválidas.")

    if not user.is_active:
        raise AuthError("Usuário inativo.")

    # saas_admin pode acessar qualquer tenant sem precisar de membership
    if not user.is_saas_admin:
        membership = await user_repository.get_active_tenant_membership(
            db, user.id, tenant_id
        )
        if not membership:
            raise AuthError("Acesso não autorizado para este tenant.")

    token = create_access_token(
        data={
            "sub": user.id,
            "tenant_id": tenant_id,
            "is_saas_admin": user.is_saas_admin,
        }
    )
    return TokenResponse(access_token=token)


async def get_current_user_data(
    db: AsyncSession,
    user_id: str,
    tenant_id: str,
) -> UserMe:
    user = await user_repository.get_by_id(db, user_id)
    if not user or not user.is_active:
        raise AuthError("Usuário não encontrado.")

    role = "saas_admin"
    if not user.is_saas_admin:
        membership = await user_repository.get_active_tenant_membership(
            db, user_id, tenant_id
        )
        if not membership:
            raise AuthError("Acesso não autorizado para este tenant.")
        role = membership.role.name

    return UserMe(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_saas_admin=user.is_saas_admin,
        tenant_id=tenant_id,
        role=role,
    )
