"""Schemas de configuração do tenant (white-label)."""
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class TenantSettingsResponse(BaseModel):
    """Configurações completas do tenant. Retornado em GET /tenant/settings."""
    id: str
    slug: str

    # Identidade Visual
    name: str
    logo_url: Optional[str] = None
    favicon_url: Optional[str] = None
    login_background_url: Optional[str] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None

    # Dados da Empresa
    legal_name: Optional[str] = None
    tax_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    website: Optional[str] = None

    # Endereço
    address_zip: Optional[str] = None
    address_street: Optional[str] = None
    address_number: Optional[str] = None
    address_complement: Optional[str] = None
    address_district: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None

    class Config:
        from_attributes = True


class TenantSettingsUpdate(BaseModel):
    """Payload do PUT /tenant/settings — campos textuais (sem imagens)."""
    # Identidade Visual (cores)
    primary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

    # Dados da Empresa
    name: Optional[str] = Field(None, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    whatsapp: Optional[str] = Field(None, max_length=50)
    website: Optional[str] = Field(None, max_length=255)

    # Endereço
    address_zip: Optional[str] = Field(None, max_length=20)
    address_street: Optional[str] = Field(None, max_length=255)
    address_number: Optional[str] = Field(None, max_length=20)
    address_complement: Optional[str] = Field(None, max_length=100)
    address_district: Optional[str] = Field(None, max_length=100)
    address_city: Optional[str] = Field(None, max_length=100)
    address_state: Optional[str] = Field(None, min_length=2, max_length=2)


class UploadResponse(BaseModel):
    """Resposta do POST /tenant/uploads/{kind}."""
    kind: str
    url: str
    size_bytes: int
