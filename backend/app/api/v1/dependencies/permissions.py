"""Dependency `requires(*codes)` para proteger endpoints por permission.

Uso típico:

    @router.post("/financeiro/lancamento")
    async def criar_lancamento(
        user: UserMe = Depends(requires("financeiro.write")),
    ):
        ...

`is_saas_admin = True` é bypass total — não passa por permission check.
"""
from fastapi import Depends, HTTPException, status

from app.api.v1.dependencies.auth import get_current_user
from app.schemas.auth import UserMe


def requires(*codes: str):
    """Retorna dependency que valida se o usuário tem TODAS as permissions listadas."""

    async def _dep(user: UserMe = Depends(get_current_user)) -> UserMe:
        if user.is_saas_admin:
            return user
        user_perms = set(user.permissions or [])
        missing = set(codes) - user_perms
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissões faltando: {', '.join(sorted(missing))}",
            )
        return user

    return _dep
