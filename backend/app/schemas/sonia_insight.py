"""
Schemas da SonIA-Insight — endpoint /ai/insight.

Formato exato consumido pelo `SonIAFab.tsx` no frontend: o JSON aqui
serializado vira direto o objeto `SonIAInsight` lá no React. Por isso
qualquer mudança aqui exige ajuste paralelo no frontend.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel


SonIAMood = Literal["default", "thinking", "alert", "happy", "curious"]
SonIABulletTone = Literal["neutral", "positive", "negative", "warning"]


class SonIABulletDTO(BaseModel):
    text: str
    tone: SonIABulletTone = "neutral"


class SonIAInsightDTO(BaseModel):
    mood: SonIAMood
    headline: str
    detail: str
    bullets: List[SonIABulletDTO] = []
    cta_href: Optional[str] = None
    cta_label: Optional[str] = None
    source: str = "Heurístico"  # "Heurístico" | "DeepSeek" | "Claude" etc.
