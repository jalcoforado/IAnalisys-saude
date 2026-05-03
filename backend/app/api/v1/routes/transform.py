"""
Endpoints de transformação STAGING → CORE.

POST /transform/clinicorp/static            — todas as 8 entidades estáticas
POST /transform/clinicorp/{entity}          — uma entidade específica
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.transform import TransformResponse, TransformResultItem
from app.transformations.clinicorp_to_core import (
    transform_all_static,
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


@router.post("/clinicorp/static", response_model=TransformResponse, status_code=200)
async def transform_clinicorp_static(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransformResponse:
    """Transforma as 8 entidades estáticas Clinicorp staging → core."""
    tenant_id = _require_tenant(current_user)
    results = await transform_all_static(db, tenant_id)
    items = [_to_item(r) for r in results]
    return TransformResponse(
        results=items,
        total_inserted=sum(i.inserted for i in items),
        total_updated=sum(i.updated for i in items),
        total_errors=sum(i.errors for i in items),
    )


@router.post("/clinicorp/{entity}", response_model=TransformResultItem, status_code=200)
async def transform_clinicorp_entity(
    entity: str,
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransformResultItem:
    """Transforma UMA entidade Clinicorp staging → core."""
    tenant_id = _require_tenant(current_user)
    try:
        result = await transform_static_entity(db, tenant_id, entity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _to_item(result)


@router.get("/status", response_model=List[TransformResultItem])
async def transform_status(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[TransformResultItem]:
    """
    Retorna contagem atual em cada core_* (não dispara transformação).
    Útil pra dashboard verificar diff entre staging e core.
    """
    from sqlalchemy import func, select

    from app.transformations.clinicorp_to_core import STATIC_TRANSFORMS

    tenant_id = _require_tenant(current_user)
    items: list[TransformResultItem] = []
    for spec in STATIC_TRANSFORMS:
        # Conta no staging
        stg_count_q = await db.execute(
            select(func.count())
            .select_from(spec.staging_model)
            .where(spec.staging_model.tenant_id == tenant_id)
        )
        # Conta no core
        core_count_q = await db.execute(
            select(func.count())
            .select_from(spec.core_model)
            .where(spec.core_model.tenant_id == tenant_id)
        )
        items.append(TransformResultItem(
            entity=spec.name,
            fetched=int(stg_count_q.scalar_one() or 0),
            inserted=int(core_count_q.scalar_one() or 0),
            updated=0,
            errors=0,
        ))
    return items
