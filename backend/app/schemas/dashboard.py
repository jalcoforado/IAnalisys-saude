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


# ── Funil comercial ──────────────────────────────────────────────

class FunilComercial(BaseModel):
    total_orcamentos: int
    aprovados: int
    abertos: int
    em_followup: int
    recusados: int
    valor_total: float
    valor_aprovado: float
    valor_pipeline: float           # abertos + followup
    valor_perdido: float
    taxa_conversao_pct: float


# ── Receita & pagamento ──────────────────────────────────────────

class Inadimplencia(BaseModel):
    recebido: float
    a_receber: float
    total_emitido: float
    inadimplencia_pct: float


class MixPagamentoItem(BaseModel):
    forma: str
    total: float
    qtd: int
    pct: float


# ── Performance ──────────────────────────────────────────────────

class TopProfissionalItem(BaseModel):
    external_id: int
    name: Optional[str]
    orcamentos: int
    aprovados: int
    valor_aprovado: float
    taxa_conversao_pct: float


class TopCategoriaItem(BaseModel):
    categoria: str
    consultas: int
    canceladas: int
    absenteismo_pct: float


class ComparacaoYoY(BaseModel):
    period_yoy: PeriodInfo
    faturamento_atual: float
    faturamento_yoy: float
    faturamento_yoy_pct: Optional[float]
    consultas_atual: int
    consultas_yoy: int
    consultas_yoy_pct: Optional[float]


# ── Pacientes ────────────────────────────────────────────────────

class CurvaAbcItem(BaseModel):
    classe: str                      # 'A', 'B', 'C'
    qtd_pacientes: int
    faturamento: float
    pct_pacientes: float
    pct_faturamento: float


class ChurnBucket(BaseModel):
    bucket: str                      # 'ativo'|'em_risco'|'inativo'|'perdido'|'sem_visita'
    label_pt: str
    qtd: int
    pct: float


class TopLtvPaciente(BaseModel):
    external_id: int
    name: Optional[str]
    ltv: float
    total_payments: int


class NovosRecorrentes(BaseModel):
    novos: int
    recorrentes: int
    total: int


class PacientesAnalise(BaseModel):
    total_base: int                  # total de pacientes na dim_paciente
    curva_abc: List[CurvaAbcItem]
    churn_buckets: List[ChurnBucket]
    top_ltv: List[TopLtvPaciente]
    novos_recorrentes: NovosRecorrentes


# ── Response final ───────────────────────────────────────────────

class DashboardExecutivoResponse(BaseModel):
    period: PeriodInfo
    previous: PeriodInfo
    kpis: DashboardKpis
    funil: FunilComercial
    inadimplencia: Inadimplencia
    mix_pagamento: List[MixPagamentoItem]
    top_profissionais: List[TopProfissionalItem]
    top_categorias_agenda: List[TopCategoriaItem]
    comparacao_yoy: ComparacaoYoY
    pacientes: PacientesAnalise
    evolution: List[EvolutionPoint]   # 12 meses, do mais antigo ao selecionado
