"""
Service do dashboard executivo.

Lê apenas da camada ANALYTICS (fato_* + dim_paciente). Tudo agregado em SQL —
nada de full-scan em Python. Multi-tenant: sempre filtra por tenant_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import (
    DashboardExecutivoResponse,
    DashboardKpis,
    EvolutionPoint,
    KpiValue,
    PeriodInfo,
)

_MONTH_NAMES_PT_FULL = (
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)
_MONTH_NAMES_PT_SHORT = (
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
)


def _ym_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _period_info(year: int, month: int) -> PeriodInfo:
    return PeriodInfo(
        year=year,
        month=month,
        label=_ym_key(year, month),
        label_pt=f"{_MONTH_NAMES_PT_FULL[month]}/{year}",
    )


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _delta_pct(curr: float, prev: Optional[float]) -> Optional[float]:
    if prev is None or prev == 0:
        return None
    return round(((curr - prev) / prev) * 100, 2)


@dataclass
class _PeriodAgg:
    faturamento: float
    consultas: int
    canceladas: int
    orcamentos: int
    aprovados: int
    valor_orcado: float


async def _aggregate_period(db: AsyncSession, tenant_id: str, ym: str) -> _PeriodAgg:
    """Uma query por fato (3 round-trips), tudo agregado no DB."""
    fin_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(CASE WHEN is_received = 1 THEN amount ELSE 0 END), 0) AS faturamento
            FROM fato_financeiro
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    faturamento = float(fin_q.scalar_one() or 0)

    ag_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN is_canceled = 1 THEN 1 ELSE 0 END), 0) AS canceladas
            FROM fato_agenda
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    row = ag_q.one()
    consultas = int(row.total or 0)
    canceladas = int(row.canceladas or 0)

    orc_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END), 0) AS aprovados,
                COALESCE(SUM(amount), 0) AS valor_orcado
            FROM fato_orcamentos
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    row = orc_q.one()
    orcamentos = int(row.total or 0)
    aprovados = int(row.aprovados or 0)
    valor_orcado = float(row.valor_orcado or 0)

    return _PeriodAgg(
        faturamento=faturamento,
        consultas=consultas,
        canceladas=canceladas,
        orcamentos=orcamentos,
        aprovados=aprovados,
        valor_orcado=valor_orcado,
    )


async def _pacientes_ativos(db: AsyncSession, tenant_id: str) -> int:
    q = await db.execute(
        text("SELECT COUNT(*) FROM dim_paciente WHERE tenant_id = :tid AND is_active = 1"),
        {"tid": tenant_id},
    )
    return int(q.scalar_one() or 0)


async def _evolution(db: AsyncSession, tenant_id: str, end_year: int, end_month: int) -> List[EvolutionPoint]:
    """12 meses terminando no período selecionado (inclusive). Faturamento + consultas."""
    months: list[tuple[int, int]] = []
    y, m = end_year, end_month
    for _ in range(12):
        months.append((y, m))
        y, m = _previous_month(y, m)
    months.reverse()
    keys = [_ym_key(yy, mm) for yy, mm in months]

    fin_stmt = text("""
        SELECT year_month_key,
               COALESCE(SUM(CASE WHEN is_received = 1 THEN amount ELSE 0 END), 0) AS faturamento
        FROM fato_financeiro
        WHERE tenant_id = :tid AND year_month_key IN :keys
        GROUP BY year_month_key
    """).bindparams(bindparam("keys", expanding=True))
    fin_q = await db.execute(fin_stmt, {"tid": tenant_id, "keys": keys})
    fin_map = {r.year_month_key: float(r.faturamento or 0) for r in fin_q.all()}

    ag_stmt = text("""
        SELECT year_month_key, COUNT(*) AS consultas
        FROM fato_agenda
        WHERE tenant_id = :tid AND year_month_key IN :keys
        GROUP BY year_month_key
    """).bindparams(bindparam("keys", expanding=True))
    ag_q = await db.execute(ag_stmt, {"tid": tenant_id, "keys": keys})
    ag_map = {r.year_month_key: int(r.consultas or 0) for r in ag_q.all()}

    out: list[EvolutionPoint] = []
    for yy, mm in months:
        key = _ym_key(yy, mm)
        out.append(EvolutionPoint(
            year_month_key=key,
            label_pt=f"{_MONTH_NAMES_PT_SHORT[mm]}/{str(yy)[-2:]}",
            faturamento=fin_map.get(key, 0.0),
            consultas=ag_map.get(key, 0),
        ))
    return out


async def get_dashboard_executivo(
    db: AsyncSession, tenant_id: str, year: int, month: int
) -> DashboardExecutivoResponse:
    prev_y, prev_m = _previous_month(year, month)
    curr_ym = _ym_key(year, month)
    prev_ym = _ym_key(prev_y, prev_m)

    curr = await _aggregate_period(db, tenant_id, curr_ym)
    prev = await _aggregate_period(db, tenant_id, prev_ym)
    pacientes_ativos = await _pacientes_ativos(db, tenant_id)
    evolution = await _evolution(db, tenant_id, year, month)

    def _abs(p: _PeriodAgg) -> float:
        return round((p.canceladas / p.consultas) * 100, 2) if p.consultas else 0.0

    def _conv(p: _PeriodAgg) -> float:
        return round((p.aprovados / p.orcamentos) * 100, 2) if p.orcamentos else 0.0

    def _ticket(p: _PeriodAgg) -> float:
        return round(p.faturamento / p.consultas, 2) if p.consultas else 0.0

    curr_abs, prev_abs = _abs(curr), _abs(prev)
    curr_conv, prev_conv = _conv(curr), _conv(prev)
    curr_ticket, prev_ticket = _ticket(curr), _ticket(prev)

    kpis = DashboardKpis(
        faturamento=KpiValue(
            value=curr.faturamento,
            previous=prev.faturamento,
            delta_pct=_delta_pct(curr.faturamento, prev.faturamento),
        ),
        consultas=KpiValue(
            value=float(curr.consultas),
            previous=float(prev.consultas),
            delta_pct=_delta_pct(curr.consultas, prev.consultas),
        ),
        absenteismo_pct=KpiValue(
            value=curr_abs,
            previous=prev_abs,
            delta_pct=_delta_pct(curr_abs, prev_abs),
        ),
        conversao_pct=KpiValue(
            value=curr_conv,
            previous=prev_conv,
            delta_pct=_delta_pct(curr_conv, prev_conv),
        ),
        ticket_medio=KpiValue(
            value=curr_ticket,
            previous=prev_ticket,
            delta_pct=_delta_pct(curr_ticket, prev_ticket),
        ),
        pacientes_ativos=KpiValue(
            value=float(pacientes_ativos),
            previous=None,
            delta_pct=None,
        ),
    )

    return DashboardExecutivoResponse(
        period=_period_info(year, month),
        previous=_period_info(prev_y, prev_m),
        kpis=kpis,
        evolution=evolution,
    )
