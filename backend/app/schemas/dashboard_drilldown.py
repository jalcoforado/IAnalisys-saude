"""Schemas do drill-down auditável dos KPIs do dashboard executivo.

Cada KPI ganha um endpoint paralelo `/dashboard/executivo/itens?kpi=<id>` que
retorna as linhas que entraram no cálculo. Total no footer do drawer **bate
com o KPI** — auditoria built-in.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.schemas.dashboard import PeriodInfo


class DrillDownItem(BaseModel):
    """Linha individual que entrou no cálculo do KPI.

    Schema flexível: cada KPI usa o subset de campos que faz sentido. Front
    sabe quais campos exibir por `kpi_id`.
    """
    external_id: str                          # chave no ERP (deep-link)
    label: str                                # display principal (paciente, etc.)
    secondary_label: Optional[str] = None     # display secundário (profissional, categoria)
    date_iso: Optional[str] = None            # 'YYYY-MM-DD' quando aplicável
    value: Optional[float] = None             # contribuição numérica (BRL ou 1)
    extras: Dict[str, str] = {}               # tags adicionais ex {"status": "aprovado"}


class DrillDownResponse(BaseModel):
    kpi_id: str                               # 'faturamento'|'consultas'|...
    kpi_label: str                            # 'Faturamento', 'Consultas'...
    period: PeriodInfo
    kpi_value: float                          # valor exato do KPI no dashboard
    kpi_unit: str                             # 'BRL'|'count'|'pct'
    # Auditoria (cumulativos): total_value === kpi_value. None pra pcts/médias.
    total_value: Optional[float] = None
    total_count: int                          # qtd de linhas que entraram
    audit_ok: Optional[bool] = None           # None pra ratios; True/False senão
    items_returned: int                       # min(total_count, limit)
    items: List[DrillDownItem]
