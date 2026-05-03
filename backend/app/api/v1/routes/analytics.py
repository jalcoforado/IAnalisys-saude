"""
Endpoints da camada ANALYTICS.

POST /analytics/rebuild/dim_tempo        — popula calendário (default 2019..2030)
POST /analytics/rebuild/dim_paciente     — materializa dim_paciente de core_patients
POST /analytics/rebuild/dim_profissional — espelha dim_profissional de core_professionals
POST /analytics/rebuild/dimensions       — todas as dimensões em sequência
GET  /analytics/status                   — counts das tabelas analytics
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.analytics import (
    DimPaciente, DimProfissional, DimTempo,
    FatoAgenda, FatoFinanceiro, FatoOrcamentos,
)
from app.schemas.auth import UserMe
from app.transformations.core_to_analytics import (
    build_all_analytics,
    build_all_dimensions,
    build_all_facts,
    build_dim_paciente,
    build_dim_profissional,
    build_dim_tempo,
    build_fato_agenda,
    build_fato_financeiro,
    build_fato_orcamentos,
)

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


def _to_response(r) -> "BuilderResultResponse":
    return BuilderResultResponse(
        entity=r.entity,
        rows_built=r.rows_built,
        inserted=r.inserted,
        updated=r.updated,
    )


class DimensionsResponse(BaseModel):
    results: list[BuilderResultResponse]
    total_inserted: int
    total_updated: int


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
    return _to_response(result)


@router.post("/rebuild/dim_paciente", response_model=BuilderResultResponse, status_code=200)
async def rebuild_dim_paciente(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuilderResultResponse:
    """Materializa dim_paciente a partir de core_patients."""
    tenant_id = _require_tenant(current_user)
    result = await build_dim_paciente(db, tenant_id)
    return _to_response(result)


@router.post("/rebuild/dim_profissional", response_model=BuilderResultResponse, status_code=200)
async def rebuild_dim_profissional(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuilderResultResponse:
    """Espelha dim_profissional a partir de core_professionals."""
    tenant_id = _require_tenant(current_user)
    result = await build_dim_profissional(db, tenant_id)
    return _to_response(result)


@router.post("/rebuild/dimensions", response_model=DimensionsResponse, status_code=200)
async def rebuild_all_dimensions(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DimensionsResponse:
    """Reconstrói todas as dimensões: tempo + paciente + profissional."""
    tenant_id = _require_tenant(current_user)
    results = await build_all_dimensions(db, tenant_id)
    items = [_to_response(r) for r in results]
    return DimensionsResponse(
        results=items,
        total_inserted=sum(i.inserted for i in items),
        total_updated=sum(i.updated for i in items),
    )


@router.post("/rebuild/fato_agenda", response_model=BuilderResultResponse, status_code=200)
async def rebuild_fato_agenda(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuilderResultResponse:
    """Constrói fato_agenda a partir de core_appointments."""
    tenant_id = _require_tenant(current_user)
    return _to_response(await build_fato_agenda(db, tenant_id))


@router.post("/rebuild/fato_orcamentos", response_model=BuilderResultResponse, status_code=200)
async def rebuild_fato_orcamentos(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuilderResultResponse:
    """Constrói fato_orcamentos a partir de core_estimates."""
    tenant_id = _require_tenant(current_user)
    return _to_response(await build_fato_orcamentos(db, tenant_id))


@router.post("/rebuild/fato_financeiro", response_model=BuilderResultResponse, status_code=200)
async def rebuild_fato_financeiro(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BuilderResultResponse:
    """Constrói fato_financeiro a partir de core_payments."""
    tenant_id = _require_tenant(current_user)
    return _to_response(await build_fato_financeiro(db, tenant_id))


@router.post("/rebuild/facts", response_model=DimensionsResponse, status_code=200)
async def rebuild_all_facts(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DimensionsResponse:
    """Reconstrói todos os 3 fatos: agenda + orcamentos + financeiro."""
    tenant_id = _require_tenant(current_user)
    results = await build_all_facts(db, tenant_id)
    items = [_to_response(r) for r in results]
    return DimensionsResponse(
        results=items,
        total_inserted=sum(i.inserted for i in items),
        total_updated=sum(i.updated for i in items),
    )


@router.post("/rebuild/all", response_model=DimensionsResponse, status_code=200)
async def rebuild_all_analytics_endpoint(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DimensionsResponse:
    """Reconstrói toda a camada analytics: dimensões + fatos."""
    tenant_id = _require_tenant(current_user)
    results = await build_all_analytics(db, tenant_id)
    items = [_to_response(r) for r in results]
    return DimensionsResponse(
        results=items,
        total_inserted=sum(i.inserted for i in items),
        total_updated=sum(i.updated for i in items),
    )


@router.get("/status", response_model=List[AnalyticsStatusItem])
async def analytics_status(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AnalyticsStatusItem]:
    """Counts de cada tabela analytics. Útil para verificar o pipeline."""
    tenant_id = _require_tenant(current_user)
    items: list[AnalyticsStatusItem] = []

    # dim_tempo (universal — sem tenant)
    q = await db.execute(select(func.count()).select_from(DimTempo))
    items.append(AnalyticsStatusItem(table="dim_tempo", rows=int(q.scalar_one() or 0)))

    # dim_paciente (por tenant)
    q = await db.execute(
        select(func.count()).select_from(DimPaciente).where(DimPaciente.tenant_id == tenant_id)
    )
    items.append(AnalyticsStatusItem(table="dim_paciente", rows=int(q.scalar_one() or 0)))

    # dim_profissional (por tenant)
    q = await db.execute(
        select(func.count()).select_from(DimProfissional).where(DimProfissional.tenant_id == tenant_id)
    )
    items.append(AnalyticsStatusItem(table="dim_profissional", rows=int(q.scalar_one() or 0)))

    # Fatos
    for tbl_name, model in (
        ("fato_agenda", FatoAgenda),
        ("fato_orcamentos", FatoOrcamentos),
        ("fato_financeiro", FatoFinanceiro),
    ):
        q = await db.execute(
            select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        )
        items.append(AnalyticsStatusItem(table=tbl_name, rows=int(q.scalar_one() or 0)))

    return items
