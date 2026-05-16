"""Schemas — /analise/pacientes/inteligencia.

Tela única "Inteligência" sob menu Pacientes. Agrega 6 visões analíticas:
1. Acurácia preditiva (backtest da heurística de risco de no-show)
2. Top faltosos do período
3. Curva de retenção (% pacientes que voltam em 30/60/90/180/365d)
4. Pacientes em risco de evasão (ativos que sumiram > 90d)
5. Heatmap de no-show (dia da semana × hora)
6. Eficácia da confirmação (has_lembrete on/off)
"""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


# ── 1. Acurácia preditiva ─────────────────────────────────────────


class AcuraciaPaciente(BaseModel):
    paciente_external_id: int
    paciente_nome: str
    data: date
    risco_pct: int
    bucket: str  # alto | medio | baixo
    razao: str
    realmente_faltou: bool


class AcuraciaBucket(BaseModel):
    bucket: str
    total: int          # quantos foram preditos no bucket
    faltou: int         # quantos desses faltaram
    veio: int           # quantos desses vieram (CHECKOUT/LATE)
    taxa_falta_pct: int


class AcuraciaSection(BaseModel):
    appointments_avaliados: int
    baseline_pct: int               # taxa de falta global no período
    acuracia_pct: int               # acertos / total (alto+falta + medio/baixo+veio)
    precisao_alto_pct: int          # alto+falta / total predito alto
    recall_alto_pct: int            # alto+falta / total faltas
    buckets: list[AcuraciaBucket]   # 3 buckets (alto, medio, baixo)
    matriz: list[list[int]]         # 2x3 — [faltou, veio] × [alto, medio, baixo]
    acertos_alto_risco: list[AcuraciaPaciente]  # bucket alto + faltou
    escapes: list[AcuraciaPaciente]             # faltou + bucket baixo/medio


# ── 2. Top faltosos ───────────────────────────────────────────────


class TopFaltosoItem(BaseModel):
    paciente_external_id: int
    paciente_nome: str
    faltas: int
    atendimentos: int
    total: int
    taxa_falta_pct: int
    ultima_falta: date | None


# ── 3. Curva de retenção ──────────────────────────────────────────


class RetencaoBucket(BaseModel):
    janela_dias: int     # 30, 60, 90, 180, 365
    elegiveis: int       # pacientes cuja 1ª consulta foi há ≥ janela_dias dias
    retornaram: int      # desses, quantos voltaram dentro da janela
    taxa_pct: int


class RetencaoSection(BaseModel):
    buckets: list[RetencaoBucket]


# ── 4. Risco de evasão ────────────────────────────────────────────


class EvasaoPaciente(BaseModel):
    paciente_external_id: int
    paciente_nome: str
    visitas_12m: int
    ultima_visita: date
    dias_sem_voltar: int


# ── 5. Heatmap no-show ────────────────────────────────────────────


class HeatmapCelula(BaseModel):
    dow: int             # 0=segunda ... 6=domingo (MySQL WEEKDAY)
    hora: int            # 0..23
    total: int
    faltas: int
    taxa_falta_pct: int


class HeatmapSection(BaseModel):
    celulas: list[HeatmapCelula]
    total_global: int
    faltas_global: int


# ── 6. Eficácia da confirmação ────────────────────────────────────


class EficaciaConfirmacao(BaseModel):
    com_lembrete_total: int
    com_lembrete_faltas: int
    com_lembrete_taxa_pct: int
    sem_lembrete_total: int
    sem_lembrete_faltas: int
    sem_lembrete_taxa_pct: int
    diferenca_pp: int            # sem - com (positivo = lembrete reduz falta)
    cobertura_lembrete_pct: int  # % appointments com has_lembrete=1


# ── Resposta agregada ─────────────────────────────────────────────


class InteligenciaPacientesResponse(BaseModel):
    periodo_dias: int
    gerado_em: datetime
    acuracia: AcuraciaSection
    top_faltosos: list[TopFaltosoItem]
    retencao: RetencaoSection
    evasao_risco: list[EvasaoPaciente]
    heatmap: HeatmapSection
    eficacia_confirmacao: EficaciaConfirmacao
