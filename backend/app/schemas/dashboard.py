"""Schemas do dashboard executivo."""
from typing import List, Optional
from pydantic import BaseModel


class PeriodInfo(BaseModel):
    year: int
    month: int
    label: str            # 'YYYY-MM'
    label_pt: str         # 'Maio/2026'


class KpiValue(BaseModel):
    """KPI com valor atual, anterior e variação percentual."""
    value: float
    previous: Optional[float] = None
    delta_pct: Optional[float] = None   # null quando previous=0 ou ausente


class DashboardKpis(BaseModel):
    faturamento: KpiValue
    consultas: KpiValue
    absenteismo_pct: KpiValue
    conversao_pct: KpiValue
    ticket_medio: KpiValue
    pacientes_ativos: KpiValue        # sem delta (snapshot)


class EvolutionPoint(BaseModel):
    year_month_key: str               # 'YYYY-MM'
    label_pt: str                     # 'Mai/26'
    faturamento: float
    consultas: int


class DashboardExecutivoResponse(BaseModel):
    period: PeriodInfo
    previous: PeriodInfo
    kpis: DashboardKpis
    evolution: List[EvolutionPoint]   # 12 meses, do mais antigo ao selecionado
