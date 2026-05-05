"""Service do dashboard financeiro (CA / fato_caixa).

Lê apenas da camada ANALYTICS CA (fato_caixa + dim_categoria_ca + dim_centro_custo_ca).
Tudo agregado em SQL puro — multi-tenant via tenant_id.

KPIs:
- entradas / saídas / saldo líquido (do mês selecionado, valor pago realizado)
- a receber / a pagar (open balances)
- inadimplência % (vencidos receita / total receita)
- top 5 categorias receita + despesa
- distribuição por centro de custo (entradas vs saídas)
- mix por status (pago/em aberto/vencido)
- evolução 12 meses (entradas vs saídas)
"""
from __future__ import annotations

from typing import List

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import PeriodInfo
from app.schemas.financeiro import (
    CategoriaItem,
    CentroCustoItem,
    FinanceiroEvolutionPoint,
    FinanceiroKpis,
    FinanceiroOverviewResponse,
    StatusMixItem,
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
    return (year - 1, 12) if month == 1 else (year, month - 1)


# ── KPIs principais ─────────────────────────────────────────────

async def _kpis_periodo(db: AsyncSession, tenant_id: str, ym: str) -> FinanceiroKpis:
    q = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_pago_rateado ELSE 0 END), 0) AS entradas,
                COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor_pago_rateado ELSE 0 END), 0) AS saidas,
                COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_em_aberto_rateado ELSE 0 END), 0) AS a_receber,
                COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor_em_aberto_rateado ELSE 0 END), 0) AS a_pagar,
                COALESCE(SUM(CASE WHEN tipo='RECEITA' AND is_vencido=1 THEN valor_em_aberto_rateado ELSE 0 END), 0) AS receita_vencida,
                COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_rateado ELSE 0 END), 0) AS receita_total,
                COALESCE(SUM(CASE WHEN is_vencido=1 THEN 1 ELSE 0 END), 0) AS qtd_vencidas
            FROM fato_caixa
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    r = q.one()
    entradas = float(r.entradas or 0)
    saidas = float(r.saidas or 0)
    receita_vencida = float(r.receita_vencida or 0)
    receita_total = float(r.receita_total or 0)
    inad_pct = round((receita_vencida / receita_total) * 100, 2) if receita_total > 0 else 0.0

    return FinanceiroKpis(
        entradas=entradas,
        saidas=saidas,
        saldo_liquido=round(entradas - saidas, 2),
        a_receber=float(r.a_receber or 0),
        a_pagar=float(r.a_pagar or 0),
        inadimplencia_pct=inad_pct,
        qtd_parcelas_vencidas=int(r.qtd_vencidas or 0),
    )


# ── Top categorias ──────────────────────────────────────────────

async def _top_categorias(
    db: AsyncSession, tenant_id: str, ym: str, tipo: str, limit: int = 5,
) -> List[CategoriaItem]:
    """tipo = 'RECEITA' | 'DESPESA'"""
    q = await db.execute(
        text("""
            SELECT
                fc.categoria_external_id,
                MAX(dc.nome) AS nome,
                SUM(fc.valor_pago_rateado) AS total
            FROM fato_caixa fc
            LEFT JOIN dim_categoria_ca dc
                ON dc.tenant_id = fc.tenant_id
               AND dc.external_id = fc.categoria_external_id
            WHERE fc.tenant_id = :tid
              AND fc.year_month_key = :ym
              AND fc.tipo = :tipo
              AND fc.is_pago = 1
            GROUP BY fc.categoria_external_id
            ORDER BY total DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "tipo": tipo, "lim": limit},
    )
    rows = q.all()
    grand = sum(float(r.total or 0) for r in rows) or 1.0
    return [
        CategoriaItem(
            external_id=r.categoria_external_id,
            nome=r.nome or "Sem categoria",
            total=float(r.total or 0),
            pct=round((float(r.total or 0) / grand) * 100, 2),
        )
        for r in rows
    ]


# ── Centros de custo ────────────────────────────────────────────

async def _centros_custo(db: AsyncSession, tenant_id: str, ym: str) -> List[CentroCustoItem]:
    q = await db.execute(
        text("""
            SELECT
                fc.centro_custo_external_id,
                MAX(dcc.nome) AS nome,
                COALESCE(SUM(CASE WHEN fc.tipo='RECEITA' THEN fc.valor_pago_rateado ELSE 0 END), 0) AS entradas,
                COALESCE(SUM(CASE WHEN fc.tipo='DESPESA' THEN fc.valor_pago_rateado ELSE 0 END), 0) AS saidas
            FROM fato_caixa fc
            LEFT JOIN dim_centro_custo_ca dcc
                ON dcc.tenant_id = fc.tenant_id
               AND dcc.external_id = fc.centro_custo_external_id
            WHERE fc.tenant_id = :tid
              AND fc.year_month_key = :ym
              AND fc.is_pago = 1
            GROUP BY fc.centro_custo_external_id
            ORDER BY (entradas + saidas) DESC
        """),
        {"tid": tenant_id, "ym": ym},
    )
    return [
        CentroCustoItem(
            external_id=r.centro_custo_external_id,
            nome=r.nome or "Sem centro de custo",
            entradas=float(r.entradas or 0),
            saidas=float(r.saidas or 0),
            saldo=round(float(r.entradas or 0) - float(r.saidas or 0), 2),
        )
        for r in q.all()
    ]


# ── Mix por status ──────────────────────────────────────────────

async def _status_mix(db: AsyncSession, tenant_id: str, ym: str) -> List[StatusMixItem]:
    q = await db.execute(
        text("""
            SELECT status, COUNT(*) AS qtd, COALESCE(SUM(valor_rateado), 0) AS total
            FROM (
                SELECT
                    CASE
                        WHEN is_pago = 1 THEN 'pago'
                        WHEN is_vencido = 1 THEN 'vencido'
                        ELSE 'em_aberto'
                    END AS status,
                    valor_rateado
                FROM fato_caixa
                WHERE tenant_id = :tid AND year_month_key = :ym
            ) sub
            GROUP BY status
            ORDER BY FIELD(status, 'pago', 'em_aberto', 'vencido')
        """),
        {"tid": tenant_id, "ym": ym},
    )
    labels = {"pago": "Pago", "em_aberto": "Em aberto", "vencido": "Vencido"}
    return [
        StatusMixItem(
            status=r.status,
            label_pt=labels.get(r.status, r.status),
            qtd=int(r.qtd or 0),
            total=float(r.total or 0),
        )
        for r in q.all()
    ]


# ── Evolução 12 meses ───────────────────────────────────────────

async def _evolution(db: AsyncSession, tenant_id: str, end_year: int, end_month: int) -> List[FinanceiroEvolutionPoint]:
    months: list[tuple[int, int]] = []
    y, m = end_year, end_month
    for _ in range(12):
        months.append((y, m))
        y, m = _previous_month(y, m)
    months.reverse()
    keys = [_ym_key(yy, mm) for yy, mm in months]

    stmt = text("""
        SELECT
            year_month_key,
            COALESCE(SUM(CASE WHEN tipo='RECEITA' THEN valor_pago_rateado ELSE 0 END), 0) AS entradas,
            COALESCE(SUM(CASE WHEN tipo='DESPESA' THEN valor_pago_rateado ELSE 0 END), 0) AS saidas
        FROM fato_caixa
        WHERE tenant_id = :tid AND year_month_key IN :keys
        GROUP BY year_month_key
    """).bindparams(bindparam("keys", expanding=True))
    q = await db.execute(stmt, {"tid": tenant_id, "keys": keys})
    by_key = {r.year_month_key: (float(r.entradas or 0), float(r.saidas or 0)) for r in q.all()}

    out: List[FinanceiroEvolutionPoint] = []
    for yy, mm in months:
        key = _ym_key(yy, mm)
        ent, sai = by_key.get(key, (0.0, 0.0))
        out.append(FinanceiroEvolutionPoint(
            year_month_key=key,
            label_pt=f"{_MONTH_NAMES_PT_SHORT[mm]}/{str(yy)[-2:]}",
            entradas=ent,
            saidas=sai,
            saldo=round(ent - sai, 2),
        ))
    return out


# ── Orquestrador ────────────────────────────────────────────────

async def get_financeiro_overview(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> FinanceiroOverviewResponse:
    prev_y, prev_m = _previous_month(year, month)
    ym = _ym_key(year, month)
    prev_ym = _ym_key(prev_y, prev_m)

    kpis = await _kpis_periodo(db, tenant_id, ym)
    kpis_prev = await _kpis_periodo(db, tenant_id, prev_ym)
    top_rec = await _top_categorias(db, tenant_id, ym, "RECEITA")
    top_desp = await _top_categorias(db, tenant_id, ym, "DESPESA")
    cc = await _centros_custo(db, tenant_id, ym)
    mix = await _status_mix(db, tenant_id, ym)
    evolution = await _evolution(db, tenant_id, year, month)

    return FinanceiroOverviewResponse(
        period=_period_info(year, month),
        previous=_period_info(prev_y, prev_m),
        kpis=kpis,
        kpis_previous=kpis_prev,
        top_receitas=top_rec,
        top_despesas=top_desp,
        centros_custo=cc,
        status_mix=mix,
        evolution=evolution,
    )
