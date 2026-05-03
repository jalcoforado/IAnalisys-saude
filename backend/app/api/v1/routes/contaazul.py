"""
Rotas OAuth e status da integração Conta Azul.

GET  /contaazul/status       — status da conexão do tenant
GET  /contaazul/auth         — gera URL de autorização OAuth
GET  /contaazul/callback     — recebe code do Conta Azul e salva token
POST /contaazul/refresh      — renova access_token via refresh_token
DELETE /contaazul/disconnect — remove token do tenant
"""
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.integrations.contaazul.oauth import (
    ContaAzulOAuthError,
    build_authorization_url,
    exchange_code_for_token,
    refresh_access_token,
)
from app.models.contaazul_token import ContaAzulToken
from app.schemas.auth import UserMe
from app.schemas.contaazul import ContaAzulAuthUrlResponse, ContaAzulStatusResponse

router = APIRouter(prefix="/contaazul", tags=["contaazul"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_token(db: AsyncSession, tenant_id: str) -> ContaAzulToken | None:
    result = await db.execute(
        select(ContaAzulToken).where(ContaAzulToken.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


@router.get("/status", response_model=ContaAzulStatusResponse)
async def contaazul_status(
    current_user: UserMe = Depends(requires("empresa.settings.read")),
    db: AsyncSession = Depends(get_db),
) -> ContaAzulStatusResponse:
    """Retorna o status da conexão Conta Azul do tenant."""
    token = await _get_token(db, current_user.tenant_id)
    if not token:
        return ContaAzulStatusResponse(connected=False, status="desconectado")

    is_expired = _now_utc() >= token.expires_at
    return ContaAzulStatusResponse(
        connected=not is_expired,
        status="expirado" if is_expired else "ativo",
        expires_at=token.expires_at,
        connected_at=token.created_at,
    )


@router.get("/auth", response_model=ContaAzulAuthUrlResponse)
async def contaazul_auth_url(
    current_user: UserMe = Depends(requires("empresa.settings.write")),
) -> ContaAzulAuthUrlResponse:
    """Retorna a URL de autorização OAuth para o frontend redirecionar o usuário."""
    state = secrets.token_hex(16)
    url = build_authorization_url(state)
    return ContaAzulAuthUrlResponse(auth_url=url)


@router.get("/callback")
async def contaazul_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Callback OAuth do Conta Azul.
    Recebe o authorization code e troca por access_token + refresh_token.

    Como usar:
    - O frontend deve incluir tenant_id no state ou como query param ao iniciar o fluxo
    - Para testes: GET /api/v1/contaazul/callback?code=CODE&tenant_id=TENANT_ID
    """
    if error:
        raise HTTPException(status_code=400, detail=f"Conta Azul retornou erro: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Código de autorização não recebido.")
    if not tenant_id:
        # Em produção, tenant_id viria no state (codificado)
        raise HTTPException(
            status_code=400,
            detail="tenant_id obrigatório. Inclua como query param: ?code=CODE&tenant_id=UUID",
        )

    try:
        token_data = await exchange_code_for_token(code)
    except ContaAzulOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Upsert: remove token anterior se existir
    await db.execute(
        delete(ContaAzulToken).where(ContaAzulToken.tenant_id == tenant_id)
    )
    db.add(ContaAzulToken(
        tenant_id=tenant_id,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_at=token_data["expires_at"],
    ))
    await db.commit()

    return {"status": "conectado", "expires_at": token_data["expires_at"].isoformat()}


@router.post("/refresh", response_model=ContaAzulStatusResponse)
async def contaazul_refresh(
    current_user: UserMe = Depends(requires("empresa.settings.write")),
    db: AsyncSession = Depends(get_db),
) -> ContaAzulStatusResponse:
    """Renova o access_token usando o refresh_token salvo."""
    token = await _get_token(db, current_user.tenant_id)
    if not token:
        raise HTTPException(status_code=404, detail="Conta Azul não conectada.")

    try:
        new_data = await refresh_access_token(token.refresh_token)
    except ContaAzulOAuthError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    token.access_token = new_data["access_token"]
    token.refresh_token = new_data["refresh_token"]
    token.expires_at = new_data["expires_at"]
    token.updated_at = _now_utc()
    await db.commit()
    await db.refresh(token)

    return ContaAzulStatusResponse(
        connected=True,
        status="ativo",
        expires_at=token.expires_at,
        connected_at=token.created_at,
    )


@router.delete("/disconnect", status_code=204)
async def contaazul_disconnect(
    current_user: UserMe = Depends(requires("empresa.settings.write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove o token Conta Azul do tenant (desconecta)."""
    await db.execute(
        delete(ContaAzulToken).where(ContaAzulToken.tenant_id == current_user.tenant_id)
    )
    await db.commit()
