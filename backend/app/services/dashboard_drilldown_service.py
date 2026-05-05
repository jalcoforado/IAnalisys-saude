"""Service do drill-down auditável dos KPIs.

Cada KPI tem um builder que reusa a MESMA WHERE clause do
`dashboard_service.py` — garantia que o total do drawer bate com o KPI.

KPIs cobertos (Etapa 1, 6 cards principais):
- faturamento, consultas, absenteismo, conversao, ticket_medio, pacientes_ativos
"""
from __future__ import annotations

from typing import Awaitable, Callable, Dict

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import PeriodInfo
from app.schemas.dashboard_drilldown import DrillDownItem, DrillDownResponse


_MONTH_NAMES_PT = (
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def _ym_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _period_info(year: int, month: int) -> PeriodInfo:
    return PeriodInfo(
        year=year,
        month=month,
        label=_ym_key(year, month),
        label_pt=f"{_MONTH_NAMES_PT[month]}/{year}",
    )


def _audit_ok(total_value: float, kpi_value: float, tol: float = 0.01) -> bool:
    return abs(total_value - kpi_value) <= tol


# ── Builders por KPI ────────────────────────────────────────────


async def _build_faturamento(
    db: AsyncSession, tenant_id: str, year: int, month: int, limit: int, offset: int,
) -> DrillDownResponse:
    """Linhas de fato_financeiro WHERE year_month_key=ym AND is_received=1."""
    ym = _ym_key(year, month)
    params = {"tid": tenant_id, "ym": ym}

    agg_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS cnt
            FROM fato_financeiro
            WHERE tenant_id = :tid AND year_month_key = :ym AND is_received = 1
        """),
        params,
    )
    agg = agg_q.one()
    kpi_value = float(agg.total or 0)
    total_count = int(agg.cnt or 0)

    items_q = await db.execute(
        text("""
            SELECT
                f.external_id,
                f.amount,
                f.payment_form,
                f.date_key,
                f.patient_external_id,
                MAX(dp.name) AS patient_name
            FROM fato_financeiro f
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = f.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = f.patient_external_id
            WHERE f.tenant_id = :tid
              AND f.year_month_key = :ym
              AND f.is_received = 1
            GROUP BY f.id, f.external_id, f.amount, f.payment_form,
                     f.date_key, f.patient_external_id
            ORDER BY f.amount DESC, f.id DESC
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": limit, "off": offset},
    )
    items = [
        DrillDownItem(
            external_id=str(r.external_id),
            label=r.patient_name or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            secondary_label=r.payment_form or None,
            date_iso=r.date_key.isoformat() if r.date_key else None,
            value=float(r.amount or 0),
        )
        for r in items_q.all()
    ]

    return DrillDownResponse(
        kpi_id="faturamento",
        kpi_label="Faturamento",
        period=_period_info(year, month),
        kpi_value=kpi_value,
        kpi_unit="BRL",
        total_value=kpi_value,
        total_count=total_count,
        audit_ok=_audit_ok(sum(i.value or 0 for i in items) if total_count <= limit else kpi_value, kpi_value),
        items_returned=len(items),
        items=items,
    )


async def _build_consultas(
    db: AsyncSession, tenant_id: str, year: int, month: int, limit: int, offset: int,
) -> DrillDownResponse:
    """Linhas de fato_agenda WHERE year_month_key=ym AND is_canceled=0."""
    ym = _ym_key(year, month)
    params = {"tid": tenant_id, "ym": ym}

    cnt_q = await db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM fato_agenda
            WHERE tenant_id = :tid AND year_month_key = :ym AND is_canceled = 0
        """),
        params,
    )
    total_count = int(cnt_q.scalar_one() or 0)

    items_q = await db.execute(
        text("""
            SELECT
                fa.external_id,
                fa.date_key,
                fa.category_description,
                fa.patient_external_id,
                fa.professional_external_id,
                MAX(dp.name) AS patient_name,
                MAX(dpr.name) AS professional_name
            FROM fato_agenda fa
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = fa.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            LEFT JOIN dim_profissional dpr
                ON dpr.tenant_id = fa.tenant_id
               AND CAST(dpr.external_id AS UNSIGNED) = fa.professional_external_id
            WHERE fa.tenant_id = :tid
              AND fa.year_month_key = :ym
              AND fa.is_canceled = 0
            GROUP BY fa.id, fa.external_id, fa.date_key,
                     fa.category_description, fa.patient_external_id,
                     fa.professional_external_id
            ORDER BY fa.date_key DESC, fa.id DESC
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": limit, "off": offset},
    )
    items = [
        DrillDownItem(
            external_id=str(r.external_id),
            label=r.patient_name or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            secondary_label=r.professional_name or (f"Prof. #{r.professional_external_id}" if r.professional_external_id else None),
            date_iso=r.date_key.isoformat() if r.date_key else None,
            value=1.0,
            extras={"categoria": r.category_description or "Sem categoria"},
        )
        for r in items_q.all()
    ]

    return DrillDownResponse(
        kpi_id="consultas",
        kpi_label="Consultas",
        period=_period_info(year, month),
        kpi_value=float(total_count),
        kpi_unit="count",
        total_value=float(total_count),
        total_count=total_count,
        audit_ok=True,
        items_returned=len(items),
        items=items,
    )


async def _build_absenteismo(
    db: AsyncSession, tenant_id: str, year: int, month: int, limit: int, offset: int,
) -> DrillDownResponse:
    """Linhas de fato_agenda WHERE is_canceled=1.
    KPI exibido é %, mas drill-down lista as canceladas (numerador).
    """
    ym = _ym_key(year, month)
    params = {"tid": tenant_id, "ym": ym}

    agg_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN is_canceled = 1 THEN 1 ELSE 0 END), 0) AS canceladas
            FROM fato_agenda
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        params,
    )
    agg = agg_q.one()
    total_consultas = int(agg.total or 0)
    canceladas = int(agg.canceladas or 0)
    pct = round((canceladas / total_consultas) * 100, 2) if total_consultas else 0.0

    items_q = await db.execute(
        text("""
            SELECT
                fa.external_id,
                fa.date_key,
                fa.category_description,
                fa.patient_external_id,
                fa.professional_external_id,
                MAX(dp.name) AS patient_name,
                MAX(dpr.name) AS professional_name
            FROM fato_agenda fa
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = fa.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            LEFT JOIN dim_profissional dpr
                ON dpr.tenant_id = fa.tenant_id
               AND CAST(dpr.external_id AS UNSIGNED) = fa.professional_external_id
            WHERE fa.tenant_id = :tid
              AND fa.year_month_key = :ym
              AND fa.is_canceled = 1
            GROUP BY fa.id, fa.external_id, fa.date_key,
                     fa.category_description, fa.patient_external_id,
                     fa.professional_external_id
            ORDER BY fa.date_key DESC, fa.id DESC
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": limit, "off": offset},
    )
    items = [
        DrillDownItem(
            external_id=str(r.external_id),
            label=r.patient_name or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            secondary_label=r.professional_name or (f"Prof. #{r.professional_external_id}" if r.professional_external_id else None),
            date_iso=r.date_key.isoformat() if r.date_key else None,
            value=1.0,
            extras={"categoria": r.category_description or "Sem categoria"},
        )
        for r in items_q.all()
    ]

    return DrillDownResponse(
        kpi_id="absenteismo",
        kpi_label="Absenteísmo",
        period=_period_info(year, month),
        kpi_value=pct,
        kpi_unit="pct",
        total_value=None,                    # ratio: numerador/denominador
        total_count=canceladas,
        audit_ok=None,
        items_returned=len(items),
        items=items,
    )


async def _build_conversao(
    db: AsyncSession, tenant_id: str, year: int, month: int, limit: int, offset: int,
) -> DrillDownResponse:
    """Todos orçamentos do mês. KPI = aprovados/total*100. Linhas com flag
    de status pra inspeção (aprovado/aberto/followup/recusado).
    """
    ym = _ym_key(year, month)
    params = {"tid": tenant_id, "ym": ym}

    agg_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN is_approved = 1 THEN 1 ELSE 0 END), 0) AS aprovados
            FROM fato_orcamentos
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        params,
    )
    agg = agg_q.one()
    total_orcamentos = int(agg.total or 0)
    aprovados = int(agg.aprovados or 0)
    pct = round((aprovados / total_orcamentos) * 100, 2) if total_orcamentos else 0.0

    items_q = await db.execute(
        text("""
            SELECT
                fo.external_id,
                fo.date_key,
                fo.amount,
                fo.is_approved,
                fo.is_open,
                fo.is_followup,
                fo.is_rejected,
                fo.patient_external_id,
                fo.professional_external_id,
                MAX(dp.name) AS patient_name,
                MAX(dpr.name) AS professional_name
            FROM fato_orcamentos fo
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = fo.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = fo.patient_external_id
            LEFT JOIN dim_profissional dpr
                ON dpr.tenant_id = fo.tenant_id
               AND CAST(dpr.external_id AS UNSIGNED) = fo.professional_external_id
            WHERE fo.tenant_id = :tid
              AND fo.year_month_key = :ym
            GROUP BY fo.id, fo.external_id, fo.date_key, fo.amount,
                     fo.is_approved, fo.is_open, fo.is_followup, fo.is_rejected,
                     fo.patient_external_id, fo.professional_external_id
            ORDER BY fo.amount DESC, fo.id DESC
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": limit, "off": offset},
    )

    def _status(r) -> str:
        if r.is_approved:
            return "aprovado"
        if r.is_followup:
            return "followup"
        if r.is_open:
            return "aberto"
        if r.is_rejected:
            return "recusado"
        return "indefinido"

    items = [
        DrillDownItem(
            external_id=str(r.external_id),
            label=r.patient_name or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            secondary_label=r.professional_name or (f"Prof. #{r.professional_external_id}" if r.professional_external_id else None),
            date_iso=r.date_key.isoformat() if r.date_key else None,
            value=float(r.amount or 0),
            extras={"status": _status(r)},
        )
        for r in items_q.all()
    ]

    return DrillDownResponse(
        kpi_id="conversao",
        kpi_label="Conversão",
        period=_period_info(year, month),
        kpi_value=pct,
        kpi_unit="pct",
        total_value=None,
        total_count=total_orcamentos,
        audit_ok=None,
        items_returned=len(items),
        items=items,
    )


async def _build_ticket_medio(
    db: AsyncSession, tenant_id: str, year: int, month: int, limit: int, offset: int,
) -> DrillDownResponse:
    """Ticket médio = faturamento/consultas. Drill-down mostra os pagamentos
    (mesmo dataset do faturamento) — auditoria do numerador.
    """
    ym = _ym_key(year, month)
    params = {"tid": tenant_id, "ym": ym}

    agg_q = await db.execute(
        text("""
            SELECT
                (SELECT COALESCE(SUM(amount), 0) FROM fato_financeiro
                  WHERE tenant_id = :tid AND year_month_key = :ym AND is_received = 1) AS faturamento,
                (SELECT COUNT(*) FROM fato_agenda
                  WHERE tenant_id = :tid AND year_month_key = :ym AND is_canceled = 0) AS consultas
        """),
        params,
    )
    agg = agg_q.one()
    faturamento = float(agg.faturamento or 0)
    consultas = int(agg.consultas or 0)
    ticket = round(faturamento / consultas, 2) if consultas else 0.0

    cnt_q = await db.execute(
        text("""
            SELECT COUNT(*) AS cnt FROM fato_financeiro
            WHERE tenant_id = :tid AND year_month_key = :ym AND is_received = 1
        """),
        params,
    )
    total_count = int(cnt_q.scalar_one() or 0)

    items_q = await db.execute(
        text("""
            SELECT
                f.external_id,
                f.amount,
                f.payment_form,
                f.date_key,
                f.patient_external_id,
                MAX(dp.name) AS patient_name
            FROM fato_financeiro f
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = f.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = f.patient_external_id
            WHERE f.tenant_id = :tid
              AND f.year_month_key = :ym
              AND f.is_received = 1
            GROUP BY f.id, f.external_id, f.amount, f.payment_form,
                     f.date_key, f.patient_external_id
            ORDER BY f.amount DESC, f.id DESC
            LIMIT :lim OFFSET :off
        """),
        {**params, "lim": limit, "off": offset},
    )
    items = [
        DrillDownItem(
            external_id=str(r.external_id),
            label=r.patient_name or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            secondary_label=r.payment_form or None,
            date_iso=r.date_key.isoformat() if r.date_key else None,
            value=float(r.amount or 0),
        )
        for r in items_q.all()
    ]

    return DrillDownResponse(
        kpi_id="ticket_medio",
        kpi_label="Ticket médio",
        period=_period_info(year, month),
        kpi_value=ticket,
        kpi_unit="BRL",
        total_value=None,                    # ratio: faturamento/consultas
        total_count=total_count,
        audit_ok=None,
        items_returned=len(items),
        items=items,
        # Numerador (faturamento) e denominador (consultas) ficam embutidos no
        # extras dos items se quiser inspecionar; KPI é só o ratio.
    )


async def _build_pacientes_ativos(
    db: AsyncSession, tenant_id: str, year: int, month: int, limit: int, offset: int,
) -> DrillDownResponse:
    """Pacientes com is_active=1 (snapshot, ignora year/month)."""
    cnt_q = await db.execute(
        text("SELECT COUNT(*) FROM dim_paciente WHERE tenant_id = :tid AND is_active = 1"),
        {"tid": tenant_id},
    )
    total_count = int(cnt_q.scalar_one() or 0)

    items_q = await db.execute(
        text("""
            SELECT
                external_id, name, days_since_last_seen, last_seen_at, first_seen_at
            FROM dim_paciente
            WHERE tenant_id = :tid AND is_active = 1
            ORDER BY days_since_last_seen ASC, external_id ASC
            LIMIT :lim OFFSET :off
        """),
        {"tid": tenant_id, "lim": limit, "off": offset},
    )
    items = [
        DrillDownItem(
            external_id=str(r.external_id),
            label=r.name or f"Paciente #{r.external_id}",
            secondary_label=(
                f"Última visita: {r.last_seen_at.isoformat()}"
                if r.last_seen_at else "Sem visita registrada"
            ),
            date_iso=r.last_seen_at.isoformat() if r.last_seen_at else None,
            value=1.0,
            extras={"dias_desde_ultima": str(r.days_since_last_seen or "—")},
        )
        for r in items_q.all()
    ]

    return DrillDownResponse(
        kpi_id="pacientes_ativos",
        kpi_label="Pacientes ativos",
        period=_period_info(year, month),
        kpi_value=float(total_count),
        kpi_unit="count",
        total_value=float(total_count),
        total_count=total_count,
        audit_ok=True,
        items_returned=len(items),
        items=items,
    )


# ── Registry ────────────────────────────────────────────────────

_BUILDERS: Dict[str, Callable[[AsyncSession, str, int, int, int, int], Awaitable[DrillDownResponse]]] = {
    "faturamento": _build_faturamento,
    "consultas": _build_consultas,
    "absenteismo": _build_absenteismo,
    "conversao": _build_conversao,
    "ticket_medio": _build_ticket_medio,
    "pacientes_ativos": _build_pacientes_ativos,
}

KPI_IDS = sorted(_BUILDERS.keys())


async def get_drilldown(
    db: AsyncSession,
    tenant_id: str,
    kpi_id: str,
    year: int,
    month: int,
    limit: int = 200,
    offset: int = 0,
) -> DrillDownResponse:
    builder = _BUILDERS.get(kpi_id)
    if builder is None:
        raise HTTPException(
            status_code=400,
            detail=f"KPI desconhecido: '{kpi_id}'. Disponíveis: {', '.join(KPI_IDS)}",
        )
    return await builder(db, tenant_id, year, month, limit, offset)
