"""
Service do dashboard executivo.

Lê apenas da camada ANALYTICS (fato_* + dim_paciente + dim_profissional).
Tudo agregado em SQL — nada de full-scan em Python. Multi-tenant: sempre
filtra por tenant_id.

Seções:
- KPIs principais (faturamento, consultas, absenteísmo, conversão, ticket, pacientes ativos)
- Funil comercial (orçamentos: aprovados/abertos/followup/recusados + valores)
- Inadimplência (recebido vs a receber)
- Mix de formas de pagamento
- Top 5 profissionais por valor aprovado
- Top 5 categorias de consulta
- Comparação YoY (mesmo mês ano anterior)
- Pacientes: curva ABC, churn buckets, top LTV, novos vs recorrentes
- Evolução 12 meses (faturamento + consultas)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import (
    ChurnBucket,
    ComparacaoYoY,
    CurvaAbcItem,
    DashboardExecutivoResponse,
    DashboardKpis,
    EvolutionPoint,
    FunilComercial,
    Inadimplencia,
    KpiValue,
    MixPagamentoItem,
    NovosRecorrentes,
    PacientesAnalise,
    PeriodInfo,
    TopCategoriaItem,
    TopLtvPaciente,
    TopProfissionalItem,
)

_MONTH_NAMES_PT_FULL = (
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)
_MONTH_NAMES_PT_SHORT = (
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez",
)

_CHURN_LABELS_PT = {
    "ativo": "Ativo (< 90d)",
    "em_risco": "Em risco (90-180d)",
    "inativo": "Inativo (180-365d)",
    "perdido": "Perdido (> 365d)",
    "sem_visita": "Sem visita registrada",
}


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


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    """Retorna (start_inclusive, end_exclusive) para WHERE em colunas DATE."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


# ── KPIs principais ─────────────────────────────────────────────

@dataclass
class _PeriodAgg:
    faturamento: float
    consultas: int
    canceladas: int
    orcamentos: int
    aprovados: int
    abertos: int
    followup: int
    recusados: int
    valor_total_orcado: float
    valor_aprovado: float
    valor_pipeline: float
    valor_perdido: float


async def _aggregate_period(db: AsyncSession, tenant_id: str, ym: str) -> _PeriodAgg:
    """Agrega tudo do mês em 3 queries (uma por fato)."""
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
                COALESCE(SUM(CASE WHEN is_open = 1 THEN 1 ELSE 0 END), 0) AS abertos,
                COALESCE(SUM(CASE WHEN is_followup = 1 THEN 1 ELSE 0 END), 0) AS followup,
                COALESCE(SUM(CASE WHEN is_rejected = 1 THEN 1 ELSE 0 END), 0) AS recusados,
                COALESCE(SUM(amount), 0) AS valor_total,
                COALESCE(SUM(CASE WHEN is_approved = 1 THEN amount ELSE 0 END), 0) AS valor_aprovado,
                COALESCE(SUM(CASE WHEN is_open = 1 OR is_followup = 1 THEN amount ELSE 0 END), 0) AS valor_pipeline,
                COALESCE(SUM(CASE WHEN is_rejected = 1 THEN amount ELSE 0 END), 0) AS valor_perdido
            FROM fato_orcamentos
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    row = orc_q.one()

    return _PeriodAgg(
        faturamento=faturamento,
        consultas=consultas,
        canceladas=canceladas,
        orcamentos=int(row.total or 0),
        aprovados=int(row.aprovados or 0),
        abertos=int(row.abertos or 0),
        followup=int(row.followup or 0),
        recusados=int(row.recusados or 0),
        valor_total_orcado=float(row.valor_total or 0),
        valor_aprovado=float(row.valor_aprovado or 0),
        valor_pipeline=float(row.valor_pipeline or 0),
        valor_perdido=float(row.valor_perdido or 0),
    )


async def _pacientes_ativos(db: AsyncSession, tenant_id: str) -> int:
    q = await db.execute(
        text("SELECT COUNT(*) FROM dim_paciente WHERE tenant_id = :tid AND is_active = 1"),
        {"tid": tenant_id},
    )
    return int(q.scalar_one() or 0)


# ── Inadimplência ───────────────────────────────────────────────

async def _inadimplencia(db: AsyncSession, tenant_id: str, ym: str) -> Inadimplencia:
    q = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN is_received = 1 THEN amount ELSE 0 END), 0) AS recebido,
                COALESCE(SUM(CASE WHEN is_received = 0 AND is_canceled = 0 THEN amount ELSE 0 END), 0) AS a_receber
            FROM fato_financeiro
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    row = q.one()
    recebido = float(row.recebido or 0)
    a_receber = float(row.a_receber or 0)
    total = recebido + a_receber
    pct = round((a_receber / total) * 100, 2) if total > 0 else 0.0
    return Inadimplencia(
        recebido=recebido,
        a_receber=a_receber,
        total_emitido=total,
        inadimplencia_pct=pct,
    )


# ── Mix de formas de pagamento ──────────────────────────────────

async def _mix_pagamento(db: AsyncSession, tenant_id: str, ym: str) -> List[MixPagamentoItem]:
    q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(payment_form, ''), 'Não informado') AS forma,
                SUM(amount) AS total,
                COUNT(*) AS qtd
            FROM fato_financeiro
            WHERE tenant_id = :tid AND year_month_key = :ym AND is_received = 1
            GROUP BY forma
            ORDER BY total DESC
        """),
        {"tid": tenant_id, "ym": ym},
    )
    rows = q.all()
    grand = sum(float(r.total or 0) for r in rows) or 1.0
    return [
        MixPagamentoItem(
            forma=r.forma,
            total=float(r.total or 0),
            qtd=int(r.qtd or 0),
            pct=round((float(r.total or 0) / grand) * 100, 2),
        )
        for r in rows
    ]


# ── Top profissionais ───────────────────────────────────────────

async def _top_profissionais(db: AsyncSession, tenant_id: str, ym: str) -> List[TopProfissionalItem]:
    """Top 5 por valor aprovado em fato_orcamentos no mês."""
    q = await db.execute(
        text("""
            SELECT
                fo.professional_external_id AS pid,
                MAX(dp.name) AS name,
                COUNT(*) AS orcamentos,
                COALESCE(SUM(CASE WHEN fo.is_approved = 1 THEN 1 ELSE 0 END), 0) AS aprovados,
                COALESCE(SUM(CASE WHEN fo.is_approved = 1 THEN fo.amount ELSE 0 END), 0) AS valor_aprovado
            FROM fato_orcamentos fo
            LEFT JOIN dim_profissional dp
                ON dp.tenant_id = fo.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = fo.professional_external_id
            WHERE fo.tenant_id = :tid
              AND fo.year_month_key = :ym
              AND fo.professional_external_id IS NOT NULL
            GROUP BY fo.professional_external_id
            ORDER BY valor_aprovado DESC
            LIMIT 5
        """),
        {"tid": tenant_id, "ym": ym},
    )
    items: list[TopProfissionalItem] = []
    for r in q.all():
        orcs = int(r.orcamentos or 0)
        aprov = int(r.aprovados or 0)
        items.append(TopProfissionalItem(
            external_id=int(r.pid),
            name=r.name,
            orcamentos=orcs,
            aprovados=aprov,
            valor_aprovado=float(r.valor_aprovado or 0),
            taxa_conversao_pct=round((aprov / orcs) * 100, 2) if orcs else 0.0,
        ))
    return items


# ── Top categorias de consulta ──────────────────────────────────

async def _top_categorias(db: AsyncSession, tenant_id: str, ym: str) -> List[TopCategoriaItem]:
    q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(category_description, ''), 'Não informado') AS categoria,
                COUNT(*) AS consultas,
                COALESCE(SUM(CASE WHEN is_canceled = 1 THEN 1 ELSE 0 END), 0) AS canceladas
            FROM fato_agenda
            WHERE tenant_id = :tid AND year_month_key = :ym
            GROUP BY categoria
            ORDER BY consultas DESC
            LIMIT 5
        """),
        {"tid": tenant_id, "ym": ym},
    )
    items: list[TopCategoriaItem] = []
    for r in q.all():
        cons = int(r.consultas or 0)
        canc = int(r.canceladas or 0)
        items.append(TopCategoriaItem(
            categoria=r.categoria,
            consultas=cons,
            canceladas=canc,
            absenteismo_pct=round((canc / cons) * 100, 2) if cons else 0.0,
        ))
    return items


# ── Comparação YoY ──────────────────────────────────────────────

async def _comparacao_yoy(db: AsyncSession, tenant_id: str, year: int, month: int,
                           curr_fat: float, curr_cons: int) -> ComparacaoYoY:
    yoy_year = year - 1
    yoy_ym = _ym_key(yoy_year, month)
    fin_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(CASE WHEN is_received = 1 THEN amount ELSE 0 END), 0) AS faturamento
            FROM fato_financeiro
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": yoy_ym},
    )
    fat_yoy = float(fin_q.scalar_one() or 0)

    ag_q = await db.execute(
        text("SELECT COUNT(*) FROM fato_agenda WHERE tenant_id = :tid AND year_month_key = :ym"),
        {"tid": tenant_id, "ym": yoy_ym},
    )
    cons_yoy = int(ag_q.scalar_one() or 0)

    return ComparacaoYoY(
        period_yoy=_period_info(yoy_year, month),
        faturamento_atual=curr_fat,
        faturamento_yoy=fat_yoy,
        faturamento_yoy_pct=_delta_pct(curr_fat, fat_yoy),
        consultas_atual=curr_cons,
        consultas_yoy=cons_yoy,
        consultas_yoy_pct=_delta_pct(curr_cons, cons_yoy),
    )


# ── Pacientes ───────────────────────────────────────────────────

async def _curva_abc(db: AsyncSession, tenant_id: str) -> List[CurvaAbcItem]:
    """
    Pareto baseado em LTV (SUM(fato_financeiro.amount WHERE is_received=1)).
    A = pacientes que somam até 80% da receita acumulada
    B = de 80% até 95%
    C = de 95% até 100%
    """
    q = await db.execute(
        text("""
            WITH ltv AS (
                SELECT patient_external_id, SUM(amount) AS total
                FROM fato_financeiro
                WHERE tenant_id = :tid
                  AND is_received = 1
                  AND patient_external_id IS NOT NULL
                GROUP BY patient_external_id
                HAVING total > 0
            ),
            ranked AS (
                SELECT
                    patient_external_id,
                    total,
                    SUM(total) OVER (ORDER BY total DESC, patient_external_id
                                      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative,
                    SUM(total) OVER () AS grand
                FROM ltv
            ),
            classified AS (
                SELECT
                    total,
                    CASE
                        WHEN cumulative / grand <= 0.80 THEN 'A'
                        WHEN cumulative / grand <= 0.95 THEN 'B'
                        ELSE 'C'
                    END AS classe
                FROM ranked
            )
            SELECT
                classe,
                COUNT(*) AS qtd,
                SUM(total) AS faturamento,
                (SELECT COUNT(*) FROM ltv) AS total_pacientes,
                (SELECT SUM(total) FROM ltv) AS grand_total
            FROM classified
            GROUP BY classe
            ORDER BY classe
        """),
        {"tid": tenant_id},
    )
    rows = q.all()
    if not rows:
        return []
    total_pacientes = int(rows[0].total_pacientes or 0)
    grand_total = float(rows[0].grand_total or 0) or 1.0
    return [
        CurvaAbcItem(
            classe=r.classe,
            qtd_pacientes=int(r.qtd or 0),
            faturamento=float(r.faturamento or 0),
            pct_pacientes=round((int(r.qtd or 0) / total_pacientes) * 100, 2) if total_pacientes else 0.0,
            pct_faturamento=round((float(r.faturamento or 0) / grand_total) * 100, 2),
        )
        for r in rows
    ]


async def _churn_buckets(db: AsyncSession, tenant_id: str) -> tuple[List[ChurnBucket], int]:
    q = await db.execute(
        text("""
            SELECT
                CASE
                    WHEN days_since_last_seen IS NULL THEN 'sem_visita'
                    WHEN days_since_last_seen < 90  THEN 'ativo'
                    WHEN days_since_last_seen < 180 THEN 'em_risco'
                    WHEN days_since_last_seen < 365 THEN 'inativo'
                    ELSE 'perdido'
                END AS bucket,
                COUNT(*) AS qtd
            FROM dim_paciente
            WHERE tenant_id = :tid
            GROUP BY bucket
        """),
        {"tid": tenant_id},
    )
    raw = {r.bucket: int(r.qtd or 0) for r in q.all()}
    total = sum(raw.values()) or 1
    order = ["ativo", "em_risco", "inativo", "perdido", "sem_visita"]
    items = [
        ChurnBucket(
            bucket=b,
            label_pt=_CHURN_LABELS_PT[b],
            qtd=raw.get(b, 0),
            pct=round((raw.get(b, 0) / total) * 100, 2),
        )
        for b in order
    ]
    return items, sum(raw.values())


async def _top_ltv(db: AsyncSession, tenant_id: str) -> List[TopLtvPaciente]:
    q = await db.execute(
        text("""
            SELECT
                f.patient_external_id AS pid,
                MAX(dp.name) AS name,
                SUM(f.amount) AS ltv,
                COUNT(*) AS total_payments
            FROM fato_financeiro f
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = f.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = f.patient_external_id
            WHERE f.tenant_id = :tid
              AND f.is_received = 1
              AND f.patient_external_id IS NOT NULL
            GROUP BY f.patient_external_id
            ORDER BY ltv DESC
            LIMIT 10
        """),
        {"tid": tenant_id},
    )
    return [
        TopLtvPaciente(
            external_id=int(r.pid),
            name=r.name,
            ltv=float(r.ltv or 0),
            total_payments=int(r.total_payments or 0),
        )
        for r in q.all()
    ]


async def _novos_recorrentes(db: AsyncSession, tenant_id: str, year: int, month: int) -> NovosRecorrentes:
    start, end = _month_bounds(year, month)
    q = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT CASE
                    WHEN dp.first_seen_at >= :start AND dp.first_seen_at < :end
                    THEN fa.patient_external_id END) AS novos,
                COUNT(DISTINCT CASE
                    WHEN dp.first_seen_at < :start
                    THEN fa.patient_external_id END) AS recorrentes,
                COUNT(DISTINCT fa.patient_external_id) AS total
            FROM fato_agenda fa
            JOIN dim_paciente dp
                ON dp.tenant_id = fa.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            WHERE fa.tenant_id = :tid
              AND fa.year_month_key = :ym
              AND fa.is_canceled = 0
              AND fa.patient_external_id IS NOT NULL
        """),
        {"tid": tenant_id, "ym": _ym_key(year, month), "start": start, "end": end},
    )
    row = q.one()
    return NovosRecorrentes(
        novos=int(row.novos or 0),
        recorrentes=int(row.recorrentes or 0),
        total=int(row.total or 0),
    )


async def _pacientes_total_base(db: AsyncSession, tenant_id: str) -> int:
    q = await db.execute(
        text("SELECT COUNT(*) FROM dim_paciente WHERE tenant_id = :tid"),
        {"tid": tenant_id},
    )
    return int(q.scalar_one() or 0)


# ── Evolução 12 meses ────────────────────────────────────────────

async def _evolution(db: AsyncSession, tenant_id: str, end_year: int, end_month: int) -> List[EvolutionPoint]:
    """12 meses terminando no período selecionado (inclusive)."""
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


# ── Orquestrador ────────────────────────────────────────────────

async def get_dashboard_executivo(
    db: AsyncSession, tenant_id: str, year: int, month: int
) -> DashboardExecutivoResponse:
    prev_y, prev_m = _previous_month(year, month)
    curr_ym = _ym_key(year, month)
    prev_ym = _ym_key(prev_y, prev_m)

    curr = await _aggregate_period(db, tenant_id, curr_ym)
    prev = await _aggregate_period(db, tenant_id, prev_ym)
    pacientes_ativos = await _pacientes_ativos(db, tenant_id)
    inadimp = await _inadimplencia(db, tenant_id, curr_ym)
    mix = await _mix_pagamento(db, tenant_id, curr_ym)
    top_prof = await _top_profissionais(db, tenant_id, curr_ym)
    top_cat = await _top_categorias(db, tenant_id, curr_ym)
    yoy = await _comparacao_yoy(db, tenant_id, year, month, curr.faturamento, curr.consultas)
    abc = await _curva_abc(db, tenant_id)
    churn, _churn_total = await _churn_buckets(db, tenant_id)
    top_ltv = await _top_ltv(db, tenant_id)
    nov_rec = await _novos_recorrentes(db, tenant_id, year, month)
    total_base = await _pacientes_total_base(db, tenant_id)
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

    funil = FunilComercial(
        total_orcamentos=curr.orcamentos,
        aprovados=curr.aprovados,
        abertos=curr.abertos,
        em_followup=curr.followup,
        recusados=curr.recusados,
        valor_total=curr.valor_total_orcado,
        valor_aprovado=curr.valor_aprovado,
        valor_pipeline=curr.valor_pipeline,
        valor_perdido=curr.valor_perdido,
        taxa_conversao_pct=curr_conv,
    )

    pacientes = PacientesAnalise(
        total_base=total_base,
        curva_abc=abc,
        churn_buckets=churn,
        top_ltv=top_ltv,
        novos_recorrentes=nov_rec,
    )

    return DashboardExecutivoResponse(
        period=_period_info(year, month),
        previous=_period_info(prev_y, prev_m),
        kpis=kpis,
        funil=funil,
        inadimplencia=inadimp,
        mix_pagamento=mix,
        top_profissionais=top_prof,
        top_categorias_agenda=top_cat,
        comparacao_yoy=yoy,
        pacientes=pacientes,
        evolution=evolution,
    )
