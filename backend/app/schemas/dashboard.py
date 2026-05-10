"""Schemas comuns. Originalmente do dashboard executivo (extinto), mantido
apenas como host de `PeriodInfo` que é usado por Fluxo de Caixa e poderá
ser movido para `schemas/common.py` numa futura limpeza."""
from pydantic import BaseModel


class PeriodInfo(BaseModel):
    year: int
    month: int
    label: str            # 'YYYY-MM'
    label_pt: str         # 'Maio/2026'
