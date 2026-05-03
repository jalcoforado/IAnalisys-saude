"""
Endpoints do dashboard executivo.

GET /dashboard/executivo?year=YYYY&month=M
    Retorna 6 KPIs (com delta vs mês anterior) + série de 12 meses.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.dashboard import DashboardExecutivoResponse
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
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardExecutivoResponse:
    tenant_id = _require_tenant(current_user)
    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")
    return await get_dashboard_executivo(db, tenant_id, year, month)
