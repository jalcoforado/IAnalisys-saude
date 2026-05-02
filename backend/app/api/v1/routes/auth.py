from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserMe
from app.services.auth_service import login, AuthError
from app.api.v1.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def auth_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await login(db, body.email, body.password, body.tenant_id)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserMe)
async def auth_me(current_user: UserMe = Depends(get_current_user)):
    return current_user
