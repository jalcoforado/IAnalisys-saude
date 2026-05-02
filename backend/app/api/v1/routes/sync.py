"""
Endpoints de sincronização de dados externos.

POST /sync/clinicorp  — dispara sync para o tenant autenticado
GET  /sync/status     — lista os últimos jobs de sync do tenant
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.integrations.clinicorp.sync_service import run_clinicorp_sync
from app.models.sync_job import SyncJob
from app.schemas.auth import UserMe
from app.schemas.sync import SyncJobResponse, SyncRequest

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/clinicorp", response_model=SyncJobResponse, status_code=202)
async def sync_clinicorp(
    payload: SyncRequest,
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """
    Busca dados da Clinicorp para o período informado e salva no staging.
    Requer autenticação — usa o tenant_id do usuário logado.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")

    job = await run_clinicorp_sync(
        db=db,
        tenant_id=current_user.tenant_id,
        from_date=payload.from_date,
        to_date=payload.to_date,
    )
    return SyncJobResponse.model_validate(job)


@router.get("/status", response_model=List[SyncJobResponse])
async def sync_status(
    limit: int = 20,
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SyncJobResponse]:
    """Retorna os últimos N jobs de sync do tenant autenticado."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")

    result = await db.execute(
        select(SyncJob)
        .where(SyncJob.tenant_id == current_user.tenant_id)
        .order_by(desc(SyncJob.created_at))
        .limit(limit)
    )
    jobs = result.scalars().all()
    return [SyncJobResponse.model_validate(j) for j in jobs]
