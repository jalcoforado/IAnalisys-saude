from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    GenericMessage,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserMe,
)
from app.services.auth_service import login, AuthError
from app.services.password_reset_service import (
    PasswordResetError,
    confirm_reset,
    request_reset,
)
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


@router.post("/password-reset/request", response_model=GenericMessage)
async def password_reset_request(
    body: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> GenericMessage:
    """
    Solicita reset de senha. SEMPRE retorna 200 com a mesma mensagem,
    independente do email existir ou não — evita enumeração de contas.
    """
    client_ip = request.client.host if request.client else None
    await request_reset(db, body.email, requested_ip=client_ip)
    return GenericMessage(
        message="Se o email estiver cadastrado, enviaremos instruções para redefinir a senha."
    )


@router.post("/password-reset/confirm", response_model=GenericMessage)
async def password_reset_confirm(
    body: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
) -> GenericMessage:
    """Consome o token e troca a senha do usuário."""
    try:
        await confirm_reset(db, body.token, body.new_password)
    except PasswordResetError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return GenericMessage(message="Senha redefinida com sucesso. Faça login com a nova senha.")
