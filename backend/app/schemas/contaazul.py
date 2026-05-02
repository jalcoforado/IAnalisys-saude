from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ContaAzulStatusResponse(BaseModel):
    connected: bool
    status: str           # "ativo" | "expirado" | "desconectado"
    expires_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ContaAzulAuthUrlResponse(BaseModel):
    auth_url: str
