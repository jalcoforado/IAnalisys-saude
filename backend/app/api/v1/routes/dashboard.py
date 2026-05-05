"""
Endpoints do dashboard executivo.

GET /dashboard/executivo?year=YYYY&month=M
    Retorna 6 KPIs (com delta vs mês anterior) + série de 12 meses.

GET /dashboard/executivo/itens?kpi=<id>&year=Y&month=M
    Drill-down auditável: linhas que entraram no cálculo de cada KPI.
    Total no footer === valor do KPI (auditoria built-in).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.dashboard import DashboardExecutivoResponse
from app.schemas.dashboard_drilldown import DrillDownResponse
from app.services.dashboard_drilldown_service import KPI_IDS, get_drilldown
from app.services.dashboard_service import get_dashboard_executivo

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


@router.get("/executivo", response_model=DashboardExecutivoResponse)
async def dashboard_executivo(
    year: int = Query(..., ge=2019, le=2100, description="Ano do período."),
    month: int = Query(..., ge=1, le=12, description="Mês do período (1-12)."),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> DashboardExecutivoResponse:
    tenant_id = _require_tenant(current_user)
    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")
    return await get_dashboard_executivo(db, tenant_id, year, month)


@router.get("/executivo/itens", response_model=DrillDownResponse)
async def dashboard_executivo_itens(
    kpi: str = Query(..., description=f"KPI alvo. Disponíveis: {', '.join(KPI_IDS)}"),
    year: int = Query(..., ge=2019, le=2100),
    month: int = Query(..., ge=1, le=12),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> DrillDownResponse:
    """Linhas que entraram no cálculo do KPI selecionado.
    Reusa as mesmas WHERE clauses do dashboard service — total bate com KPI.
    """
    tenant_id = _require_tenant(current_user)
    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")
    return await get_drilldown(db, tenant_id, kpi, year, month, limit=limit, offset=offset)
