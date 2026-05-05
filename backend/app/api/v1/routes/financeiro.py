"""
Endpoints do dashboard financeiro (Conta Azul / fato_caixa).

GET /financeiro/overview?year=Y&month=M
    KPIs de caixa do período + top categorias + centros de custo +
    mix por status + evolução 12 meses.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.financeiro import FinanceiroOverviewResponse
from app.services.financeiro_service import get_financeiro_overview

router = APIRouter(prefix="/financeiro", tags=["financeiro"])


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


@router.get("/overview", response_model=FinanceiroOverviewResponse)
async def financeiro_overview(
    year: int = Query(..., ge=2019, le=2100, description="Ano do período."),
    month: int = Query(..., ge=1, le=12, description="Mês do período (1-12)."),
    current_user: UserMe = Depends(requires("financeiro.read")),
    db: AsyncSession = Depends(get_db),
) -> FinanceiroOverviewResponse:
    tenant_id = _require_tenant(current_user)
    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")
    return await get_financeiro_overview(db, tenant_id, year, month)
