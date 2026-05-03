"""Schemas dos endpoints administrativos de usuários do tenant."""
from pydantic import BaseModel, EmailStr, Field


class UserListItem(BaseModel):
    id: str
    email: str
    full_name: str
    is_active: bool
    role_id: str
    role_name: str


class UserInviteRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=120)
    role_id: str


class UserUpdateRequest(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=120)
    role_id: str | None = None
    is_active: bool | None = None


class UserActionResponse(BaseModel):
    id: str
    message: str
