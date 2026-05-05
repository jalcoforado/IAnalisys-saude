"""
Endpoint do Cockpit Operacional.

GET /home/dashboard
    Retorna seções condicionais por user.role.
    Não requer permission específica — qualquer usuário autenticado vê o
    cockpit com as seções aplicáveis ao seu role.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.db.session import get_db
from app.schemas.auth import UserMe
from app.schemas.home import HomeDashboardResponse
from app.services.home_service import get_home_dashboard

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/dashboard", response_model=HomeDashboardResponse)
async def home_dashboard(
    current_user: UserMe = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HomeDashboardResponse:
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return await get_home_dashboard(
        db,
        tenant_id=current_user.tenant_id,
        role=current_user.role,
        user_full_name=current_user.full_name,
    )
