"""
Endpoints da camada ANALYTICS.

POST /analytics/rebuild/dim_tempo  — popula calendário (default 2019..2030)
GET  /analytics/status             — counts das tabelas analytics
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.analytics import DimTempo
from app.schemas.auth import UserMe
from app.transformations.core_to_analytics import build_dim_tempo

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


class DimTempoRebuildRequest(BaseModel):
    start_year: int = Field(2019, ge=1900, le=2100)
    end_year: int = Field(2030, ge=1900, le=2100)


class BuilderResultResponse(BaseModel):
    entity: str
    rows_built: int
    inserted: int
    updated: int


class AnalyticsStatusItem(BaseModel):
    table: str
    rows: int


@router.post("/rebuild/dim_tempo", response_model=BuilderResultResponse, status_code=200)
async def rebuild_dim_tempo(
    payload: DimTempoRebuildRequest = DimTempoRebuildRequest(),
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuilderResultResponse:
    """Popula dim_tempo cobrindo o intervalo de anos. Idempotente."""
    _require_tenant(current_user)
    if payload.end_year < payload.start_year:
        raise HTTPException(status_code=400, detail="end_year < start_year")
    result = await build_dim_tempo(db, payload.start_year, payload.end_year)
    return BuilderResultResponse(
        entity=result.entity,
        rows_built=result.rows_built,
        inserted=result.inserted,
        updated=result.updated,
    )


@router.get("/status", response_model=List[AnalyticsStatusItem])
async def analytics_status(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AnalyticsStatusItem]:
    """Counts de cada tabela analytics. Útil para verificar o pipeline."""
    _require_tenant(current_user)
    items: list[AnalyticsStatusItem] = []

    # dim_tempo (universal — sem tenant)
    q = await db.execute(select(func.count()).select_from(DimTempo))
    items.append(AnalyticsStatusItem(table="dim_tempo", rows=int(q.scalar_one() or 0)))

    return items
