from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMe(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    is_saas_admin: bool
    tenant_id: str
    role: str

    model_config = {"from_attributes": True}
