"""
Endpoints da IA narrativa — SonIA-Insight (DeepSeek).

GET /ai/insight?page_key=...&year=Y&month=M
    Gera insight contextual da SonIA pra página informada. Retorna 200
    com o JSON do insight, ou 404 quando a página não é suportada ou a
    IA não está disponível (frontend cai pra heurística local).

Modelo padrão: DeepSeek-Chat (V3). ~13× mais barato que Sonnet 4.6,
qualidade suficiente pra ler 5-15 KPIs e gerar 2-3 frases + bullets.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.sonia_insight import SonIAInsightDTO
from app.services.sonia_insight_service import generate_insight

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/insight", response_model=SonIAInsightDTO)
async def ai_insight(
    page_key: str = Query(..., description="Rota da página (ex: /analise/financeiro)"),
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: UserMe = Depends(requires("dashboard.read")),
    db: AsyncSession = Depends(get_db),
) -> SonIAInsightDTO:
    """
    Gera insight da SonIA pra (page_key, year, month).

    Retornos:
    - 200 + SonIAInsightDTO — IA gerou com sucesso
    - 404 — página não suportada OU IA indisponível (DeepSeek não
      configurada / erro de chamada). Frontend deve cair pra heurística
      local sem mostrar erro ao usuário.
    """
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")

    today = date.today()
    if (year, month) > (today.year, today.month):
        raise HTTPException(status_code=400, detail="Período no futuro.")

    first_name = (current_user.full_name or current_user.email or "").split(" ")[0] or None

    insight = await generate_insight(
        db,
        tenant_id=current_user.tenant_id,
        page_key=page_key,
        year=year,
        month=month,
        user_first_name=first_name,
    )

    if insight is None:
        # 404 acionado por: página não suportada, IA não configurada, ou erro
        # transitório. Mensagem genérica — frontend cai pra fallback heurístico.
        raise HTTPException(status_code=404, detail="Insight não disponível pra esta página.")

    return insight
