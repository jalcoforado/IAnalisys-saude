"""Schemas do layout customizado do "Meu IAnalisys" (My-Analisys)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LayoutItem(BaseModel):
    """Posição/tamanho de um widget no grid. Contrato react-grid-layout."""

    widget_id: str = Field(..., min_length=1, max_length=80)
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    w: int = Field(..., ge=1, le=12)
    h: int = Field(..., ge=1, le=12)


class HomeLayoutResponse(BaseModel):
    """Resposta de GET/PUT /home/layout.

    `layout=None` significa que o usuário nunca salvou — o front deve aplicar
    o layout default da role atual e abrir o onboarding do My-Analisys.
    """

    model_config = ConfigDict(from_attributes=True)

    layout: list[LayoutItem] | None = None
    version: int = 0
    updated_at: datetime | None = None


class HomeLayoutUpdate(BaseModel):
    layout: list[LayoutItem] = Field(..., max_length=60)
