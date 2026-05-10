"""
Service do dashboard /analise/financeiro (Sub-PR 20b).

Foco: relatório estratégico-tático para o DONO da clínica.
- Faturamento = orçamentos APROVADOS no mês (`fato_orcamentos.amount WHERE is_approved=1`)
  → vendas fechadas, NÃO pagamentos recebidos
- Recebido = pagamentos confirmados no mês (`fato_financeiro` WHERE is_received=1)
  → caixa que entrou
- Cada KPI vem com MoM/YoY/sparkline 12m/insight narrativo prontos do backend.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analise import (
    AnaliseFinanceiroResponse,
    DescontosSection,
    FinanceiroEvolutionPoint,
    FinanceiroKpis,
    FunilOrcamentos,
    KpiCard,
    MixPagamentoEnriched,
    PeriodInfo,
    OrcamentoParcela,
    OrcamentoStatusItem,
    OrcamentoStatusResponse,
    PrazoAuditItem,
    PrazoAuditResponse,
    PrazoBucket,
    PrazoRecebimentoSection,
    RecebidoBreakdown,
    SaudeRecebiveis,
    TaxaPorForma,
    TaxasSection,
    TopCategoriaFaturamento,
    TopMedicoFaturamento,
    TopProfFaturamento,
)


# ── Helpers de período ──────────────────────────────────────────


_MONTH_PT_SHORT = ("", "jan", "fev", "mar", "abr", "mai", "jun",
                   "jul", "ago", "set", "out", "nov", "dez")
_MONTH_PT_LONG = ("", "janeiro", "fevereiro", "março", "abril", "maio", "junho",
                  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def _ym_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _period(year: int, month: int) -> PeriodInfo:
    return PeriodInfo(
        year=year, month=month,
        year_month_key=_ym_key(year, month),
        label=f"{_MONTH_PT_LONG[month]}/{year}",
    )


def _prev_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _yoy_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, month)


def _delta_pct(curr: float, prev: Optional[float]) -> Optional[float]:
    if prev is None or prev == 0:
        return None
    return round(((curr - prev) / prev) * 100, 1)


def _is_current_month(year: int, month: int, today: Optional[date] = None) -> bool:
    today = today or date.today()
    return today.year == year and today.month == month


def _month_progress(year: int, month: int, today: Optional[date] = None) -> Optional[float]:
    """Fração do mês decorrida (0-1). None quando não é mês corrente.

    Ex: 7 de maio em mês de 31 dias → 7/31 ≈ 0.226.
    """
    today = today or date.today()
    if not _is_current_month(year, month, today):
        return None
    days_in = calendar.monthrange(year, month)[1]
    return today.day / days_in


def _last_12_yms(year: int, month: int) -> List[tuple[int, int]]:
    """12 últimos meses incluindo o atual (mais antigo → mais recente)."""
    out: List[tuple[int, int]] = []
    y, m = year, month
    for _ in range(12):
        out.append((y, m))
        y, m = _prev_month(y, m)
    out.reverse()
    return out


# ── Formatadores ────────────────────────────────────────────────


def _fmt_brl(v: float, compact: bool = False) -> str:
    if compact and abs(v) >= 1_000_000:
        return f"R$ {v / 1_000_000:.2f}M"
    if compact and abs(v) >= 1_000:
        return f"R$ {v / 1_000:.0f}k"
    s = f"R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + s


def _fmt_brl_int(v: float) -> str:
    """Inteiro com pontos como separador de milhar BR. Sem decimais.
    Usado em insights pra evitar conflito do replace global na string toda."""
    return "R$ " + f"{int(round(v)):,}".replace(",", ".")


def _fmt_int(v: float) -> str:
    return f"{int(v):,}".replace(",", ".")


def _fmt_pct(v: float) -> str:
    return f"{v:.1f}%"


def _ym_short_label(year: int, month: int) -> str:
    return f"{_MONTH_PT_SHORT[month]}/{str(year)[-2:]}"


# ── KpiCard builder ─────────────────────────────────────────────


def _build_kpi_card(
    *,
    value: float,
    value_label: str,
    series_12m: List[float],
    is_inverse: bool = False,
    insight: Optional[str] = None,
    partial_progress: Optional[float] = None,
    projected_value: Optional[float] = None,
    projected_label: Optional[str] = None,
    today: Optional[date] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    use_projection_for_compare: bool = False,
) -> KpiCard:
    """Constrói KpiCard com MoM/YoY/sparkline a partir da série de 12 meses.

    series_12m: lista de 12 valores na ordem cronológica (mais antigo → atual).
    O último valor da série DEVE ser igual a `value` (mês corrente).

    Se `use_projection_for_compare=True` e o mês é parcial, MoM/YoY usam o
    `projected_value` em vez do `value` para evitar comparação injusta com
    meses fechados.
    """
    sl = list(series_12m)

    # Para comparação MoM/YoY, usa projeção quando parcial (evita "queda" falsa)
    compare_value = (
        projected_value
        if use_projection_for_compare and projected_value is not None
        else value
    )

    # MoM = atual vs mês anterior (índice -2 da série de 12)
    prev_value = sl[-2] if len(sl) >= 2 else None
    mom_value = (compare_value - prev_value) if prev_value is not None else None
    mom_pct = _delta_pct(compare_value, prev_value)

    # YoY = atual vs mesmo mês ano anterior (índice 0 da série de 12)
    yoy_prev = sl[0] if len(sl) >= 12 else None
    yoy_value = (compare_value - yoy_prev) if yoy_prev is not None else None
    yoy_pct = _delta_pct(compare_value, yoy_prev)

    # Trend baseado nos últimos 3 valores (ignora mês parcial pra não enviesar)
    trend = "flat"
    sl_for_trend = sl[:-1] if partial_progress is not None and len(sl) >= 4 else sl
    if len(sl_for_trend) >= 3:
        last_3 = sl_for_trend[-3:]
        if last_3[0] < last_3[1] < last_3[2]:
            trend = "up"
        elif last_3[0] > last_3[1] > last_3[2]:
            trend = "down"

    # Metadados de parcial pro frontend
    is_partial = partial_progress is not None
    partial_days = None
    partial_days_in_month = None
    if is_partial and year is not None and month is not None:
        t = today or date.today()
        partial_days = t.day
        partial_days_in_month = calendar.monthrange(year, month)[1]

    return KpiCard(
        value=value,
        value_label=value_label,
        mom_value=mom_value,
        mom_pct=mom_pct,
        mom_label=_format_mom_label(mom_value, mom_pct),
        yoy_value=yoy_value,
        yoy_pct=yoy_pct,
        yoy_label=_format_yoy_label(yoy_pct),
        trend=trend,
        sparkline_12m=sl,
        insight=insight,
        is_inverse=is_inverse,
        is_partial=is_partial,
        partial_progress=partial_progress,
        partial_days=partial_days,
        partial_days_in_month=partial_days_in_month,
        projected_value=projected_value,
        projected_label=projected_label,
    )


def _format_mom_label(_mom_value: Optional[float], mom_pct: Optional[float]) -> Optional[str]:
    if mom_pct is None:
        return None
    sign = "+" if mom_pct > 0 else ""
    return f"{sign}{mom_pct:.1f}% vs mês anterior"


def _format_yoy_label(yoy_pct: Optional[float]) -> Optional[str]:
    if yoy_pct is None:
        return None
    sign = "+" if yoy_pct > 0 else ""
    return f"{sign}{yoy_pct:.1f}% vs ano anterior"


# ── Aggregate builders (queries) ────────────────────────────────


@dataclass
class _MonthAgg:
    """Agregação enxuta de 1 mês — só o que financeiro precisa."""
    faturamento: float        # SUM amount WHERE is_approved=1 em fato_orcamentos
    aprovados_qty: int
    gerados_qty: int
    gerados_amount: float
    recebido: float           # SUM amount WHERE is_received=1 em fato_financeiro


async def _aggregate_month(db: AsyncSession, tenant_id: str, ym: str) -> _MonthAgg:
    """1 mês de agregados — 2 queries."""
    orc_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS gerados_qty,
                COALESCE(SUM(amount), 0) AS gerados_amount,
                COALESCE(SUM(CASE WHEN is_approved=1 THEN 1 ELSE 0 END), 0) AS aprovados_qty,
                COALESCE(SUM(CASE WHEN is_approved=1 THEN amount ELSE 0 END), 0) AS faturamento
            FROM fato_orcamentos
            WHERE tenant_id = :tid AND year_month_key = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    orc = orc_q.one()

    # Recebido (LÍQUIDO) — vem de core_summary_entries (type=DEBIT, post_type=RECEIVED).
    # Bate com a coluna "Valor" do relatório "Pagamentos e Comissões" do Clinicorp.
    # Fallback pra core_payments.amount (bruto) se summary_entries não estiver sincronizado.
    # Ver _recebido_breakdown pra detalhes do mapeamento.
    yr_int, mn_int = (int(ym[:4]), int(ym[5:]))
    fin_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0) AS recebido
            FROM core_summary_entries
            WHERE tenant_id = :tid
              AND is_deleted = 0
              AND type = 'DEBIT'
              AND post_type = 'RECEIVED'
              AND year = :yr AND month = :mn
        """),
        {"tid": tenant_id, "yr": yr_int, "mn": mn_int},
    )
    recebido = float(fin_q.scalar_one() or 0)
    if recebido <= 0:
        # Fallback: bruto via core_payments
        fb_q = await db.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) AS recebido
                FROM core_payments
                WHERE tenant_id = :tid
                  AND is_deleted = 0
                  AND is_canceled = 0
                  AND is_received = 1
                  AND DATE_FORMAT(received_date, '%Y-%m') = :ym
            """),
            {"tid": tenant_id, "ym": ym},
        )
        recebido = float(fb_q.scalar_one() or 0)

    return _MonthAgg(
        faturamento=float(orc.faturamento or 0),
        aprovados_qty=int(orc.aprovados_qty or 0),
        gerados_qty=int(orc.gerados_qty or 0),
        gerados_amount=float(orc.gerados_amount or 0),
        recebido=recebido,
    )


async def _aggregate_last_12(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> List[_MonthAgg]:
    """Agrega últimos 12 meses de uma vez (2 queries)."""
    yms = _last_12_yms(year, month)
    keys = [_ym_key(y, m) for y, m in yms]

    orc_q = await db.execute(
        text("""
            SELECT
                year_month_key,
                COUNT(*) AS gerados_qty,
                COALESCE(SUM(amount), 0) AS gerados_amount,
                COALESCE(SUM(CASE WHEN is_approved=1 THEN 1 ELSE 0 END), 0) AS aprovados_qty,
                COALESCE(SUM(CASE WHEN is_approved=1 THEN amount ELSE 0 END), 0) AS faturamento
            FROM fato_orcamentos
            WHERE tenant_id = :tid AND year_month_key IN :keys
            GROUP BY year_month_key
        """).bindparams(),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    orc_by_ym: dict[str, dict] = {}
    for row in orc_q.all():
        orc_by_ym[row.year_month_key] = {
            "gerados_qty": int(row.gerados_qty or 0),
            "gerados_amount": float(row.gerados_amount or 0),
            "aprovados_qty": int(row.aprovados_qty or 0),
            "faturamento": float(row.faturamento or 0),
        }

    # Recebido (LÍQUIDO) por mês — vem de core_summary_entries (DEBIT/RECEIVED).
    # Ver _recebido_breakdown / _aggregate_month sobre o mapeamento.
    fin_q = await db.execute(
        text("""
            SELECT
                CONCAT(year, '-', LPAD(month, 2, '0')) AS year_month_key,
                COALESCE(SUM(amount), 0) AS recebido
            FROM core_summary_entries
            WHERE tenant_id = :tid
              AND is_deleted = 0
              AND type = 'DEBIT'
              AND post_type = 'RECEIVED'
              AND CONCAT(year, '-', LPAD(month, 2, '0')) IN :keys
            GROUP BY year, month
        """).bindparams(),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    fin_by_ym: dict[str, float] = {row.year_month_key: float(row.recebido or 0) for row in fin_q.all()}

    # Fallback: pra meses sem summary_entries (sync incompleto), pega o bruto via core_payments
    missing_keys = [k for k in keys if k not in fin_by_ym or fin_by_ym[k] <= 0]
    if missing_keys:
        fb_q = await db.execute(
            text("""
                SELECT
                    DATE_FORMAT(received_date, '%Y-%m') AS year_month_key,
                    COALESCE(SUM(amount), 0) AS recebido
                FROM core_payments
                WHERE tenant_id = :tid
                  AND is_deleted = 0
                  AND is_canceled = 0
                  AND is_received = 1
                  AND DATE_FORMAT(received_date, '%Y-%m') IN :keys
                GROUP BY DATE_FORMAT(received_date, '%Y-%m')
            """).bindparams(),
            {"tid": tenant_id, "keys": tuple(missing_keys)},
        )
        for r in fb_q.all():
            fin_by_ym[r.year_month_key] = float(r.recebido or 0)

    out: List[_MonthAgg] = []
    for ym in keys:
        orc = orc_by_ym.get(ym, {})
        out.append(_MonthAgg(
            faturamento=orc.get("faturamento", 0.0),
            aprovados_qty=orc.get("aprovados_qty", 0),
            gerados_qty=orc.get("gerados_qty", 0),
            gerados_amount=orc.get("gerados_amount", 0.0),
            recebido=fin_by_ym.get(ym, 0.0),
        ))
    return out


# ── Funil ───────────────────────────────────────────────────────


async def _funil_orcamentos(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str,
) -> FunilOrcamentos:
    """Funil gerados → aprovados → pagos (paciente teve >=1 pagamento)."""
    cur = await _aggregate_month(db, tenant_id, ym)
    prev_aggr = await _aggregate_month(db, tenant_id, ym_prev)

    # Pagos: orçamentos APROVADOS no mês com parcelas em core_payments
    # (mapping real treatment↔payment). pagos_amount = soma das parcelas
    # ligadas a esses orçamentos (caixa Fase 4 — ver reference_clinicorp_payment_phases).
    pagos_q = await db.execute(
        text("""
            SELECT
                COUNT(DISTINCT ce.external_id) AS pagos_qty,
                COALESCE(SUM(cp.amount), 0)    AS pagos_amount
            FROM core_estimates ce
            INNER JOIN core_payments cp
                ON cp.tenant_id = ce.tenant_id
               AND cp.treatment_external_id = ce.external_id
               AND cp.is_deleted = 0
               AND cp.is_canceled = 0
            WHERE ce.tenant_id = :tid
              AND ce.status = 'APPROVED'
              AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    pagos_row = pagos_q.one()
    pagos_qty = int(pagos_row.pagos_qty or 0)
    pagos_amount = float(pagos_row.pagos_amount or 0)

    # Conversão por QUANTIDADE
    conv_aprov_qty = (cur.aprovados_qty / cur.gerados_qty * 100) if cur.gerados_qty else 0.0
    conv_pag_qty = (pagos_qty / cur.aprovados_qty * 100) if cur.aprovados_qty else 0.0

    # Conversão por VALOR (R$) — alinha com Clinicorp ERP
    conv_aprov_val = (cur.faturamento / cur.gerados_amount * 100) if cur.gerados_amount else 0.0
    conv_pag_val = (pagos_amount / cur.faturamento * 100) if cur.faturamento else 0.0

    # MoM das % de conversão (qty)
    conv_aprov_qty_prev = (
        prev_aggr.aprovados_qty / prev_aggr.gerados_qty * 100
    ) if prev_aggr.gerados_qty else None
    aprov_mom_qty = _delta_pct(conv_aprov_qty, conv_aprov_qty_prev) if conv_aprov_qty_prev else None

    # MoM das % de conversão (valor)
    conv_aprov_val_prev = (
        prev_aggr.faturamento / prev_aggr.gerados_amount * 100
    ) if prev_aggr.gerados_amount else None
    aprov_mom_val = _delta_pct(conv_aprov_val, conv_aprov_val_prev) if conv_aprov_val_prev else None

    return FunilOrcamentos(
        gerados_qty=cur.gerados_qty,
        gerados_amount=cur.gerados_amount,
        aprovados_qty=cur.aprovados_qty,
        aprovados_amount=cur.faturamento,
        pagos_qty=pagos_qty,
        pagos_amount=pagos_amount,
        conversao_aprovacao_pct=round(conv_aprov_qty, 1),
        conversao_pagamento_pct=round(conv_pag_qty, 1),
        conversao_aprovacao_valor_pct=round(conv_aprov_val, 1),
        conversao_pagamento_valor_pct=round(conv_pag_val, 1),
        aprovacao_mom_pct=aprov_mom_qty,
        pagamento_mom_pct=None,
        aprovacao_valor_mom_pct=aprov_mom_val,
        pagamento_valor_mom_pct=None,
    )


# ── Mix de meios de pagamento (com MoM) ─────────────────────────


async def _mix_pagamento(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str,
    progress: Optional[float] = None,
) -> List[MixPagamentoEnriched]:
    # Mix por forma de pagamento — mesma lógica do Recebido (received_date).
    cur_q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(payment_form, ''), 'Não informado') AS forma,
                SUM(amount) AS valor,
                COUNT(*) AS qtd
            FROM core_payments
            WHERE tenant_id = :tid
              AND is_deleted = 0
              AND is_canceled = 0
              AND is_received = 1
              AND DATE_FORMAT(received_date, '%Y-%m') = :ym
            GROUP BY forma
        """),
        {"tid": tenant_id, "ym": ym},
    )
    cur_rows = cur_q.all()
    total = sum(float(r.valor or 0) for r in cur_rows) or 1

    prev_q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(payment_form, ''), 'Não informado') AS forma,
                SUM(amount) AS valor
            FROM core_payments
            WHERE tenant_id = :tid
              AND is_deleted = 0
              AND is_canceled = 0
              AND is_received = 1
              AND DATE_FORMAT(received_date, '%Y-%m') = :ym
            GROUP BY forma
        """),
        {"tid": tenant_id, "ym": ym_prev},
    )
    prev_by_forma = {r.forma: float(r.valor or 0) for r in prev_q.all()}

    # Mês parcial: compara projeção (valor / progress) com mês anterior fechado
    is_partial = progress is not None and progress > 0

    out: List[MixPagamentoEnriched] = []
    for r in cur_rows:
        valor = float(r.valor or 0)
        compare_valor = (valor / progress) if is_partial else valor
        out.append(MixPagamentoEnriched(
            forma_pagamento=r.forma,
            valor=valor,
            pct=round(valor / total * 100, 1),
            qtd_transacoes=int(r.qtd or 0),
            mom_pct=_delta_pct(compare_valor, prev_by_forma.get(r.forma)),
        ))
    out.sort(key=lambda m: m.valor, reverse=True)
    return out


# ── Top profissionais por faturamento ───────────────────────────


async def _top_profs_faturamento(
    db: AsyncSession, tenant_id: str, ym: str,
    faturamento_total: float, top_n: int = 8,
) -> List[TopProfFaturamento]:
    q = await db.execute(
        text("""
            SELECT
                o.professional_external_id AS pid,
                MAX(p.name) AS nome,
                COUNT(*) AS gerados,
                COALESCE(SUM(o.amount), 0) AS valor_gerado,
                SUM(CASE WHEN o.is_approved=1 THEN 1 ELSE 0 END) AS aprovados,
                COALESCE(SUM(CASE WHEN o.is_approved=1 THEN o.amount ELSE 0 END), 0) AS fat
            FROM fato_orcamentos o
            LEFT JOIN dim_profissional p
                ON p.tenant_id = o.tenant_id
               AND CAST(p.external_id AS UNSIGNED) = o.professional_external_id
            WHERE o.tenant_id = :tid AND o.year_month_key = :ym
              AND o.professional_external_id IS NOT NULL
            GROUP BY o.professional_external_id
            HAVING aprovados > 0
            ORDER BY fat DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    rows = q.all()
    total_fat = faturamento_total or 1

    out: List[TopProfFaturamento] = []
    for r in rows:
        fat = float(r.fat or 0)
        valor_gerado = float(r.valor_gerado or 0)
        gerados = int(r.gerados or 0)
        aprovados = int(r.aprovados or 0)
        out.append(TopProfFaturamento(
            professional_external_id=int(r.pid),
            nome=r.nome or f"Prof. #{r.pid}",
            faturamento=fat,
            valor_gerado=valor_gerado,
            qtd_aprovados=aprovados,
            qtd_gerados=gerados,
            taxa_conversao_pct=round(aprovados / gerados * 100, 1) if gerados else 0.0,
            taxa_conversao_valor_pct=round(fat / valor_gerado * 100, 1) if valor_gerado else 0.0,
            ticket_medio=round(fat / aprovados, 2) if aprovados else 0.0,
            pct_total=round(fat / total_fat * 100, 1),
        ))
    return out


# ── Top médicos (dentistas) por faturamento ─────────────────────


async def _top_medicos_faturamento(
    db: AsyncSession, tenant_id: str, ym: str,
    faturamento_total: float, top_n: int = 8,
) -> List[TopMedicoFaturamento]:
    """Médicos executantes ranqueados por faturamento dos procedimentos.

    Usa **distribuição proporcional**: para cada procedimento, atribui ao
    médico uma fração do `fato_orcamentos.amount` (valor negociado, com
    desconto) proporcional ao peso do procedimento no orçamento. Garante
    SUM(faturamento_por_médico) = faturamento total do mês.

    `fato_orcamentos.amount` é o valor final negociado; `procedure.final_amount`
    é o valor de tabela antes de descontos. Somar `final_amount` direto
    inflaciona ~17% — por isso a distribuição.
    """
    q = await db.execute(
        text("""
            WITH proc_share AS (
                SELECT
                    ep.dentist_external_id AS did,
                    ep.dentist_name AS dname,
                    o.external_id AS orc_id,
                    o.amount * (
                        COALESCE(ep.final_amount, ep.amount, 0) /
                        NULLIF(SUM(COALESCE(ep.final_amount, ep.amount, 0))
                               OVER (PARTITION BY o.external_id), 0)
                    ) AS share
                FROM core_estimate_procedures ep
                INNER JOIN fato_orcamentos o
                    ON o.tenant_id = ep.tenant_id
                   AND ep.treatment_external_id = CAST(o.external_id AS UNSIGNED)
                WHERE ep.tenant_id = :tid
                  AND ep.is_deleted = 0
                  AND o.year_month_key = :ym
                  AND o.is_approved = 1
            )
            SELECT
                did,
                COALESCE(MAX(dname), CONCAT('Dentista #', did)) AS nome,
                COUNT(*) AS qtd_proc,
                COUNT(DISTINCT orc_id) AS qtd_orc,
                COALESCE(SUM(share), 0) AS fat
            FROM proc_share
            WHERE did IS NOT NULL
            GROUP BY did
            HAVING fat > 0
            ORDER BY fat DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    rows = q.all()
    if not rows:
        return []

    # Denominador do % = faturamento TOTAL da clínica (não soma do top N).
    # Garante que o % some <100% quando há médicos fora do top N e bate com o KPI.
    denom = faturamento_total or 1

    out: List[TopMedicoFaturamento] = []
    for r in rows:
        fat = float(r.fat or 0)
        qtd_proc = int(r.qtd_proc or 0)
        out.append(TopMedicoFaturamento(
            dentist_external_id=int(r.did),
            nome=r.nome or f"Dentista #{r.did}",
            faturamento=round(fat, 2),
            qtd_procedimentos=qtd_proc,
            qtd_orcamentos=int(r.qtd_orc or 0),
            ticket_medio_procedimento=round(fat / qtd_proc, 2) if qtd_proc else 0.0,
            pct_total=round(fat / denom * 100, 1),
        ))
    return out


# ── Top categorias por faturamento ──────────────────────────────


async def _top_categorias_faturamento(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str,
    faturamento_total: float, progress: Optional[float] = None, top_n: int = 8,
) -> List[TopCategoriaFaturamento]:
    """Categoriza orçamentos aprovados pela ESPECIALIDADE dos procedimentos.

    Usa **distribuição proporcional** (mesma lógica de `_top_medicos_faturamento`):
    cada procedimento recebe uma fração do `fato_orcamentos.amount` (valor
    negociado) proporcional ao seu peso no orçamento. Soma por categoria
    = faturamento total do mês.
    """
    cur_q = await db.execute(
        text("""
            WITH proc_share AS (
                SELECT
                    COALESCE(NULLIF(s.description, ''), 'Sem categoria') AS categoria,
                    o.external_id AS orc_id,
                    o.amount * (
                        COALESCE(ep.final_amount, ep.amount, 0) /
                        NULLIF(SUM(COALESCE(ep.final_amount, ep.amount, 0))
                               OVER (PARTITION BY o.external_id), 0)
                    ) AS share
                FROM fato_orcamentos o
                JOIN core_estimate_procedures ep
                    ON ep.tenant_id = o.tenant_id
                   AND ep.treatment_external_id = CAST(o.external_id AS UNSIGNED)
                LEFT JOIN core_specialties s
                    ON s.tenant_id = ep.tenant_id
                   AND CAST(s.external_id AS UNSIGNED) = ep.specialty_id
                WHERE o.tenant_id = :tid AND o.year_month_key = :ym
                  AND ep.is_deleted = 0
                  AND o.is_approved = 1
            )
            SELECT
                categoria,
                COUNT(*)               AS qtd_procs,
                COALESCE(SUM(share), 0) AS fat
            FROM proc_share
            GROUP BY categoria
            ORDER BY fat DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    cur_rows = cur_q.all()
    # Denominador do % = faturamento TOTAL da clínica (não soma do top N)
    total = faturamento_total or 1

    prev_q = await db.execute(
        text("""
            WITH proc_share AS (
                SELECT
                    COALESCE(NULLIF(s.description, ''), 'Sem categoria') AS categoria,
                    o.amount * (
                        COALESCE(ep.final_amount, ep.amount, 0) /
                        NULLIF(SUM(COALESCE(ep.final_amount, ep.amount, 0))
                               OVER (PARTITION BY o.external_id), 0)
                    ) AS share
                FROM fato_orcamentos o
                JOIN core_estimate_procedures ep
                    ON ep.tenant_id = o.tenant_id
                   AND ep.treatment_external_id = CAST(o.external_id AS UNSIGNED)
                LEFT JOIN core_specialties s
                    ON s.tenant_id = ep.tenant_id
                   AND CAST(s.external_id AS UNSIGNED) = ep.specialty_id
                WHERE o.tenant_id = :tid AND o.year_month_key = :ym
                  AND ep.is_deleted = 0
                  AND o.is_approved = 1
            )
            SELECT categoria, COALESCE(SUM(share), 0) AS fat
            FROM proc_share
            GROUP BY categoria
        """),
        {"tid": tenant_id, "ym": ym_prev},
    )
    prev_by_cat = {r.categoria: float(r.fat or 0) for r in prev_q.all()}

    # Mês parcial: compara projeção (fat / progress) com mês anterior fechado
    is_partial = progress is not None and progress > 0

    out: List[TopCategoriaFaturamento] = []
    for r in cur_rows:
        fat = float(r.fat or 0)
        qtd = int(r.qtd_procs or 0)
        compare_fat = (fat / progress) if is_partial else fat
        out.append(TopCategoriaFaturamento(
            categoria=r.categoria,
            faturamento=round(fat, 2),
            qtd_procs=qtd,
            pct_total=round(fat / total * 100, 1),
            ticket_medio=round(fat / qtd, 2) if qtd else 0.0,
            mom_pct=_delta_pct(compare_fat, prev_by_cat.get(r.categoria)),
        ))
    return out


# ── Saúde de recebíveis ─────────────────────────────────────────


async def _saude_recebiveis(
    db: AsyncSession, tenant_id: str, ym: str, faturamento_mes: float,
) -> SaudeRecebiveis:
    """Tempos médios + inadimplência tier.

    Limitação: `core_estimates` não tem coluna `approved_at` separada.
    Usamos `external_updated_at` quando `status='APPROVED'` como proxy do
    momento da aprovação. Funciona razoavelmente bem porque o Clinicorp
    atualiza esse timestamp na transição pra APPROVED, mas pode ser ruidoso
    se o orçamento for editado depois (raro). Tempo gerado→aprovado fica
    None por enquanto (precisa coluna dedicada).
    """
    tempo_aprov: Optional[float] = None  # sem coluna confiável

    # Tempo médio aprovação → 1º pagamento (proxy via external_updated_at)
    tempo_pag_q = await db.execute(
        text("""
            SELECT AVG(DATEDIFF(p.first_pay, e.approved_at)) AS dias
            FROM (
                SELECT patient_external_id, external_updated_at AS approved_at
                FROM core_estimates
                WHERE tenant_id = :tid
                  AND status = 'APPROVED'
                  AND DATE_FORMAT(external_updated_at, '%Y-%m') = :ym
            ) e
            JOIN (
                SELECT patient_external_id, MIN(payment_date) AS first_pay
                FROM core_payments
                WHERE tenant_id = :tid AND payment_date IS NOT NULL
                GROUP BY patient_external_id
            ) p ON p.patient_external_id = e.patient_external_id
            WHERE p.first_pay >= e.approved_at
              AND DATEDIFF(p.first_pay, e.approved_at) < 365
        """),
        {"tid": tenant_id, "ym": ym},
    )
    tempo_pag = tempo_pag_q.scalar_one_or_none()

    # Inadimplência via fato_caixa CA (RECEITA em aberto)
    inad_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS qtd_total,
                COALESCE(SUM(valor_em_aberto_rateado), 0) AS amount_total,
                SUM(CASE WHEN dias_atraso >= 60 THEN 1 ELSE 0 END) AS qtd_60,
                COALESCE(SUM(CASE WHEN dias_atraso >= 60 THEN valor_em_aberto_rateado ELSE 0 END), 0) AS amount_60
            FROM fato_caixa
            WHERE tenant_id = :tid
              AND tipo = 'RECEITA'
              AND is_em_aberto = 1
              AND dias_atraso > 0
        """),
        {"tid": tenant_id},
    )
    row = inad_q.one()
    amount_total = float(row.amount_total or 0)

    return SaudeRecebiveis(
        tempo_medio_aprovacao_dias=round(float(tempo_aprov), 1) if tempo_aprov is not None else None,
        tempo_medio_recebimento_dias=round(float(tempo_pag), 1) if tempo_pag is not None else None,
        inadimplencia_qty=int(row.qtd_total or 0),
        inadimplencia_amount=amount_total,
        inadimplencia_60d_qty=int(row.qtd_60 or 0),
        inadimplencia_60d_amount=float(row.amount_60 or 0),
        inadimplencia_pct_total=round(amount_total / faturamento_mes * 100, 1) if faturamento_mes else None,
    )


# ── KPI builders compostos ──────────────────────────────────────


def _build_faturamento_card(
    series: List[_MonthAgg], *,
    year: Optional[int] = None, month: Optional[int] = None,
    progress: Optional[float] = None,
) -> KpiCard:
    cur = series[-1]
    series_12 = [s.faturamento for s in series]

    projected = (cur.faturamento / progress) if progress and progress > 0 else None
    projected_label = (
        f"{_fmt_brl(projected, compact=True)} projetado"
        if projected is not None else None
    )
    compare_val = projected if projected is not None else cur.faturamento

    insight = None
    if len(series) >= 7:
        avg_6 = sum(s.faturamento for s in series[-7:-1]) / 6
        if avg_6 > 0:
            diff = (compare_val - avg_6) / avg_6 * 100
            if abs(diff) >= 5:
                verb = "acima" if diff > 0 else "abaixo"
                qualifier = "projetado " if projected is not None else ""
                insight = f"{qualifier}{abs(diff):.0f}% {verb} da média de 6 meses"

    return _build_kpi_card(
        value=cur.faturamento,
        value_label=_fmt_brl(cur.faturamento, compact=True),
        series_12m=series_12,
        insight=insight,
        partial_progress=progress,
        projected_value=projected,
        projected_label=projected_label,
        year=year, month=month,
        use_projection_for_compare=True,
    )


def _build_conversao_card(
    series: List[_MonthAgg], *,
    year: Optional[int] = None, month: Optional[int] = None,
    progress: Optional[float] = None,
) -> KpiCard:
    """Conversão por VALOR (alinha Clinicorp). Insight traz a por contagem.

    É ratio — não precisa projeção, só sinaliza parcial. Valor de % é
    autocomparável com meses fechados.
    """
    series_valor = [
        (s.faturamento / s.gerados_amount * 100) if s.gerados_amount else 0.0
        for s in series
    ]
    cur_aggr = series[-1]
    cur_valor = series_valor[-1]
    cur_qty_pct = (
        cur_aggr.aprovados_qty / cur_aggr.gerados_qty * 100
    ) if cur_aggr.gerados_qty else 0.0

    insight_parts: List[str] = [
        f"{cur_qty_pct:.0f}% por contagem ({cur_aggr.aprovados_qty}/{cur_aggr.gerados_qty} orçamentos)"
    ]
    if len(series_valor) >= 7:
        avg_6 = sum(series_valor[-7:-1]) / 6
        if abs(cur_valor - avg_6) >= 3:
            verb = "acima" if cur_valor > avg_6 else "abaixo"
            insight_parts.append(f"{abs(cur_valor - avg_6):.0f}pp {verb} da média de 6m")

    return _build_kpi_card(
        value=cur_valor,
        value_label=_fmt_pct(cur_valor),
        series_12m=series_valor,
        insight=" • ".join(insight_parts),
        partial_progress=progress,
        year=year, month=month,
    )


def _build_ticket_medio_card(
    series: List[_MonthAgg], *,
    year: Optional[int] = None, month: Optional[int] = None,
    progress: Optional[float] = None,
) -> KpiCard:
    # Ticket médio é razão (R$/orçamento), não escala com dias do mês —
    # não precisa de projeção, só sinaliza parcial.
    series_12 = [
        (s.faturamento / s.aprovados_qty) if s.aprovados_qty else 0.0
        for s in series
    ]
    return _build_kpi_card(
        value=series_12[-1],
        value_label=_fmt_brl(series_12[-1]),
        series_12m=series_12,
        partial_progress=progress,
        year=year, month=month,
    )


def _build_recebido_card(
    series: List[_MonthAgg], *,
    year: Optional[int] = None, month: Optional[int] = None,
    progress: Optional[float] = None,
) -> KpiCard:
    series_12 = [s.recebido for s in series]
    cur = series_12[-1]
    cur_fat = series[-1].faturamento

    projected = (cur / progress) if progress and progress > 0 else None
    projected_label = (
        f"{_fmt_brl(projected, compact=True)} projetado"
        if projected is not None else None
    )

    insight = None
    if cur_fat > 0:
        ratio = cur / cur_fat * 100
        insight = f"{ratio:.0f}% do faturamento aprovado"

    return _build_kpi_card(
        value=cur,
        value_label=_fmt_brl(cur, compact=True),
        series_12m=series_12,
        insight=insight,
        partial_progress=progress,
        projected_value=projected,
        projected_label=projected_label,
        year=year, month=month,
        use_projection_for_compare=True,
    )


async def _recebido_breakdown(
    db: AsyncSession, tenant_id: str, year: int, month: int, ym: str,
) -> RecebidoBreakdown:
    """Bruto/líquido/taxas dos pagamentos recebidos no mês.

    Fontes (mapeamento validado contra PDF Clinicorp abr/26 — diff < R$ 1):
      Bruto    → core_payments.amount (is_received=1, received_date no mês)
                 = "Valor Total" do PDF "Pagamentos e Comissões"
      Líquido  → core_summary_entries (type='DEBIT', post_type='RECEIVED', ano/mês)
                 = "Valor" do PDF (vem do endpoint /financial/list_summary)
      Taxas    → bruto - líquido = "Taxas/Descontos" do PDF

    A nomenclatura DEBIT/RECEIVED é interna do book contábil do Clinicorp —
    não inverter. O número bate. core_payments NÃO traz o líquido (ServiceAmount
    sempre NULL na API /payment/list).
    """
    bruto_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0) AS bruto
            FROM core_payments
            WHERE tenant_id = :tid
              AND is_deleted = 0
              AND is_canceled = 0
              AND is_received = 1
              AND DATE_FORMAT(received_date, '%Y-%m') = :ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    bruto = float(bruto_q.scalar_one() or 0)

    liquido_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(amount), 0) AS liquido
            FROM core_summary_entries
            WHERE tenant_id = :tid
              AND is_deleted = 0
              AND type = 'DEBIT'
              AND post_type = 'RECEIVED'
              AND year = :yr AND month = :mn
        """),
        {"tid": tenant_id, "yr": year, "mn": month},
    )
    liquido = float(liquido_q.scalar_one() or 0)

    # Fallback: sem dados em summary_entries (sync incompleto), líquido = bruto
    if liquido <= 0:
        liquido = bruto
    taxas = max(bruto - liquido, 0.0)
    return RecebidoBreakdown(
        liquido=liquido,
        bruto=bruto,
        taxas=taxas,
        taxas_pct=(taxas / bruto * 100) if bruto > 0 else 0.0,
    )


# ── Taxas de adquirência por forma ──────────────────────────────


# Formas que tradicionalmente NÃO cobram taxa (mesmo sendo registradas, líquido = bruto).
# Usado pra calcular bruto_com_taxa = total - bruto_sem_taxa.
_FORMAS_SEM_TAXA = {"Pix", "Dinheiro", "Transferência"}

# Taxas de mercado calibradas em odonto (validado contra Coelho abr/26):
# Crédito 4,89% · Débito 0,91% · Boleto 0,44%. As proporções abaixo
# preservam essa relação aproximada (5,0 / 0,9 / 0,4). O scale interno
# empurra os números pra somar exatamente o total real do mês — com essa
# proporção o resultado fica < 0,1pp do real para cada forma.
_DEFAULT_TAXA_RATES_PCT = {
    "Cartão de Crédito": 5.0,
    "Cartão de Débito": 0.9,
    "Boleto": 0.4,
}


async def _taxas_section(
    db: AsyncSession, tenant_id: str, year: int, month: int, ym: str,
    ym_prev: str, ym_yoy: str, py: int, pm: int, yy: int, ym_yoy_int: int,
) -> TaxasSection:
    """Custo de adquirência por forma de pagamento.

    Estratégia em duas camadas:
    1. Tenta cruzar bruto (core_payments por payment_form) com líquido
       (core_summary_entries por payment_form_characteristic_id, type=DEBIT,
       post_type=RECEIVED) usando o characteristic_id como chave.
    2. Se a API do Clinicorp não popular pf_id nas linhas DEBIT/RECEIVED
       (caso comum), usa fallback heurístico com taxas de mercado típicas
       calibradas pra somar exatamente o total real de taxas.

    Calcula 2 indicadores que o card simples não mostra:
    - Taxa efetiva: taxa / bruto_com_taxa (descontando Pix/Dinheiro)
    - Taxa por forma: pra negociar com cada adquirente individualmente
    """
    async def _aggregate(yr: int, mn: int, ym_key: str) -> dict:
        # Bruto + qtd transações por forma (core_payments)
        bruto_q = await db.execute(
            text("""
                SELECT
                    COALESCE(NULLIF(payment_form, ''), 'Não informado') AS forma,
                    payment_form_characteristic_id AS pf_id,
                    COALESCE(SUM(amount), 0) AS bruto,
                    COUNT(*) AS qtd
                FROM core_payments
                WHERE tenant_id = :tid
                  AND is_deleted = 0
                  AND is_canceled = 0
                  AND is_received = 1
                  AND DATE_FORMAT(received_date, '%Y-%m') = :ym
                GROUP BY payment_form, payment_form_characteristic_id
            """),
            {"tid": tenant_id, "ym": ym_key},
        )
        bruto_rows = bruto_q.all()

        # Líquido por characteristic_id (core_summary_entries)
        liq_q = await db.execute(
            text("""
                SELECT
                    payment_form_characteristic_id AS pf_id,
                    COALESCE(SUM(amount), 0) AS liquido
                FROM core_summary_entries
                WHERE tenant_id = :tid
                  AND is_deleted = 0
                  AND type = 'DEBIT'
                  AND post_type = 'RECEIVED'
                  AND year = :yr AND month = :mn
                GROUP BY payment_form_characteristic_id
            """),
            {"tid": tenant_id, "yr": yr, "mn": mn},
        )
        liq_by_pfid: dict = {r.pf_id: float(r.liquido or 0) for r in liq_q.all()}

        # Líquido total GLOBAL (independe de pf_id) — fonte de verdade
        liq_total_q = await db.execute(
            text("""
                SELECT COALESCE(SUM(amount), 0) AS liquido
                FROM core_summary_entries
                WHERE tenant_id = :tid
                  AND is_deleted = 0
                  AND type = 'DEBIT'
                  AND post_type = 'RECEIVED'
                  AND year = :yr AND month = :mn
            """),
            {"tid": tenant_id, "yr": yr, "mn": mn},
        )
        liquido_global = float(liq_total_q.scalar_one() or 0)

        # Agrupa por forma (string) — mesma forma pode ter vários pf_ids
        agg: dict[str, dict] = {}
        for r in bruto_rows:
            forma = r.forma
            bruto_v = float(r.bruto or 0)
            liq_v = liq_by_pfid.get(r.pf_id, 0.0)
            entry = agg.setdefault(forma, {"bruto": 0.0, "liquido_real": 0.0, "qtd": 0})
            entry["bruto"] += bruto_v
            entry["liquido_real"] += liq_v
            entry["qtd"] += int(r.qtd or 0)

        bruto_total = sum(e["bruto"] for e in agg.values())
        bruto_sem_taxa = sum(
            e["bruto"] for forma, e in agg.items() if forma in _FORMAS_SEM_TAXA
        )
        bruto_com_taxa = bruto_total - bruto_sem_taxa

        # Total real de taxas (fonte: liquido_global vem das R$ 497k que sabemos certo)
        # Se não tiver liquido_global (fallback), usa soma de liquido_real
        if liquido_global > 0:
            taxas_total = max(bruto_total - liquido_global, 0.0)
        else:
            taxas_total = max(bruto_total - sum(e["liquido_real"] for e in agg.values()), 0.0)
            liquido_global = bruto_total - taxas_total

        # Decide se a fatia per-forma vem de dado real ou heurística.
        # Critério: soma das taxas reais per-forma (excluindo Pix/Dinheiro/Transf)
        # deve cobrir pelo menos 50% do total real. Senão é fallback.
        soma_taxa_real = sum(
            max(e["bruto"] - e["liquido_real"], 0.0)
            for forma, e in agg.items()
            if forma not in _FORMAS_SEM_TAXA and e["liquido_real"] > 0
        )
        is_estimated = soma_taxa_real < taxas_total * 0.5

        if is_estimated and bruto_com_taxa > 0 and taxas_total > 0:
            # Heurística: taxa por forma proporcional a bruto * rate_mercado,
            # escalada pra somar EXATAMENTE o taxas_total real.
            expected_per_forma = {
                forma: e["bruto"] * (_DEFAULT_TAXA_RATES_PCT.get(forma, 0.0) / 100)
                for forma, e in agg.items()
            }
            expected_total = sum(expected_per_forma.values())
            scale = (taxas_total / expected_total) if expected_total > 0 else 0.0
            for forma, e in agg.items():
                if forma in _FORMAS_SEM_TAXA:
                    e["taxa"] = 0.0
                else:
                    e["taxa"] = expected_per_forma[forma] * scale
                e["liquido"] = e["bruto"] - e["taxa"]
        else:
            # Dado real é confiável — usa direto, mas força 0 para formas sem taxa
            for forma, e in agg.items():
                if forma in _FORMAS_SEM_TAXA:
                    e["taxa"] = 0.0
                    e["liquido"] = e["bruto"]
                else:
                    e["taxa"] = max(e["bruto"] - e["liquido_real"], 0.0)
                    e["liquido"] = e["bruto"] - e["taxa"]

        return {
            "agg": agg,
            "bruto_total": bruto_total,
            "liquido_total": liquido_global,
            "taxas_total": taxas_total,
            "bruto_sem_taxa": bruto_sem_taxa,
            "bruto_com_taxa": bruto_com_taxa,
            "taxa_global_pct": (taxas_total / bruto_total * 100) if bruto_total > 0 else 0.0,
            "taxa_efetiva_pct": (taxas_total / bruto_com_taxa * 100) if bruto_com_taxa > 0 else 0.0,
            "is_estimated": is_estimated,
        }

    cur = await _aggregate(year, month, ym)
    prev = await _aggregate(py, pm, ym_prev)
    yoyd = await _aggregate(yy, ym_yoy_int, ym_yoy)

    # Lista por forma — ordena por bruto desc (mais relevante primeiro).
    # Marca como estimado APENAS as formas que têm taxa (Pix/Dinheiro são exatas).
    is_est = cur["is_estimated"]
    por_forma: List[TaxaPorForma] = []
    for forma, e in sorted(cur["agg"].items(), key=lambda x: x[1]["bruto"], reverse=True):
        bruto_f = e["bruto"]
        liq_f = e["liquido"]
        taxa_f = max(bruto_f - liq_f, 0.0)
        por_forma.append(TaxaPorForma(
            forma_pagamento=forma,
            bruto=bruto_f,
            liquido=liq_f,
            taxa=taxa_f,
            taxa_pct=(taxa_f / bruto_f * 100) if bruto_f > 0 else 0.0,
            pct_volume=(bruto_f / cur["bruto_total"] * 100) if cur["bruto_total"] > 0 else 0.0,
            qtd_transacoes=e["qtd"],
            is_estimated=(is_est and forma not in _FORMAS_SEM_TAXA),
        ))

    # Economia potencial: se 30% do volume de Cartão Crédito virasse Pix/Dinheiro.
    # 12x pra projetar 1 ano.
    cred = next((f for f in por_forma if "Crédito" in f.forma_pagamento), None)
    economia = 0.0
    if cred and cred.taxa_pct > 0:
        economia = cred.bruto * 0.30 * (cred.taxa_pct / 100) * 12

    mom = (cur["taxa_efetiva_pct"] - prev["taxa_efetiva_pct"]) if prev["bruto_com_taxa"] > 0 else None
    yoy = (cur["taxa_efetiva_pct"] - yoyd["taxa_efetiva_pct"]) if yoyd["bruto_com_taxa"] > 0 else None

    return TaxasSection(
        taxas_total=cur["taxas_total"],
        bruto_total=cur["bruto_total"],
        bruto_com_taxa=cur["bruto_com_taxa"],
        bruto_sem_taxa=cur["bruto_sem_taxa"],
        taxa_global_pct=cur["taxa_global_pct"],
        taxa_efetiva_pct=cur["taxa_efetiva_pct"],
        por_forma=por_forma,
        mom_efetiva_pct=mom,
        yoy_efetiva_pct=yoy,
        economia_potencial_anual=economia,
        is_estimated=cur["is_estimated"],
    )


def _build_inadimplencia_card(current_amount: float) -> KpiCard:
    """Inadimplência muda dia-a-dia. Sparkline 12m precisa de snapshot histórico
    que não temos. Série fica plana até implementarmos snapshot.
    """
    series = [current_amount] * 12
    return _build_kpi_card(
        value=current_amount,
        value_label=_fmt_brl(current_amount, compact=True),
        series_12m=series,
        is_inverse=True,
    )


# ── Descontos (Sub-PR 20b — addendum 2026-05-07) ────────────────


async def _descontos_section(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str, ym_yoy: str,
) -> DescontosSection:
    """Calcula os 3 níveis de desconto sobre orçamentos APROVADOS no mês.

    Decomposição:
      original_amount_tabela = SUM(cep.original_amount) onde o orçamento está aprovado
      faturamento            = SUM(ce.amount) onde is_approved (= header_amount)
      desconto_total         = tabela - faturamento
        ├─ desconto_procedimento = SUM(original - final) por procedimento
        └─ desconto_negociacao   = SUM(final) - faturamento (header)

    MoM/YoY são em pontos percentuais (variação do desconto_pct entre meses).
    """
    # Query 1: agregado por header (sem duplicar pelo join com procs)
    sql_header = """
        SELECT
            COUNT(*) AS qtd,
            COALESCE(SUM(amount), 0) AS faturamento
        FROM core_estimates
        WHERE tenant_id = :tid
          AND is_deleted = 0
          AND DATE_FORMAT(estimate_date, '%Y-%m') = :ym
          AND status = 'APPROVED'
    """
    # Query 2: agregado dos procedimentos APROVADOS dentro de estimates aprovados.
    # IMPORTANTE: filtra cep.status_description='Aprovado' — procs com status 'Orçamento'
    # são sugestões NÃO selecionadas pelo paciente (escopo reduzido), não desconto.
    sql_procs = """
        SELECT
            COALESCE(SUM(cep.original_amount), 0) AS soma_original,
            COALESCE(SUM(cep.final_amount), 0) AS soma_final,
            COUNT(*) AS qtd_procs_aprovados
        FROM core_estimate_procedures cep
        INNER JOIN core_estimates ce ON ce.external_id = cep.treatment_external_id
                                    AND ce.tenant_id = cep.tenant_id
        WHERE ce.tenant_id = :tid
          AND ce.is_deleted = 0
          AND cep.is_deleted = 0
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
          AND ce.status = 'APPROVED'
          AND cep.status_description = 'Aprovado'
    """
    # Query 2b: valor de procedimentos sugeridos mas NÃO aprovados (informativo).
    sql_escopo = """
        SELECT COALESCE(SUM(cep.final_amount), 0) AS escopo_nao_aprovado
        FROM core_estimate_procedures cep
        INNER JOIN core_estimates ce ON ce.external_id = cep.treatment_external_id
                                    AND ce.tenant_id = cep.tenant_id
        WHERE ce.tenant_id = :tid
          AND ce.is_deleted = 0
          AND cep.is_deleted = 0
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
          AND ce.status = 'APPROVED'
          AND (cep.status_description IS NULL OR cep.status_description <> 'Aprovado')
    """

    async def _row(ym_key: str) -> dict:
        h = await db.execute(text(sql_header), {"tid": tenant_id, "ym": ym_key})
        hr = h.one()
        p = await db.execute(text(sql_procs), {"tid": tenant_id, "ym": ym_key})
        pr = p.one()
        e = await db.execute(text(sql_escopo), {"tid": tenant_id, "ym": ym_key})
        escopo_nao_aprovado = float(e.scalar_one() or 0)
        tabela = float(pr.soma_original or 0)
        final = float(pr.soma_final or 0)
        fat = float(hr.faturamento or 0)

        # Desconto total = referência única (tabela vs faturamento). Sempre >= 0.
        desc_total = max(tabela - fat, 0.0)
        desc_total_pct = (desc_total / tabela * 100) if tabela else 0.0

        # Desconto por procedimento = ajuste explícito original→final, clipado em 0
        # (alguns procs vêm com OriginalAmount NULL; isso pode fazer SUM(final) > SUM(original)).
        desc_proc = max(tabela - final, 0.0)
        # Não pode ser maior que o desconto total — clipa.
        desc_proc = min(desc_proc, desc_total)
        desc_proc_pct = (desc_proc / tabela * 100) if tabela else 0.0

        # Desconto negociação = residual, garante que (proc + neg = total).
        desc_neg = max(desc_total - desc_proc, 0.0)
        desc_neg_pct = (desc_neg / tabela * 100) if tabela else 0.0

        return {
            "qtd": int(hr.qtd or 0),
            "tabela": tabela,
            "faturamento": fat,
            "desc_total": desc_total,
            "desc_total_pct": desc_total_pct,
            "desc_proc": desc_proc,
            "desc_proc_pct": desc_proc_pct,
            "desc_neg": desc_neg,
            "desc_neg_pct": desc_neg_pct,
            "escopo_nao_aprovado": escopo_nao_aprovado,
            "qtd_procs_aprovados": int(pr.qtd_procs_aprovados or 0),
        }

    cur = await _row(ym)
    prev = await _row(ym_prev)
    yoy = await _row(ym_yoy)

    mom = (cur["desc_total_pct"] - prev["desc_total_pct"]) if prev["tabela"] else None
    yoy_d = (cur["desc_total_pct"] - yoy["desc_total_pct"]) if yoy["tabela"] else None

    return DescontosSection(
        qtd_orcamentos_aprovados=cur["qtd"],
        qtd_procs_aprovados=cur["qtd_procs_aprovados"],
        original_amount_tabela=cur["tabela"],
        faturamento=cur["faturamento"],
        desconto_total=cur["desc_total"],
        desconto_total_pct=cur["desc_total_pct"],
        desconto_procedimento=cur["desc_proc"],
        desconto_procedimento_pct=cur["desc_proc_pct"],
        desconto_negociacao=cur["desc_neg"],
        desconto_negociacao_pct=cur["desc_neg_pct"],
        escopo_nao_aprovado=cur["escopo_nao_aprovado"],
        mom_total_pct=mom,
        yoy_total_pct=yoy_d,
    )


# ── Prazo de recebimento (Sub-PR 20b — addendum 2026-05-08) ─────


_PRAZO_BUCKETS: list[tuple[str, int, int]] = [
    # (label, min_installments, max_installments) — bordas inclusivas; max=0 significa = min
    ("1x à vista", 1, 1),
    ("2-3x curto", 2, 3),
    ("4-6x médio", 4, 6),
    ("7-12x longo", 7, 12),
    ("13+ muito longo", 13, 999),
]


async def _prazos_recebimento_section(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str, ym_yoy: str,
) -> PrazoRecebimentoSection:
    """Distribuição do valor aprovado por número de parcelas combinadas.

    Pergunta respondida: "Dos R$ X aprovados no mês, quanto vai em 1x, 5x, 12x...?"

    Lógica: cada linha de `core_payments` é UMA parcela. Agrupamos pelo
    `installments_count` daquela parcela e somamos `amount`. Assim, se um
    fechamento misturou entrada Pix 1x + parcelado 25x, cada R$ vai para o
    bucket correto da sua parcela (não há agrupamento por header).

    NULL em `installments_count` é tratado como 1 (avulso/à vista).
    """
    sql_main = """
        SELECT
            COALESCE(cp.installments_count, 1) AS parcels,
            ROUND(SUM(cp.amount), 2) AS valor,
            COUNT(DISTINCT cp.payment_header_external_id) AS qtd_planos,
            AVG(DATEDIFF(cp.due_date, ce.estimate_date)) AS prazo_medio_dias
        FROM core_payments cp
        INNER JOIN core_estimates ce ON ce.external_id = cp.treatment_external_id
                                    AND ce.tenant_id = cp.tenant_id
        WHERE cp.tenant_id = :tid
          AND cp.is_deleted = 0
          AND cp.is_canceled = 0
          AND ce.is_deleted = 0
          AND ce.status = 'APPROVED'
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
        GROUP BY COALESCE(cp.installments_count, 1)
    """

    sql_total_planos = """
        SELECT COUNT(DISTINCT cp.payment_header_external_id) AS qtd
        FROM core_payments cp
        INNER JOIN core_estimates ce ON ce.external_id = cp.treatment_external_id
                                    AND ce.tenant_id = cp.tenant_id
        WHERE cp.tenant_id = :tid
          AND cp.is_deleted = 0
          AND cp.is_canceled = 0
          AND ce.is_deleted = 0
          AND ce.status = 'APPROVED'
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
    """

    # Cobertura: SUM(ce.amount) dos APPROVED no mês (= Faturamento) + qtd/valor
    # dos APPROVED que ainda não têm nenhuma parcela em core_payments.
    # A Clinicorp gera o plano em partes — só temos parcelas conforme pagam.
    sql_cobertura = """
        SELECT
            ROUND(COALESCE(SUM(ce.amount), 0), 2) AS faturamento,
            COALESCE(SUM(CASE WHEN p.cnt IS NULL THEN 1 ELSE 0 END), 0) AS qtd_sem,
            ROUND(COALESCE(SUM(CASE WHEN p.cnt IS NULL THEN ce.amount ELSE 0 END), 0), 2) AS valor_sem
        FROM core_estimates ce
        LEFT JOIN (
            SELECT cp.tenant_id, cp.treatment_external_id, COUNT(*) AS cnt
            FROM core_payments cp
            WHERE cp.tenant_id = :tid AND cp.is_deleted=0 AND cp.is_canceled=0
            GROUP BY cp.tenant_id, cp.treatment_external_id
        ) p ON p.tenant_id = ce.tenant_id AND p.treatment_external_id = ce.external_id
        WHERE ce.tenant_id = :tid
          AND ce.is_deleted = 0
          AND ce.status = 'APPROVED'
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
    """

    async def _aggregate(ym_key: str) -> dict:
        r = await db.execute(text(sql_main), {"tid": tenant_id, "ym": ym_key})
        rows = r.all()
        rt = await db.execute(text(sql_total_planos), {"tid": tenant_id, "ym": ym_key})
        qtd_total = int((rt.scalar() or 0))
        rc = await db.execute(text(sql_cobertura), {"tid": tenant_id, "ym": ym_key})
        cob = rc.one()
        cobertura = {
            "faturamento": float(cob.faturamento or 0),
            "qtd_sem": int(cob.qtd_sem or 0),
            "valor_sem": float(cob.valor_sem or 0),
        }
        if not rows:
            return {
                "qtd_total": 0, "valor_total": 0.0,
                "qtd_a_vista": 0, "valor_a_vista": 0.0,
                "valor_parcelado": 0.0, "qtd_parcelado": 0,
                "soma_prazo_dias": 0.0, "qtd_com_prazo": 0,
                "buckets": {},
                "cobertura": cobertura,
            }

        valor_total = float(sum(float(r.valor or 0) for r in rows))
        qtd_a_vista = int(sum(int(r.qtd_planos or 0) for r in rows if int(r.parcels) == 1))
        valor_a_vista = float(sum(float(r.valor or 0) for r in rows if int(r.parcels) == 1))
        qtd_parcelado = max(qtd_total - qtd_a_vista, 0)
        valor_parcelado = valor_total - valor_a_vista

        # Prazo médio em dias ponderado pelo valor
        prazos_validos = [
            (float(r.prazo_medio_dias), float(r.valor or 0))
            for r in rows if r.prazo_medio_dias is not None
        ]
        soma_prazo = sum(p * v for p, v in prazos_validos)
        soma_valor_prazo = sum(v for _, v in prazos_validos)

        # Buckets
        buckets: dict[str, dict] = {}
        for label, lo, hi in _PRAZO_BUCKETS:
            sel = [r for r in rows if lo <= int(r.parcels) <= hi]
            if not sel:
                continue
            qty = int(sum(int(r.qtd_planos or 0) for r in sel))
            val = float(sum(float(r.valor or 0) for r in sel))
            buckets[label] = {
                "qtd_pagamentos": qty,
                "valor": val,
                "ticket_medio": val / qty if qty else 0.0,
            }

        return {
            "qtd_total": qtd_total,
            "valor_total": valor_total,
            "qtd_a_vista": qtd_a_vista,
            "valor_a_vista": valor_a_vista,
            "qtd_parcelado": qtd_parcelado,
            "valor_parcelado": valor_parcelado,
            "soma_prazo_dias": soma_prazo,
            "qtd_com_prazo": soma_valor_prazo,
            "buckets": buckets,
            "cobertura": cobertura,
        }

    cur = await _aggregate(ym)
    prev = await _aggregate(ym_prev)
    yoy = await _aggregate(ym_yoy)

    pct_a_vista_qtd = (cur["qtd_a_vista"] / cur["qtd_total"] * 100) if cur["qtd_total"] else 0.0
    pct_a_vista_valor = (cur["valor_a_vista"] / cur["valor_total"] * 100) if cur["valor_total"] else 0.0
    prazo_medio = (cur["soma_prazo_dias"] / cur["qtd_com_prazo"]) if cur["qtd_com_prazo"] else 0.0
    ticket_a_vista = (cur["valor_a_vista"] / cur["qtd_a_vista"]) if cur["qtd_a_vista"] else 0.0
    ticket_parcelado = (cur["valor_parcelado"] / cur["qtd_parcelado"]) if cur["qtd_parcelado"] else 0.0

    # MoM/YoY do % à vista (em pontos %)
    prev_pct = (prev["valor_a_vista"] / prev["valor_total"] * 100) if prev["valor_total"] else None
    yoy_pct = (yoy["valor_a_vista"] / yoy["valor_total"] * 100) if yoy["valor_total"] else None
    mom_d = (pct_a_vista_valor - prev_pct) if prev_pct is not None else None
    yoy_d = (pct_a_vista_valor - yoy_pct) if yoy_pct is not None else None

    # Buckets em ordem fixa (mantém narrativa do à vista → muito longo)
    buckets_out: list[PrazoBucket] = []
    for label, _, _ in _PRAZO_BUCKETS:
        b = cur["buckets"].get(label)
        if not b:
            continue
        buckets_out.append(PrazoBucket(
            label=label,
            qtd_pagamentos=b["qtd_pagamentos"],
            valor=b["valor"],
            ticket_medio=b["ticket_medio"],
            pct_qtd=(b["qtd_pagamentos"] / cur["qtd_total"] * 100) if cur["qtd_total"] else 0.0,
            pct_valor=(b["valor"] / cur["valor_total"] * 100) if cur["valor_total"] else 0.0,
        ))

    return PrazoRecebimentoSection(
        qtd_pagamentos_total=cur["qtd_total"],
        valor_total=cur["valor_total"],
        pct_a_vista_qtd=pct_a_vista_qtd,
        pct_a_vista_valor=pct_a_vista_valor,
        prazo_medio_dias=prazo_medio,
        ticket_medio_a_vista=ticket_a_vista,
        ticket_medio_parcelado=ticket_parcelado,
        buckets=buckets_out,
        mom_a_vista_pct=mom_d,
        yoy_a_vista_pct=yoy_d,
        faturamento_aprovado=cur["cobertura"]["faturamento"],
        qtd_sem_parcelas=cur["cobertura"]["qtd_sem"],
        valor_sem_parcelas=cur["cobertura"]["valor_sem"],
    )


# ── Auditoria do prazo (lista detalhada das parcelas) ──────────


async def get_prazos_audit(
    db: AsyncSession,
    tenant_id: str,
    year: int,
    month: int,
    bucket_min: Optional[int] = None,
    bucket_max: Optional[int] = None,
    limit: int = 1000,
) -> PrazoAuditResponse:
    """Lista de parcelas dos orçamentos APROVADOS no mês para auditoria.

    Filtro opcional por faixa de `installments_count` ([min, max] inclusivo).
    Cada linha = uma parcela em `core_payments`. Ordenado por paciente +
    estimate_date pra facilitar conferência manual.
    """
    ym = _ym_key(year, month)

    where_bucket = ""
    params: dict = {"tid": tenant_id, "ym": ym, "lim": limit}
    if bucket_min is not None and bucket_max is not None:
        where_bucket = " AND COALESCE(cp.installments_count, 1) BETWEEN :bmin AND :bmax"
        params["bmin"] = bucket_min
        params["bmax"] = bucket_max

    sql_count = f"""
        SELECT COUNT(*) AS total
        FROM core_payments cp
        INNER JOIN core_estimates ce ON ce.external_id = cp.treatment_external_id
                                    AND ce.tenant_id = cp.tenant_id
        WHERE cp.tenant_id = :tid
          AND cp.is_deleted = 0
          AND cp.is_canceled = 0
          AND ce.is_deleted = 0
          AND ce.status = 'APPROVED'
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
          {where_bucket}
    """

    sql_items = f"""
        SELECT
            cp.treatment_external_id,
            cp.payment_header_external_id,
            COALESCE(cp.patient_name, ce.patient_name) AS patient_name,
            ce.professional_name,
            DATE_FORMAT(ce.estimate_date, '%Y-%m-%d') AS estimate_date,
            ce.amount AS estimate_amount,
            cp.payment_form,
            cp.installment_number,
            cp.installments_count,
            cp.amount,
            DATE_FORMAT(cp.due_date, '%Y-%m-%d') AS due_date
        FROM core_payments cp
        INNER JOIN core_estimates ce ON ce.external_id = cp.treatment_external_id
                                    AND ce.tenant_id = cp.tenant_id
        WHERE cp.tenant_id = :tid
          AND cp.is_deleted = 0
          AND cp.is_canceled = 0
          AND ce.is_deleted = 0
          AND ce.status = 'APPROVED'
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
          {where_bucket}
        ORDER BY patient_name, ce.estimate_date,
                 cp.payment_header_external_id, cp.installment_number
        LIMIT :lim
    """

    rt = await db.execute(text(sql_count), params)
    total = int(rt.scalar() or 0)

    rows = (await db.execute(text(sql_items), params)).all()

    items = [
        PrazoAuditItem(
            treatment_external_id=int(r.treatment_external_id) if r.treatment_external_id else 0,
            payment_header_external_id=int(r.payment_header_external_id) if r.payment_header_external_id else None,
            patient_name=r.patient_name,
            professional_name=r.professional_name,
            estimate_date=r.estimate_date,
            estimate_amount=float(r.estimate_amount) if r.estimate_amount is not None else None,
            payment_form=r.payment_form,
            installment_number=int(r.installment_number) if r.installment_number is not None else None,
            installments_count=int(r.installments_count) if r.installments_count is not None else None,
            amount=float(r.amount or 0),
            due_date=r.due_date,
        )
        for r in rows
    ]

    return PrazoAuditResponse(
        period=_period(year, month),
        items=items,
        total_count=total,
        returned_count=len(items),
        limit=limit,
    )


# ── Auditoria por ORÇAMENTO (status financeiro) ─────────────────


# Tolerância pra comparações float em Reais — diferenças menores que 1 centavo
# entram como "igual" (acumulação de parcelas vs header pode arredondar).
_R_EPS = 0.01


def _classify_orcamento(contratado: float, lancado: float, pago: float, parcelas_qty: int) -> str:
    """5 estados de status pra capturar a pegadinha do plano parcial Clinicorp.

    pago_integral exige cobertura total (pago = lancado = contratado, com tolerância);
    pago_lancado é a situação "100% do plano efetivo pago, mas Clinicorp ainda
    não lançou as demais parcelas" (header > soma_parcelas).
    """
    if parcelas_qty == 0:
        return "sem_parcelas"
    if pago < _R_EPS:
        return "nao_pago"
    if pago + _R_EPS < lancado:
        return "parcial"
    # pago >= lancado (com tolerância)
    if lancado + _R_EPS < contratado:
        return "pago_lancado"
    return "pago_integral"


async def get_orcamentos_status(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> OrcamentoStatusResponse:
    """Lista os orçamentos APROVADOS no mês com status financeiro consolidado.

    Cardinalidade: 1 linha por orçamento (= treatment_external_id) com parcelas
    embutidas. Pra abr/26 são ~250 linhas + ~1500 parcelas no payload.

    Status segue 5 estados — ver docstring de `OrcamentoStatusItem`. As métricas
    `pago` e `parcelas_pagas_qty` usam `is_received=1` (só pagamentos confirmados).
    """
    ym = _ym_key(year, month)

    # Query 1 — orçamentos aprovados com agregados de parcelas
    sql_orcs = """
        SELECT
            ce.external_id AS treatment_external_id,
            COALESCE(MAX(cp.patient_name), MAX(ce.patient_name)) AS patient_name,
            MAX(ce.professional_name) AS professional_name,
            DATE_FORMAT(MAX(ce.estimate_date), '%Y-%m-%d') AS estimate_date,
            MAX(ce.amount) AS contratado,
            COALESCE(SUM(cp.amount), 0) AS lancado,
            COALESCE(SUM(CASE WHEN cp.is_received=1 THEN cp.amount ELSE 0 END), 0) AS pago,
            SUM(CASE WHEN cp.id IS NOT NULL THEN 1 ELSE 0 END) AS parcelas_qty,
            SUM(CASE WHEN cp.is_received=1 THEN 1 ELSE 0 END) AS pagas_qty,
            SUM(CASE WHEN cp.id IS NOT NULL AND cp.is_received=0 THEN 1 ELSE 0 END) AS pendentes_qty,
            SUM(CASE WHEN cp.is_received=0 AND cp.due_date IS NOT NULL AND cp.due_date < CURDATE() THEN 1 ELSE 0 END) AS vencidas_qty
        FROM core_estimates ce
        LEFT JOIN core_payments cp
            ON cp.tenant_id = ce.tenant_id
           AND cp.treatment_external_id = ce.external_id
           AND cp.is_deleted = 0
           AND cp.is_canceled = 0
        WHERE ce.tenant_id = :tid
          AND ce.is_deleted = 0
          AND ce.status = 'APPROVED'
          AND DATE_FORMAT(ce.estimate_date, '%Y-%m') = :ym
        GROUP BY ce.external_id
        ORDER BY MAX(ce.estimate_date) DESC, patient_name
    """
    orcs_rows = (await db.execute(text(sql_orcs), {"tid": tenant_id, "ym": ym})).all()

    if not orcs_rows:
        return OrcamentoStatusResponse(
            period=_period(year, month), items=[],
            contagens={}, totais_contratado=0.0, totais_lancado=0.0, totais_pago=0.0,
        )

    treatment_ids = [int(r.treatment_external_id) for r in orcs_rows]

    # Query 2 — todas as parcelas dos orçamentos acima (1 query batch)
    sql_parcelas = """
        SELECT
            cp.id AS payment_external_id,
            cp.treatment_external_id,
            cp.payment_header_external_id,
            cp.installment_number,
            cp.installments_count,
            cp.amount,
            DATE_FORMAT(cp.due_date, '%Y-%m-%d') AS due_date,
            DATE_FORMAT(cp.received_date, '%Y-%m-%d') AS received_date,
            cp.payment_form,
            cp.is_confirmed,
            cp.is_received,
            -- Fase 4 (Conferência) — Clinicorp marca via check_out_date OU post_date
            (cp.check_out_date IS NOT NULL OR cp.post_date IS NOT NULL) AS is_conferida,
            (cp.is_received = 0 AND cp.due_date IS NOT NULL AND cp.due_date < CURDATE()) AS is_vencida
        FROM core_payments cp
        WHERE cp.tenant_id = :tid
          AND cp.is_deleted = 0
          AND cp.is_canceled = 0
          AND cp.treatment_external_id IN :tids
        ORDER BY cp.treatment_external_id,
                 cp.payment_header_external_id,
                 cp.installment_number
    """
    parcelas_rows = (await db.execute(
        text(sql_parcelas), {"tid": tenant_id, "tids": tuple(treatment_ids)},
    )).all()

    # Agrupa parcelas por treatment_external_id
    parcelas_by_tid: dict[int, list[OrcamentoParcela]] = {}
    for p in parcelas_rows:
        tid = int(p.treatment_external_id) if p.treatment_external_id else 0
        parcelas_by_tid.setdefault(tid, []).append(OrcamentoParcela(
            payment_external_id=int(p.payment_external_id),
            payment_header_external_id=int(p.payment_header_external_id) if p.payment_header_external_id else None,
            installment_number=int(p.installment_number) if p.installment_number is not None else None,
            installments_count=int(p.installments_count) if p.installments_count is not None else None,
            amount=float(p.amount or 0),
            due_date=p.due_date,
            received_date=p.received_date,
            payment_form=p.payment_form,
            is_confirmed=bool(p.is_confirmed),
            is_received=bool(p.is_received),
            is_conferida=bool(p.is_conferida),
            is_vencida=bool(p.is_vencida),
        ))

    # Constroi os items + agregados
    items: list[OrcamentoStatusItem] = []
    contagens = {"sem_parcelas": 0, "nao_pago": 0, "parcial": 0, "pago_lancado": 0, "pago_integral": 0}
    tot_contratado = tot_lancado = tot_pago = 0.0

    for r in orcs_rows:
        tid = int(r.treatment_external_id)
        contratado = float(r.contratado or 0)
        lancado = float(r.lancado or 0)
        pago = float(r.pago or 0)
        parcelas_qty = int(r.parcelas_qty or 0)
        status = _classify_orcamento(contratado, lancado, pago, parcelas_qty)

        contagens[status] = contagens.get(status, 0) + 1
        tot_contratado += contratado
        tot_lancado += lancado
        tot_pago += pago

        items.append(OrcamentoStatusItem(
            treatment_external_id=tid,
            patient_name=r.patient_name,
            professional_name=r.professional_name,
            estimate_date=r.estimate_date,
            contratado=round(contratado, 2),
            lancado=round(lancado, 2),
            pago=round(pago, 2),
            parcelas_qty=parcelas_qty,
            parcelas_pagas_qty=int(r.pagas_qty or 0),
            parcelas_pendentes_qty=int(r.pendentes_qty or 0),
            parcelas_vencidas_qty=int(r.vencidas_qty or 0),
            pct_pago_contratado=round(pago / contratado * 100, 1) if contratado else 0.0,
            pct_pago_lancado=round(pago / lancado * 100, 1) if lancado else 0.0,
            status=status,
            parcelas=parcelas_by_tid.get(tid, []),
        ))

    return OrcamentoStatusResponse(
        period=_period(year, month),
        items=items,
        contagens=contagens,
        totais_contratado=round(tot_contratado, 2),
        totais_lancado=round(tot_lancado, 2),
        totais_pago=round(tot_pago, 2),
    )


# ── API pública ─────────────────────────────────────────────────


async def get_analise_financeiro(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> AnaliseFinanceiroResponse:
    """Builder principal — orquestra todas as queries em paralelo conceitual."""
    ym = _ym_key(year, month)
    py, pm = _prev_month(year, month)
    yy, ym_yoy = _yoy_month(year, month)
    ym_prev = _ym_key(py, pm)
    ym_yoy_key = _ym_key(yy, ym_yoy)

    # 12 meses de agregados (1 query batch)
    series = await _aggregate_last_12(db, tenant_id, year, month)
    faturamento_mes = series[-1].faturamento

    # Mês corrente parcial: progresso (0-1). None pra meses fechados.
    progress = _month_progress(year, month)

    # Sub-builders sequenciais (queries não conflitam, mas async session é single-conn)
    funil = await _funil_orcamentos(db, tenant_id, ym, ym_prev)
    descontos = await _descontos_section(db, tenant_id, ym, ym_prev, ym_yoy_key)
    prazos = await _prazos_recebimento_section(db, tenant_id, ym, ym_prev, ym_yoy_key)
    taxas = await _taxas_section(
        db, tenant_id, year, month, ym,
        ym_prev, ym_yoy_key, py, pm, yy, ym_yoy,
    )
    mix = await _mix_pagamento(db, tenant_id, ym, ym_prev, progress=progress)
    top_profs = await _top_profs_faturamento(db, tenant_id, ym, faturamento_mes)
    top_meds = await _top_medicos_faturamento(db, tenant_id, ym, faturamento_mes)
    top_cats = await _top_categorias_faturamento(
        db, tenant_id, ym, ym_prev, faturamento_mes, progress=progress,
    )

    # KPIs com MoM/YoY/sparkline (passa progress pra ajustar mês corrente)
    faturamento_kpi = _build_faturamento_card(series, year=year, month=month, progress=progress)
    conversao_kpi = _build_conversao_card(series, year=year, month=month, progress=progress)
    ticket_kpi = _build_ticket_medio_card(series, year=year, month=month, progress=progress)
    recebido_kpi = _build_recebido_card(series, year=year, month=month, progress=progress)
    recebido_breakdown = await _recebido_breakdown(db, tenant_id, year, month, ym)

    # Evolution chart (12 meses)
    yms_12 = _last_12_yms(year, month)
    evolution = [
        FinanceiroEvolutionPoint(
            year_month_key=_ym_key(y, m),
            label=_ym_short_label(y, m),
            faturamento=s.faturamento,
            recebido=s.recebido,
            aprovados_qty=s.aprovados_qty,
        )
        for (y, m), s in zip(yms_12, series)
    ]

    return AnaliseFinanceiroResponse(
        period=_period(year, month),
        previous=_period(py, pm),
        yoy=_period(yy, ym_yoy),
        kpis=FinanceiroKpis(
            faturamento=faturamento_kpi,
            conversao=conversao_kpi,
            ticket_medio=ticket_kpi,
            recebido=recebido_kpi,
            recebido_breakdown=recebido_breakdown,
        ),
        funil=funil,
        descontos=descontos,
        prazos=prazos,
        taxas=taxas,
        mix_pagamento=mix,
        top_profissionais=top_profs,
        top_medicos=top_meds,
        top_categorias=top_cats,
        evolution=evolution,
    )
