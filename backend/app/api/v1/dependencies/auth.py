from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError

from app.db.session import get_db
from app.security.jwt import decode_access_token
from app.services.auth_service import get_current_user_data, AuthError
from app.schemas.auth import UserMe

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> UserMe:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id: str = payload["sub"]
        tenant_id: str = payload["tenant_id"]
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado.",
        )

    try:
        return await get_current_user_data(db, user_id, tenant_id)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
