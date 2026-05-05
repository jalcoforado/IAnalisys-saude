"""Schemas do dashboard financeiro (Conta Azul / fato_caixa)."""
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.dashboard import PeriodInfo


class FinanceiroKpis(BaseModel):
    entradas: float                   # SUM(valor_pago_rateado WHERE tipo=RECEITA)
    saidas: float                     # SUM(valor_pago_rateado WHERE tipo=DESPESA)
    saldo_liquido: float              # entradas - saidas
    a_receber: float                  # SUM(valor_em_aberto_rateado WHERE tipo=RECEITA)
    a_pagar: float                    # SUM(valor_em_aberto_rateado WHERE tipo=DESPESA)
    inadimplencia_pct: float          # vencidos receita / total receita * 100
    qtd_parcelas_vencidas: int


class CategoriaItem(BaseModel):
    external_id: Optional[str]
    nome: str
    total: float
    pct: float                        # % do tipo (entrada ou saída)


class CentroCustoItem(BaseModel):
    external_id: Optional[str]
    nome: str
    entradas: float
    saidas: float
    saldo: float


class StatusMixItem(BaseModel):
    status: str                       # 'pago'|'em_aberto'|'vencido'
    label_pt: str                     # 'Pago'|'Em aberto'|'Vencido'
    qtd: int
    total: float


class FinanceiroEvolutionPoint(BaseModel):
    year_month_key: str               # 'YYYY-MM'
    label_pt: str                     # 'Out/25'
    entradas: float
    saidas: float
    saldo: float                      # entradas - saidas (mês isolado, não cumulativo)


class FinanceiroOverviewResponse(BaseModel):
    period: PeriodInfo
    previous: PeriodInfo
    kpis: FinanceiroKpis
    kpis_previous: FinanceiroKpis     # mesmo objeto pro mês anterior, pra MoM
    top_receitas: List[CategoriaItem]
    top_despesas: List[CategoriaItem]
    centros_custo: List[CentroCustoItem]
    status_mix: List[StatusMixItem]
    evolution: List[FinanceiroEvolutionPoint]
