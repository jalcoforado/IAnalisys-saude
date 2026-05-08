"""
Endpoints dos dashboards segmentados (Sub-PR 20).

GET /analise/financeiro?year=Y&month=M
    Dashboard financeiro: faturamento (orçamentos aprovados), conversão,
    ticket médio, recebido. Cada KPI traz MoM/YoY/sparkline 12m/insight
    determinístico. Inclui funil, mix de pagamento, tops e insights
    estratégicos hardcoded.

POST /analise/financeiro/ai-insights
    Gera 4-6 insights estratégicos via Claude cruzando dimensões.
    POST (não GET) porque é chamada paga/externa — cliente invoca por
    clique deliberado, não automaticamente.

Próximos:
    GET /analise/comercial    — consultas, absenteísmo, top profs/categorias
    GET /analise/pacientes    — curva ABC, LTV, churn, novos×recorrentes
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.core.config import settings
from app.db.session import get_db
from app.models.tenant import Tenant
from app.schemas.analise import (
    AnaliseComercialResponse,
    AnaliseFinanceiroResponse,
    PrazoAuditResponse,
)
from app.schemas.auth import UserMe
from app.services.ai_service import (
    generate_comercial_insights,
    generate_financeiro_insights,
)
from app.services.analise_comercial_service import get_analise_comercial
from app.services.analise_financeiro_service import (
    get_analise_financeiro,
    get_prazos_audit,
)

router = APIRouter(prefix="/analise", tags=["analise"])


# Singleton Redis lazy-init (mesmo padrão de routes/home.py)
_REDIS_SINGLETON: Optional[Redis] = None


def _get_redis() -> Redis:
    global _REDIS_SINGLETON
    if _REDIS_SINGLETON is None:
        _REDIS_SINGLETON = Redis.from_url(settings.REDIS_URL)
    return _REDIS_SINGLETON


@router.get("/financeiro", response_model=AnaliseFinanceiroResponse)
async def analise_financeiro(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> AnaliseFinanceiroResponse:
    """Dashboard financeiro consolidado. Faturamento = orçamentos aprovados
    no mês. Recebido = pagamentos confirmados no mês. Os dois conceitos
    aparecem lado a lado pra mostrar o gap (parcelas em curso).
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")

    # Bloqueia futuro — sem dados ainda
    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(
            status_code=400,
            detail="Período no futuro — selecione mês atual ou anterior.",
        )

    return await get_analise_financeiro(db, current_user.tenant_id, year, month)


# ── Auditoria do prazo (lista de parcelas) ──────────────────────


@router.get("/financeiro/prazos-detalhe", response_model=PrazoAuditResponse)
async def analise_financeiro_prazos_detalhe(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    bucket_min: Optional[int] = Query(None, ge=1, le=999),
    bucket_max: Optional[int] = Query(None, ge=1, le=999),
    limit: int = Query(1000, ge=1, le=5000),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> PrazoAuditResponse:
    """Lista de parcelas dos orçamentos APROVADOS no mês para auditoria.

    Filtro opcional por faixa de installments_count (bucket_min/bucket_max).
    Cada linha da resposta = uma parcela em core_payments.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")

    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")

    return await get_prazos_audit(
        db, current_user.tenant_id, year, month,
        bucket_min=bucket_min, bucket_max=bucket_max, limit=limit,
    )


# ── Insights via IA (chamada explícita por clique do usuário) ───


class FinanceiroAIInsightsResponse(BaseModel):
    narrative: str
    model: str


@router.post("/financeiro/ai-insights", response_model=FinanceiroAIInsightsResponse)
async def analise_financeiro_ai_insights(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> FinanceiroAIInsightsResponse:
    """Gera 4-6 insights estratégicos via Claude cruzando dimensões.

    POST (não GET) porque chama API externa paga — invocação deliberada
    pelo usuário (clique no botão "Gerar insights via IA"), nunca em
    prefetch/refresh automático.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY não configurada. Configure no .env do backend.",
        )

    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")

    data = await get_analise_financeiro(db, current_user.tenant_id, year, month)

    clinic_q = await db.execute(
        select(Tenant.name).where(Tenant.id == current_user.tenant_id)
    )
    clinic_name = clinic_q.scalar_one_or_none()

    try:
        narrative = await generate_financeiro_insights(
            data, clinic_name=clinic_name, redis=_get_redis(),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return FinanceiroAIInsightsResponse(
        narrative=narrative, model=settings.ANTHROPIC_MODEL,
    )


# ── Comercial ───────────────────────────────────────────────────


@router.get("/comercial", response_model=AnaliseComercialResponse)
async def analise_comercial(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> AnaliseComercialResponse:
    """Dashboard comercial. Foco em VOLUME e EFICIÊNCIA OPERACIONAL —
    consultas, absenteísmo, conversão consulta→orçamento, top procedimentos
    e especialidades, mix de categorias e operacional (encaixe, perdas).
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")

    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(
            status_code=400,
            detail="Período no futuro — selecione mês atual ou anterior.",
        )

    return await get_analise_comercial(db, current_user.tenant_id, year, month)


class ComercialAIInsightsResponse(BaseModel):
    narrative: str
    model: str


@router.post("/comercial/ai-insights", response_model=ComercialAIInsightsResponse)
async def analise_comercial_ai_insights(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> ComercialAIInsightsResponse:
    """Insights estratégicos via Claude pro dashboard comercial. Sob demanda."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY não configurada.",
        )

    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")

    data = await get_analise_comercial(db, current_user.tenant_id, year, month)

    clinic_q = await db.execute(
        select(Tenant.name).where(Tenant.id == current_user.tenant_id)
    )
    clinic_name = clinic_q.scalar_one_or_none()

    try:
        narrative = await generate_comercial_insights(
            data, clinic_name=clinic_name, redis=_get_redis(),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return ComercialAIInsightsResponse(
        narrative=narrative, model=settings.ANTHROPIC_MODEL,
    )
