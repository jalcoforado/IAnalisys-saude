"""
Endpoints de sincronização Clinicorp.

POST /sync/clinicorp/static                   — 8 entidades estáticas
POST /sync/clinicorp/transactional            — 1 entidade transacional / 1 mês
POST /sync/clinicorp/transactional/batch      — N entidades transacionais / 1 mês
POST /sync/clinicorp/kpis_monthly             — 10 endpoints agregados / 1 mês
GET  /sync/jobs                               — lista jobs de sync recentes
GET  /sync/checkpoints                        — estado por entidade
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.integrations.clinicorp.sync_service import (
    get_entity_spec,
    sync_all_static,
    sync_kpis_monthly,
    sync_transactional_batch,
    sync_transactional_entity,
    TRANSACTIONAL_ENTITIES,
)
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_job import SyncJob
from app.schemas.auth import UserMe
from app.schemas.sync import (
    CheckpointResponse,
    KpisMonthlyRequest,
    StaticSyncResponse,
    SyncJobResponse,
    TransactionalBatchRequest,
    TransactionalSyncRequest,
    TransactionalSyncResponse,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


@router.post("/clinicorp/static", response_model=StaticSyncResponse, status_code=200)
async def sync_clinicorp_static(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> StaticSyncResponse:
    """
    Dispara sync das 8 entidades estáticas Clinicorp.
    Cada entidade gera um SyncJob independente. Falhas isoladas
    não interrompem as demais.
    """
    tenant_id = _require_tenant(current_user)
    jobs = await sync_all_static(db, tenant_id)
    return StaticSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/clinicorp/transactional", response_model=SyncJobResponse, status_code=200)
async def sync_clinicorp_transactional(
    payload: TransactionalSyncRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """Sincroniza UMA entidade transacional cobrindo o mês indicado."""
    tenant_id = _require_tenant(current_user)
    try:
        spec = get_entity_spec(payload.entity)
        if spec not in TRANSACTIONAL_ENTITIES:
            raise ValueError(f"Entidade '{payload.entity}' não é transacional.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        job = await sync_transactional_entity(db, tenant_id, spec, payload.year, payload.month)
    except ValueError as exc:  # ex: mês ainda não começou
        raise HTTPException(status_code=400, detail=str(exc))

    return SyncJobResponse.model_validate(job)


@router.post("/clinicorp/transactional/batch", response_model=TransactionalSyncResponse, status_code=200)
async def sync_clinicorp_transactional_batch(
    payload: TransactionalBatchRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> TransactionalSyncResponse:
    """Sincroniza várias entidades transacionais num único mês."""
    tenant_id = _require_tenant(current_user)
    try:
        jobs = await sync_transactional_batch(
            db, tenant_id, payload.year, payload.month, payload.entities,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TransactionalSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/clinicorp/kpis_monthly", response_model=SyncJobResponse, status_code=200)
async def sync_clinicorp_kpis_monthly(
    payload: KpisMonthlyRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """
    Sincroniza os 10 endpoints agregados num único job mensal,
    com chamadas em paralelo. Grava 1 linha em stg_cc_kpis_monthly.
    """
    tenant_id = _require_tenant(current_user)
    try:
        job = await sync_kpis_monthly(db, tenant_id, payload.year, payload.month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SyncJobResponse.model_validate(job)


@router.get("/jobs", response_model=List[SyncJobResponse])
async def list_sync_jobs(
    limit: int = 50,
    entity: str | None = None,
    year: int | None = None,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> List[SyncJobResponse]:
    """
    Lista jobs de sync do tenant.
    - `limit` (default 50): número máximo de jobs.
    - `entity` (opcional): filtra por nome da entidade.
    - `year` (opcional): filtra jobs cujo period_from caia no ano (heatmap).
    """
    from datetime import date as _date
    tenant_id = _require_tenant(current_user)
    stmt = select(SyncJob).where(SyncJob.tenant_id == tenant_id)
    if entity:
        stmt = stmt.where(SyncJob.entity == entity)
    if year is not None:
        stmt = stmt.where(
            SyncJob.period_from >= _date(year, 1, 1),
            SyncJob.period_from <= _date(year, 12, 31),
        )
    stmt = stmt.order_by(desc(SyncJob.created_at)).limit(limit)
    result = await db.execute(stmt)
    return [SyncJobResponse.model_validate(j) for j in result.scalars().all()]


@router.get("/checkpoints", response_model=List[CheckpointResponse])
async def list_checkpoints(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> List[CheckpointResponse]:
    """Estado atual de sync por entidade do tenant."""
    tenant_id = _require_tenant(current_user)
    result = await db.execute(
        select(SyncCheckpoint).where(SyncCheckpoint.tenant_id == tenant_id)
    )
    return [CheckpointResponse.model_validate(c) for c in result.scalars().all()]
