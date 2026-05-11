"""
Endpoints do dashboard financeiro (Conta Azul / fato_caixa).

GET /financeiro/overview?year=Y&month=M
    KPIs de caixa do período + top categorias + centros de custo +
    mix por status + evolução 12 meses.

GET /financeiro/dre?year=Y&month=M
    DRE estruturada com 3 níveis de drill (grupo → subgrupo → categoria
    plana). Endpoint dedicado da página /financeiro/dre — mais leve que
    o overview por trazer só o bloco DRE (com categorias detalhadas).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.dashboard import PeriodInfo
from app.schemas.financeiro import DreBlock, FinanceiroOverviewResponse
from app.services.financeiro_service import (
    _dre_block,
    _period_info,
    _ym_key,
    get_financeiro_overview,
)
from pydantic import BaseModel

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


class DreResponse(BaseModel):
    """Resposta do endpoint dedicado /financeiro/dre."""
    period: PeriodInfo
    dre: DreBlock


@router.get("/dre", response_model=DreResponse)
async def financeiro_dre(
    year: int = Query(..., ge=2019, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: UserMe = Depends(requires("financeiro.read")),
    db: AsyncSession = Depends(get_db),
) -> DreResponse:
    """DRE estruturada com 3 níveis de drill (grupo → subgrupo → categoria
    plana). Cada subgrupo traz `categorias[]` ordenadas por valor decrescente
    com `pct_subgrupo` calculado. Mais leve que o overview porque traz só
    o bloco DRE."""
    tenant_id = _require_tenant(current_user)
    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")
    ym = _ym_key(year, month)
    dre = await _dre_block(db, tenant_id, ym, with_categorias=True)
    return DreResponse(period=_period_info(year, month), dre=dre)
