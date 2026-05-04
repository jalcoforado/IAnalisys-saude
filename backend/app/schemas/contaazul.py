from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class ContaAzulStatusResponse(BaseModel):
    connected: bool
    status: str           # "ativo" | "expirado" | "desconectado"
    expires_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    # Empresa CA conectada (de /v1/pessoas/conta-conectada). Nullable pra
    # tokens antigos sem essa info; UI mostra "—" quando vazio.
    empresa_documento: Optional[str] = None
    empresa_razao_social: Optional[str] = None
    empresa_nome_fantasia: Optional[str] = None
    empresa_data_fundacao: Optional[date] = None
    empresa_email: Optional[str] = None

    model_config = {"from_attributes": True}


class ContaAzulAuthUrlResponse(BaseModel):
    auth_url: str
