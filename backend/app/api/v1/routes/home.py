"""
Endpoint do Cockpit Operacional.

GET /home/dashboard
    Retorna seções condicionais por user.role.
    Não requer permission específica — qualquer usuário autenticado vê o
    cockpit com as seções aplicáveis ao seu role.
"""
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.tenant import Tenant
from app.repositories.home_layout_repository import get_layout, upsert_layout
from app.schemas.auth import UserMe
from app.schemas.home import AgendaSection, HomeDashboardResponse, StrategicOverview
from app.schemas.home_layout import HomeLayoutResponse, HomeLayoutUpdate
from app.services.ai_service import generate_agenda_narrative
from app.services.home_service import (
    get_agenda_section,
    get_home_dashboard,
    get_strategic_overview,
)

router = APIRouter(prefix="/home", tags=["home"])


async def _resolve_now_local(db: AsyncSession, tenant_id: str) -> datetime:
    """Resolve "agora" no timezone do tenant (tenants.timezone, default
    America/Sao_Paulo). Backend roda em UTC; sem isso, depois das 21h BRT
    `date.today()` mostra o dia seguinte e a agenda some.
    """
    tz_q = await db.execute(select(Tenant.timezone).where(Tenant.id == tenant_id))
    tz_name = tz_q.scalar_one_or_none() or "America/Sao_Paulo"
    try:
        return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
    except Exception:
        return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


@router.get("/dashboard", response_model=HomeDashboardResponse)
async def home_dashboard(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HomeDashboardResponse:
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    now_local = await _resolve_now_local(db, current_user.tenant_id)
    return await get_home_dashboard(
        db,
        tenant_id=current_user.tenant_id,
        role=current_user.role,
        user_full_name=current_user.full_name,
        now_local=now_local,
    )


@router.get("/agenda", response_model=AgendaSection)
async def home_agenda(
    target_date: date | None = Query(None, alias="date", description="Data alvo YYYY-MM-DD. Default: hoje (com fallback até 7d à frente)"),
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgendaSection:
    """Endpoint dedicado pra agenda de um dia específico. Permite o seletor
    Hoje/Amanhã do AgendaPage trocar de data sem recarregar todo o dashboard.
    Limite gerencial: 2 dias à frente — bloqueia uso operacional.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    now_local = await _resolve_now_local(db, current_user.tenant_id)
    today = now_local.date()
    if target_date is not None:
        delta = (target_date - today).days
        if delta < 0 or delta > 2:
            raise HTTPException(
                status_code=400,
                detail="Data fora da janela permitida (hoje + 2 dias à frente).",
            )
    return await get_agenda_section(db, current_user.tenant_id, now_local, target_date=target_date)


@router.get("/agenda-strategic", response_model=StrategicOverview)
async def home_agenda_strategic(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StrategicOverview:
    """Visão estratégica consolidada (Hoje + Amanhã + Depois) pra HomePage do dono.

    Retorna KPIs por dia + agregados de 3 dias + top pacientes a confirmar +
    top profissionais ociosos. Endpoint pesado: roda 3× o cálculo completo
    de capacity+risk. Cache por 60s no front mitiga.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    now_local = await _resolve_now_local(db, current_user.tenant_id)
    return await get_strategic_overview(db, current_user.tenant_id, now_local)


# ── IA narrativa (Sub-PR 17b) ──────────────────────────────────


_REDIS_SINGLETON: Optional[Redis] = None


def _get_redis() -> Redis:
    """Singleton de Redis pra cache da narrativa IA. Lazy: só conecta quando
    o endpoint for chamado de fato (evita custo no startup)."""
    global _REDIS_SINGLETON
    if _REDIS_SINGLETON is None:
        _REDIS_SINGLETON = Redis.from_url(settings.REDIS_URL)
    return _REDIS_SINGLETON


class AgendaAISummaryResponse(BaseModel):
    narrative: str
    model: str


@router.post("/agenda/ai-summary", response_model=AgendaAISummaryResponse)
async def home_agenda_ai_summary(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AgendaAISummaryResponse:
    """Gera prosa narrativa da agenda dos próximos 3 dias.
    Usa o mesmo `StrategicOverview` que alimenta o card estratégico do dono.

    POST (não GET) porque chama uma API externa paga e queremos que o cliente
    invoque deliberadamente, não em prefetch automático.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    if not settings.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY não configurada. Configure no .env do backend.",
        )

    now_local = await _resolve_now_local(db, current_user.tenant_id)
    overview = await get_strategic_overview(db, current_user.tenant_id, now_local)

    # Nome da clínica pra contextualizar a IA
    clinic_q = await db.execute(select(Tenant.name).where(Tenant.id == current_user.tenant_id))
    clinic_name = clinic_q.scalar_one_or_none()

    try:
        narrative = await generate_agenda_narrative(
            overview, clinic_name=clinic_name, redis=_get_redis(),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return AgendaAISummaryResponse(narrative=narrative, model=settings.ANTHROPIC_MODEL)


# ── My-Analisys (home customizável) ───────────────────────────


@router.get("/layout", response_model=HomeLayoutResponse)
async def get_home_layout(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HomeLayoutResponse:
    """Retorna o layout customizado do usuário no "Meu IAnalisys" (My-Analisys).

    Se nunca customizou, retorna `layout=None`. O frontend deve aplicar o
    default da role atual e abrir o onboarding.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    row = await get_layout(db, current_user.tenant_id, current_user.id)
    if row is None:
        return HomeLayoutResponse(layout=None, version=0, updated_at=None)
    return HomeLayoutResponse(
        layout=row.layout_json,
        version=row.version,
        updated_at=row.updated_at,
    )


@router.put("/layout", response_model=HomeLayoutResponse)
async def update_home_layout(
    payload: HomeLayoutUpdate,
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HomeLayoutResponse:
    """Salva o layout do "Meu IAnalisys". Incrementa version a cada PUT."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    items = [item.model_dump() for item in payload.layout]
    row = await upsert_layout(db, current_user.tenant_id, current_user.id, items)
    await db.commit()
    return HomeLayoutResponse(
        layout=row.layout_json,
        version=row.version,
        updated_at=row.updated_at,
    )
