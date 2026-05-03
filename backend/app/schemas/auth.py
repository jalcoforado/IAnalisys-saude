from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=20, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class GenericMessage(BaseModel):
    """Resposta genérica do reset — não revela existência do email."""
    message: str


class UserMe(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_saas_admin: bool
    tenant_id: str
    role: str
    permissions: list[str] = []

    model_config = {"from_attributes": True}
