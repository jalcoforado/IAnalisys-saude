"""
Endpoints de transformação STAGING → CORE.

POST /transform/clinicorp/static            — todas as 8 entidades estáticas
POST /transform/clinicorp/events            — 6 eventos (estimates emite 2 outputs)
POST /transform/clinicorp/all               — cadastros + eventos
POST /transform/clinicorp/{entity}          — uma entidade específica
GET  /transform/status                      — counts staging vs core
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.core import CoreEstimateProcedures, CoreEstimates
from app.models.staging import StgCcEstimates
from app.schemas.auth import UserMe
from app.schemas.transform import TransformResponse, TransformResultItem
from app.transformations.clinicorp_to_core import (
    EVENT_TRANSFORMS,
    STATIC_TRANSFORMS,
    transform_all,
    transform_all_events,
    transform_all_static,
    transform_estimates,
    transform_static_entity,
)

router = APIRouter(prefix="/transform", tags=["transform"])


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


def _to_item(r) -> TransformResultItem:
    return TransformResultItem(
        entity=r.entity, fetched=r.fetched,
        inserted=r.inserted, updated=r.updated, errors=r.errors,
    )


def _aggregate(items: list[TransformResultItem]) -> TransformResponse:
    return TransformResponse(
        results=items,
        total_inserted=sum(i.inserted for i in items),
        total_updated=sum(i.updated for i in items),
        total_errors=sum(i.errors for i in items),
    )


@router.post("/clinicorp/static", response_model=TransformResponse, status_code=200)
async def transform_clinicorp_static(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransformResponse:
    """Transforma as 8 entidades estáticas Clinicorp staging → core."""
    tenant_id = _require_tenant(current_user)
    results = await transform_all_static(db, tenant_id)
    return _aggregate([_to_item(r) for r in results])


@router.post("/clinicorp/events", response_model=TransformResponse, status_code=200)
async def transform_clinicorp_events(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransformResponse:
    """Transforma os 6 eventos Clinicorp (5 simples + estimates com line items)."""
    tenant_id = _require_tenant(current_user)
    results = await transform_all_events(db, tenant_id)
    return _aggregate([_to_item(r) for r in results])


@router.post("/clinicorp/all", response_model=TransformResponse, status_code=200)
async def transform_clinicorp_all(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransformResponse:
    """Transforma cadastros + eventos. Não inclui core_patients (PR-5c)."""
    tenant_id = _require_tenant(current_user)
    results = await transform_all(db, tenant_id)
    return _aggregate([_to_item(r) for r in results])


@router.post("/clinicorp/{entity}", response_model=TransformResponse, status_code=200)
async def transform_clinicorp_entity(
    entity: str,
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransformResponse:
    """Transforma UMA entidade Clinicorp staging → core. Para 'estimates' devolve 2 resultados."""
    tenant_id = _require_tenant(current_user)
    try:
        if entity == "estimates":
            header_r, proc_r = await transform_estimates(db, tenant_id)
            items = [_to_item(header_r), _to_item(proc_r)]
        else:
            result = await transform_static_entity(db, tenant_id, entity)
            items = [_to_item(result)]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _aggregate(items)


@router.get("/status", response_model=List[TransformResultItem])
async def transform_status(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TransformResultItem]:
    """
    Retorna contagem atual em cada core_* (não dispara transformação).
    Útil pra dashboard verificar diff entre staging e core.
    """
    tenant_id = _require_tenant(current_user)
    items: list[TransformResultItem] = []

    # Static + simple events: usam staging→core 1:1
    for spec in (*STATIC_TRANSFORMS, *EVENT_TRANSFORMS):
        stg_count_q = await db.execute(
            select(func.count())
            .select_from(spec.staging_model)
            .where(spec.staging_model.tenant_id == tenant_id)
        )
        core_count_q = await db.execute(
            select(func.count())
            .select_from(spec.core_model)
            .where(spec.core_model.tenant_id == tenant_id)
        )
        items.append(TransformResultItem(
            entity=spec.name,
            fetched=int(stg_count_q.scalar_one() or 0),
            inserted=int(core_count_q.scalar_one() or 0),
            updated=0, errors=0,
        ))

    # Estimates (header) + estimate_procedures (line items)
    stg_est_q = await db.execute(
        select(func.count()).select_from(StgCcEstimates).where(StgCcEstimates.tenant_id == tenant_id)
    )
    core_est_q = await db.execute(
        select(func.count()).select_from(CoreEstimates).where(CoreEstimates.tenant_id == tenant_id)
    )
    items.append(TransformResultItem(
        entity="estimates",
        fetched=int(stg_est_q.scalar_one() or 0),
        inserted=int(core_est_q.scalar_one() or 0),
        updated=0, errors=0,
    ))
    core_proc_q = await db.execute(
        select(func.count()).select_from(CoreEstimateProcedures).where(CoreEstimateProcedures.tenant_id == tenant_id)
    )
    items.append(TransformResultItem(
        entity="estimate_procedures",
        fetched=0,  # não tem staging próprio (vem nested)
        inserted=int(core_proc_q.scalar_one() or 0),
        updated=0, errors=0,
    ))

    return items
