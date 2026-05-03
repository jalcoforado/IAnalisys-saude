"""
Endpoints de configuração do tenant (white-label).

GET    /tenant/settings              — retorna config do tenant atual
PUT    /tenant/settings              — atualiza dados textuais
POST   /tenant/uploads/{kind}        — upload de imagem (logo|favicon|login_background)
DELETE /tenant/uploads/{kind}        — remove imagem

Permissão: somente usuários com role == 'admin' podem editar.
Leitura é permitida a qualquer usuário autenticado do tenant.
"""
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.tenant import Tenant
from app.schemas.auth import UserMe
from app.schemas.tenant import TenantSettingsResponse, TenantSettingsUpdate, UploadResponse


router = APIRouter(prefix="/tenant", tags=["tenant"])

UPLOAD_ROOT = Path("/app/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

UPLOAD_KINDS = {
    "logo": {
        "max_bytes": 1_000_000,        # 1 MB
        "allowed_mime": {"image/png", "image/jpeg", "image/svg+xml", "image/webp"},
        "field": "logo_url",
    },
    "favicon": {
        "max_bytes": 200_000,          # 200 KB
        "allowed_mime": {"image/png", "image/x-icon", "image/vnd.microsoft.icon", "image/svg+xml"},
        "field": "favicon_url",
    },
    "login_background": {
        "max_bytes": 3_000_000,        # 3 MB
        "allowed_mime": {"image/png", "image/jpeg", "image/webp"},
        "field": "login_background_url",
    },
}


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


_ADMIN_ROLES = {"tenant_admin", "saas_admin"}


def _require_admin(user: UserMe) -> None:
    """Apenas tenant_admin (ou saas_admin) pode editar."""
    if user.is_saas_admin:
        return
    if (user.role or "").lower() not in _ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem editar configurações da empresa.",
        )


async def _get_tenant(db: AsyncSession, tenant_id: str) -> Tenant:
    q = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    t = q.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Tenant não encontrado.")
    return t


@router.get("/settings", response_model=TenantSettingsResponse)
async def get_settings(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantSettingsResponse:
    tenant_id = _require_tenant(current_user)
    tenant = await _get_tenant(db, tenant_id)
    return TenantSettingsResponse.model_validate(tenant)


@router.put("/settings", response_model=TenantSettingsResponse)
async def update_settings(
    payload: TenantSettingsUpdate,
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TenantSettingsResponse:
    _require_admin(current_user)
    tenant_id = _require_tenant(current_user)
    tenant = await _get_tenant(db, tenant_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)

    await db.commit()
    await db.refresh(tenant)
    return TenantSettingsResponse.model_validate(tenant)


@router.post("/uploads/{kind}", response_model=UploadResponse)
async def upload_asset(
    kind: Literal["logo", "favicon", "login_background"],
    file: UploadFile = File(...),
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    _require_admin(current_user)
    tenant_id = _require_tenant(current_user)
    tenant = await _get_tenant(db, tenant_id)

    spec = UPLOAD_KINDS[kind]

    # Mime type
    if file.content_type not in spec["allowed_mime"]:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de arquivo não permitido. Aceitos: {', '.join(sorted(spec['allowed_mime']))}",
        )

    # Lê em chunks pra controlar tamanho
    content = await file.read()
    if len(content) > spec["max_bytes"]:
        raise HTTPException(
            status_code=400,
            detail=f"Arquivo excede o limite de {spec['max_bytes'] // 1000} KB.",
        )

    # Determinar extensão a partir do mime (estável e seguro)
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/svg+xml": "svg",
        "image/webp": "webp",
        "image/x-icon": "ico",
        "image/vnd.microsoft.icon": "ico",
    }
    ext = ext_map.get(file.content_type or "", "bin")

    # Salva em /app/uploads/{tenant_id}/{kind}.{ext}
    tenant_dir = UPLOAD_ROOT / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    # Remove versão anterior em outras extensões para esse kind
    for old in tenant_dir.glob(f"{kind}.*"):
        try:
            old.unlink()
        except OSError:
            pass

    out_path = tenant_dir / f"{kind}.{ext}"
    out_path.write_bytes(content)

    # URL pública (servido como estático)
    url = f"/uploads/{tenant_id}/{kind}.{ext}"
    setattr(tenant, spec["field"], url)
    await db.commit()

    return UploadResponse(kind=kind, url=url, size_bytes=len(content))


@router.delete("/uploads/{kind}", status_code=204)
async def delete_asset(
    kind: Literal["logo", "favicon", "login_background"],
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _require_admin(current_user)
    tenant_id = _require_tenant(current_user)
    tenant = await _get_tenant(db, tenant_id)

    spec = UPLOAD_KINDS[kind]
    tenant_dir = UPLOAD_ROOT / tenant_id
    for old in tenant_dir.glob(f"{kind}.*"):
        try:
            old.unlink()
        except OSError:
            pass

    setattr(tenant, spec["field"], None)
    await db.commit()
