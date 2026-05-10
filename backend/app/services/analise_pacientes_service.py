"""
Service do dashboard /analise/pacientes (Sub-PR 20d).

Foco: retenção e oportunidade — descobrir QUEM remarcar, resgatar, fidelizar.
Pergunta-guia: "quem eu deveria estar ligando?".

Principais cuidados:
- Pacientes ativos / LTV / em_risco vêm de SNAPSHOT (dim_paciente é rebuilt
  com estado atual), então não há série histórica simples para sparkline.
  KPIs sem histórico apresentam só valor + comparativo de novos+atendidos.
- Recorrência tem histórico computável a partir de fato_agenda + dim_paciente
  (paciente é "novo" se first_seen_at no mês).
- Reusa helpers de analise_financeiro_service (period, ym, _build_kpi_card).
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analise import (
    AnalisePacientesResponse,
    CaptacaoOrigemItem,
    CaptacaoOrigemResponse,
    CurvaAbcItem,
    IndicacaoNominal,
    NovoPacienteMes,
    NovosRecorrentesSection,
    OrcamentoPendentePaciente,
    PacienteDetalhe,
    PacienteHistoricoConsulta,
    PacienteHistoricoOrcamento,
    PacienteHistoricoResponse,
    PacienteMetricas,
    PacientesEvolutionPoint,
    PacientesKpis,
    ParaResgatarPaciente,
    SaudeBaseSection,
    TopLtvPaciente,
)
from app.services.analise_financeiro_service import (
    _build_kpi_card,
    _fmt_brl_int,
    _fmt_int,
    _fmt_pct,
    _last_12_yms,
    _month_progress,
    _period,
    _prev_month,
    _yoy_month,
    _ym_key,
    _ym_short_label,
)


# ── Saúde da base (snapshot sobre dim_paciente) ─────────────────


async def _saude_base(db: AsyncSession, tenant_id: str) -> SaudeBaseSection:
    """Decompõe `dim_paciente` em 5 buckets de retenção."""
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
    pct = lambda k: round(raw.get(k, 0) / total * 100, 1)
    return SaudeBaseSection(
        total=sum(raw.values()),
        ativo_qty=raw.get("ativo", 0),
        em_risco_qty=raw.get("em_risco", 0),
        inativo_qty=raw.get("inativo", 0),
        perdido_qty=raw.get("perdido", 0),
        sem_visita_qty=raw.get("sem_visita", 0),
        ativo_pct=pct("ativo"),
        em_risco_pct=pct("em_risco"),
        inativo_pct=pct("inativo"),
        perdido_pct=pct("perdido"),
        sem_visita_pct=pct("sem_visita"),
    )


def _bucket_for(days: Optional[int]) -> str:
    if days is None:
        return "sem_visita"
    if days < 90:
        return "ativo"
    if days < 180:
        return "em_risco"
    if days < 365:
        return "inativo"
    return "perdido"


# ── Curva ABC (Pareto sobre LTV) ────────────────────────────────


async def _curva_abc(db: AsyncSession, tenant_id: str) -> List[CurvaAbcItem]:
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
            pct_pacientes=round(int(r.qtd or 0) / total_pacientes * 100, 1) if total_pacientes else 0.0,
            pct_faturamento=round(float(r.faturamento or 0) / grand_total * 100, 1),
        )
        for r in rows
    ]


# ── Novos × Recorrentes (mês selecionado) ───────────────────────


async def _novos_recorrentes(
    db: AsyncSession, tenant_id: str, ym: str,
) -> NovosRecorrentesSection:
    """Qty + R$ aprovado por grupo (novos vs já-base)."""
    q = await db.execute(
        text("""
            WITH atendidos AS (
                SELECT DISTINCT a.patient_external_id, dp.first_seen_at
                FROM fato_agenda a
                INNER JOIN dim_paciente dp
                    ON dp.tenant_id=a.tenant_id
                   AND CAST(dp.external_id AS UNSIGNED) = a.patient_external_id
                WHERE a.tenant_id=:tid
                  AND a.year_month_key=:ym
                  AND a.is_efetiva=1
                  AND a.patient_external_id IS NOT NULL
            ),
            classificados AS (
                SELECT
                    patient_external_id,
                    CASE
                        WHEN first_seen_at IS NULL THEN 'recorrente'
                        WHEN DATE_FORMAT(first_seen_at, '%Y-%m') = :ym THEN 'novo'
                        ELSE 'recorrente'
                    END AS tipo
                FROM atendidos
            ),
            aprovados_paciente AS (
                SELECT patient_external_id, SUM(amount) AS amt
                FROM fato_orcamentos
                WHERE tenant_id=:tid
                  AND year_month_key=:ym
                  AND is_approved=1
                GROUP BY patient_external_id
            )
            SELECT
                c.tipo,
                COUNT(*) AS qtd,
                COALESCE(SUM(ap.amt), 0) AS amt
            FROM classificados c
            LEFT JOIN aprovados_paciente ap
                ON ap.patient_external_id = c.patient_external_id
            GROUP BY c.tipo
        """),
        {"tid": tenant_id, "ym": ym},
    )
    rows = {r.tipo: r for r in q.all()}
    novo = rows.get("novo")
    rec = rows.get("recorrente")
    novos_qty = int(novo.qtd) if novo else 0
    rec_qty = int(rec.qtd) if rec else 0
    novos_amt = float(novo.amt or 0) if novo else 0.0
    rec_amt = float(rec.amt or 0) if rec else 0.0
    return NovosRecorrentesSection(
        total=novos_qty + rec_qty,
        novos_qty=novos_qty,
        recorrentes_qty=rec_qty,
        novos_amount_aprovado=round(novos_amt, 2),
        recorrentes_amount_aprovado=round(rec_amt, 2),
        novos_ticket_medio=round(novos_amt / novos_qty, 2) if novos_qty else 0.0,
        recorrentes_ticket_medio=round(rec_amt / rec_qty, 2) if rec_qty else 0.0,
    )


# ── Top 10 LTV (com status de retenção) ─────────────────────────


async def _top_ltv(db: AsyncSession, tenant_id: str) -> List[TopLtvPaciente]:
    """Top 10 pacientes por LTV.

    Implementado em 2 passos pra evitar GROUP BY + JOIN gigante:
    1. CTE agrega LTV por paciente em fato_financeiro (índice cobre)
    2. JOIN com dim_paciente roda só nos 10 vencedores
    """
    q = await db.execute(
        text("""
            WITH top_ltv AS (
                SELECT
                    patient_external_id AS pid,
                    SUM(amount) AS ltv,
                    COUNT(*)    AS payments
                FROM fato_financeiro
                WHERE tenant_id = :tid
                  AND is_received = 1
                  AND patient_external_id IS NOT NULL
                GROUP BY patient_external_id
                ORDER BY ltv DESC
                LIMIT 10
            )
            SELECT
                t.pid AS pid,
                dp.name AS name,
                t.ltv  AS ltv,
                t.payments AS payments,
                dp.days_since_last_seen AS days_last,
                dp.total_appointments   AS apps_total
            FROM top_ltv t
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = :tid
               AND CAST(dp.external_id AS UNSIGNED) = t.pid
            ORDER BY t.ltv DESC
        """),
        {"tid": tenant_id},
    )
    out: List[TopLtvPaciente] = []
    for r in q.all():
        days = int(r.days_last) if r.days_last is not None else None
        out.append(TopLtvPaciente(
            external_id=int(r.pid),
            name=r.name,
            ltv=float(r.ltv or 0),
            total_payments=int(r.payments or 0),
            days_since_last_seen=days,
            bucket=_bucket_for(days),
            qtd_consultas_total=int(r.apps_total or 0),
        ))
    return out


# ── Para resgatar (em risco/inativo + LTV alto) ─────────────────


async def _para_resgatar(
    db: AsyncSession, tenant_id: str, top_n: int = 15,
) -> List[ParaResgatarPaciente]:
    """Pacientes que **fechado tratamento antes** mas estão sumidos.

    Critério: `days_since_last_seen` entre 90 e 365 (em risco ou inativo)
    + tem LTV > 0. Ordena por LTV desc — alvo prioritário pra ligação.
    """
    q = await db.execute(
        text("""
            SELECT
                dp.external_id AS pid,
                dp.name,
                dp.days_since_last_seen AS days,
                dp.mobile_phone,
                COALESCE(SUM(f.amount), 0) AS ltv
            FROM dim_paciente dp
            LEFT JOIN fato_financeiro f
                ON f.tenant_id = dp.tenant_id
               AND f.patient_external_id = CAST(dp.external_id AS UNSIGNED)
               AND f.is_received = 1
            WHERE dp.tenant_id = :tid
              AND dp.days_since_last_seen IS NOT NULL
              AND dp.days_since_last_seen >= 90
              AND dp.days_since_last_seen < 365
            GROUP BY dp.external_id, dp.name, dp.days_since_last_seen, dp.mobile_phone
            HAVING ltv > 0
            ORDER BY ltv DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "lim": top_n},
    )
    return [
        ParaResgatarPaciente(
            external_id=int(r.pid),
            name=r.name,
            ltv=float(r.ltv or 0),
            days_since_last_seen=int(r.days or 0),
            bucket=_bucket_for(int(r.days)),
            mobile_phone=r.mobile_phone,
        )
        for r in q.all()
    ]


# ── Orçamentos pendentes (em decisão, últimos 60d) ──────────────


async def _orcamentos_pendentes(
    db: AsyncSession, tenant_id: str, top_n: int = 20,
) -> List[OrcamentoPendentePaciente]:
    """Top orçamentos em decisão dos últimos 60 dias.

    Status pendentes na Clinicorp = FOLLOWUP (em acompanhamento) e OPEN.
    Ordena por valor desc — prioriza maiores oportunidades.
    Janela ancorada em CURDATE — independente do filtro de mês.
    """
    q = await db.execute(
        text("""
            SELECT
                ce.external_id           AS treatment_id,
                ce.patient_external_id   AS pid,
                ce.patient_name          AS patient_name,
                ce.estimate_date         AS estimate_date,
                DATEDIFF(CURDATE(), ce.estimate_date) AS days_ago,
                ce.amount                AS amount,
                ce.status                AS status,
                ce.professional_name     AS prof_name,
                ce.patient_mobile_phone  AS mobile_phone
            FROM core_estimates ce
            WHERE ce.tenant_id = :tid
              AND ce.status IN ('FOLLOWUP', 'OPEN')
              AND ce.estimate_date >= DATE_SUB(CURDATE(), INTERVAL 60 DAY)
              AND ce.is_deleted = 0
            ORDER BY ce.amount DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "lim": top_n},
    )
    return [
        OrcamentoPendentePaciente(
            treatment_external_id=int(r.treatment_id),
            patient_external_id=int(r.pid) if r.pid else 0,
            patient_name=r.patient_name,
            professional_name=r.prof_name,
            estimate_date=r.estimate_date,
            days_ago=int(r.days_ago or 0),
            amount=float(r.amount or 0),
            status=r.status,
            mobile_phone=r.mobile_phone,
        )
        for r in q.all()
    ]


# ── Novos do mês (lista) ────────────────────────────────────────


async def _novos_do_mes(
    db: AsyncSession, tenant_id: str, ym: str, top_n: int = 20,
) -> List[NovoPacienteMes]:
    """Pacientes com first_seen_at no mês — ordenados por valor aprovado desc."""
    q = await db.execute(
        text("""
            WITH novos AS (
                SELECT dp.external_id AS pid, dp.name, dp.first_seen_at
                FROM dim_paciente dp
                WHERE dp.tenant_id = :tid
                  AND DATE_FORMAT(dp.first_seen_at, '%Y-%m') = :ym
            ),
            primeiro_prof AS (
                SELECT n.pid, MAX(prof.name) AS prof_name
                FROM novos n
                LEFT JOIN fato_agenda a
                    ON a.tenant_id = :tid
                   AND a.patient_external_id = CAST(n.pid AS UNSIGNED)
                   AND a.year_month_key = :ym
                   AND a.is_efetiva = 1
                LEFT JOIN dim_profissional prof
                    ON prof.tenant_id = :tid
                   AND CAST(prof.external_id AS UNSIGNED) = a.professional_external_id
                GROUP BY n.pid
            ),
            orc AS (
                SELECT
                    o.patient_external_id AS pid,
                    COUNT(*) AS qtd,
                    SUM(CASE WHEN o.is_approved=1 THEN 1 ELSE 0 END) AS aprov_qty,
                    SUM(CASE WHEN o.is_approved=1 THEN o.amount ELSE 0 END) AS aprov_amt
                FROM fato_orcamentos o
                WHERE o.tenant_id = :tid
                  AND o.year_month_key = :ym
                GROUP BY o.patient_external_id
            )
            SELECT
                n.pid,
                n.name,
                n.first_seen_at,
                pp.prof_name,
                COALESCE(orc.qtd, 0) AS orc_qtd,
                COALESCE(orc.aprov_qty, 0) AS orc_aprov,
                COALESCE(orc.aprov_amt, 0) AS aprov_amt
            FROM novos n
            LEFT JOIN primeiro_prof pp ON pp.pid = n.pid
            LEFT JOIN orc ON orc.pid = CAST(n.pid AS UNSIGNED)
            ORDER BY aprov_amt DESC, orc_qtd DESC, n.first_seen_at ASC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    return [
        NovoPacienteMes(
            external_id=int(r.pid),
            name=r.name,
            first_seen_at=r.first_seen_at,
            professional_name=r.prof_name,
            teve_orcamento=int(r.orc_qtd or 0) > 0,
            aprovou=int(r.orc_aprov or 0) > 0,
            valor_aprovado=float(r.aprov_amt or 0),
        )
        for r in q.all()
    ]


# ── KPIs principais ─────────────────────────────────────────────


async def _pacientes_ativos_total(db: AsyncSession, tenant_id: str) -> int:
    """Visita nos últimos 90 dias — mesmo critério do bucket "ativo" da
    saúde da base. NÃO usa `dim_paciente.is_active` porque essa flag tem
    critério mais frouxo (visita < 180d) e gera divergência entre o KPI
    (1986) e o bucket "Ativos" da saúde (1140) — confunde a leitura.
    """
    q = await db.execute(
        text("""
            SELECT COUNT(*) FROM dim_paciente
            WHERE tenant_id=:tid AND days_since_last_seen < 90
        """),
        {"tid": tenant_id},
    )
    return int(q.scalar_one() or 0)


async def _em_risco_total(db: AsyncSession, tenant_id: str) -> int:
    """Bucket 90-180d sem visita."""
    q = await db.execute(
        text("""
            SELECT COUNT(*) FROM dim_paciente
            WHERE tenant_id=:tid
              AND days_since_last_seen >= 90
              AND days_since_last_seen < 180
        """),
        {"tid": tenant_id},
    )
    return int(q.scalar_one() or 0)


async def _ltv_medio(db: AsyncSession, tenant_id: str) -> float:
    """Média do LTV entre pacientes que têm pelo menos 1 pagamento recebido."""
    q = await db.execute(
        text("""
            SELECT AVG(ltv) AS media FROM (
                SELECT SUM(amount) AS ltv
                FROM fato_financeiro
                WHERE tenant_id=:tid AND is_received=1 AND patient_external_id IS NOT NULL
                GROUP BY patient_external_id
                HAVING ltv > 0
            ) t
        """),
        {"tid": tenant_id},
    )
    v = q.scalar_one_or_none()
    return float(v) if v is not None else 0.0


async def _recorrencia_series_12m(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> List[float]:
    """Taxa de recorrência (% atendidos no mês que já eram base) por mês.

    Recorrência_M = pacientes_atendidos_M com first_seen_at < início_M /
                    pacientes_atendidos_M
    """
    yms = _last_12_yms(year, month)
    keys = [_ym_key(y, m) for y, m in yms]
    q = await db.execute(
        text("""
            SELECT
                a.year_month_key AS ym,
                COUNT(DISTINCT a.patient_external_id) AS atendidos,
                COUNT(DISTINCT CASE
                    WHEN dp.first_seen_at < STR_TO_DATE(CONCAT(a.year_month_key, '-01'), '%Y-%m-%d')
                    THEN a.patient_external_id END) AS recorrentes
            FROM fato_agenda a
            INNER JOIN dim_paciente dp
                ON dp.tenant_id = a.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = a.patient_external_id
            WHERE a.tenant_id = :tid
              AND a.year_month_key IN :keys
              AND a.is_efetiva = 1
              AND a.patient_external_id IS NOT NULL
            GROUP BY a.year_month_key
        """),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    by_ym = {r.ym: (int(r.recorrentes or 0), int(r.atendidos or 0)) for r in q.all()}
    out: List[float] = []
    for ym in keys:
        rec, atend = by_ym.get(ym, (0, 0))
        out.append(round(rec / atend * 100, 1) if atend else 0.0)
    return out


async def _build_kpis(
    db: AsyncSession, tenant_id: str, year: int, month: int,
    progress: Optional[float],
) -> PacientesKpis:
    ativos = await _pacientes_ativos_total(db, tenant_id)
    em_risco = await _em_risco_total(db, tenant_id)
    ltv_avg = await _ltv_medio(db, tenant_id)
    rec_series = await _recorrencia_series_12m(db, tenant_id, year, month)
    rec_now = rec_series[-1] if rec_series else 0.0

    # Pacientes ativos / em_risco / LTV médio são SNAPSHOT (não há histórico
    # mês-a-mês simples — dim_paciente é rebuilt com estado atual). Sparkline
    # vazia / sem MoM. Aceitar por enquanto — evolução fica como Sub-PR futuro.
    pacientes_ativos_kpi = _build_kpi_card(
        value=ativos,
        value_label=_fmt_int(ativos),
        series_12m=[],
        partial_progress=progress,
        year=year, month=month,
    )
    em_risco_kpi = _build_kpi_card(
        value=em_risco,
        value_label=_fmt_int(em_risco),
        series_12m=[],
        is_inverse=True,
        partial_progress=progress,
        year=year, month=month,
    )
    ltv_kpi = _build_kpi_card(
        value=ltv_avg,
        value_label=_fmt_brl_int(ltv_avg),
        series_12m=[],
        partial_progress=progress,
        year=year, month=month,
    )
    recorrencia_kpi = _build_kpi_card(
        value=rec_now,
        value_label=_fmt_pct(rec_now),
        series_12m=rec_series,
        partial_progress=progress,
        year=year, month=month,
    )
    return PacientesKpis(
        pacientes_ativos=pacientes_ativos_kpi,
        taxa_recorrencia_pct=recorrencia_kpi,
        ltv_medio=ltv_kpi,
        em_risco_qty=em_risco_kpi,
    )


# ── Evolution chart (12m novos vs recorrentes) ──────────────────


async def _evolution_12m(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> List[PacientesEvolutionPoint]:
    yms = _last_12_yms(year, month)
    keys = [_ym_key(y, m) for y, m in yms]
    q = await db.execute(
        text("""
            SELECT
                a.year_month_key AS ym,
                COUNT(DISTINCT CASE
                    WHEN DATE_FORMAT(dp.first_seen_at, '%Y-%m') = a.year_month_key
                    THEN a.patient_external_id END) AS novos,
                COUNT(DISTINCT CASE
                    WHEN dp.first_seen_at < STR_TO_DATE(CONCAT(a.year_month_key, '-01'), '%Y-%m-%d')
                    THEN a.patient_external_id END) AS recorrentes
            FROM fato_agenda a
            INNER JOIN dim_paciente dp
                ON dp.tenant_id = a.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = a.patient_external_id
            WHERE a.tenant_id = :tid
              AND a.year_month_key IN :keys
              AND a.is_efetiva = 1
              AND a.patient_external_id IS NOT NULL
            GROUP BY a.year_month_key
        """),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    by_ym = {r.ym: (int(r.novos or 0), int(r.recorrentes or 0)) for r in q.all()}
    out: List[PacientesEvolutionPoint] = []
    for (y, m), key in zip(yms, keys):
        novos, rec = by_ym.get(key, (0, 0))
        out.append(PacientesEvolutionPoint(
            year_month_key=key,
            label=_ym_short_label(y, m),
            novos=novos,
            recorrentes=rec,
        ))
    return out


# ── API pública ─────────────────────────────────────────────────


async def get_analise_pacientes(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> AnalisePacientesResponse:
    """Builder principal — orquestra todas as queries do dashboard pacientes."""
    ym = _ym_key(year, month)
    py, pm = _prev_month(year, month)
    yy, ym_yoy = _yoy_month(year, month)
    progress = _month_progress(year, month)

    kpis = await _build_kpis(db, tenant_id, year, month, progress)
    saude = await _saude_base(db, tenant_id)
    abc = await _curva_abc(db, tenant_id)
    nov_rec = await _novos_recorrentes(db, tenant_id, ym)
    top_ltv = await _top_ltv(db, tenant_id)
    resgatar = await _para_resgatar(db, tenant_id)
    pendentes = await _orcamentos_pendentes(db, tenant_id)
    novos = await _novos_do_mes(db, tenant_id, ym)
    evolution = await _evolution_12m(db, tenant_id, year, month)

    return AnalisePacientesResponse(
        period=_period(year, month),
        previous=_period(py, pm),
        yoy=_period(yy, ym_yoy),
        kpis=kpis,
        saude_base=saude,
        curva_abc=abc,
        novos_recorrentes=nov_rec,
        top_ltv=top_ltv,
        para_resgatar=resgatar,
        orcamentos_pendentes=pendentes,
        novos_do_mes=novos,
        evolution=evolution,
    )


# ── Histórico de paciente (drawer drill-down) ───────────────────


async def get_paciente_historico(
    db: AsyncSession, tenant_id: str, patient_external_id: int,
) -> Optional[PacienteHistoricoResponse]:
    """Retorna detalhes + histórico (top 20 consultas + top 10 orçamentos)
    de um paciente específico — usado pelo drawer de drill-down.

    Retorna None se o paciente não existir no tenant.
    """
    # 1) Cabeçalho a partir de dim_paciente
    pac_q = await db.execute(
        text("""
            SELECT
                external_id, name, mobile_phone, email, gender, birth_date,
                first_seen_at, last_seen_at, days_since_last_seen,
                total_appointments, total_estimates, total_payments
            FROM dim_paciente
            WHERE tenant_id = :tid AND CAST(external_id AS UNSIGNED) = :pid
            LIMIT 1
        """),
        {"tid": tenant_id, "pid": patient_external_id},
    )
    pac_row = pac_q.first()
    if pac_row is None:
        return None

    days = int(pac_row.days_since_last_seen) if pac_row.days_since_last_seen is not None else None
    bucket = _bucket_for(days)

    # Idade calculada se birth_date estiver preenchido
    age: Optional[int] = None
    if pac_row.birth_date:
        from datetime import date as _date
        today_d = _date.today()
        age = today_d.year - pac_row.birth_date.year - (
            (today_d.month, today_d.day) < (pac_row.birth_date.month, pac_row.birth_date.day)
        )

    # 2) Métricas (LTV + qtd_efetivas + qtd_aprovados + valor pendente)
    metr_q = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(amount), 0) AS ltv
            FROM fato_financeiro
            WHERE tenant_id = :tid
              AND patient_external_id = :pid
              AND is_received = 1
        """),
        {"tid": tenant_id, "pid": patient_external_id},
    )
    ltv = float(metr_q.scalar() or 0)

    efet_q = await db.execute(
        text("""
            SELECT COUNT(*) FROM fato_agenda
            WHERE tenant_id = :tid AND patient_external_id = :pid AND is_efetiva = 1
        """),
        {"tid": tenant_id, "pid": patient_external_id},
    )
    qtd_efet = int(efet_q.scalar() or 0)

    orc_q = await db.execute(
        text("""
            SELECT
                SUM(CASE WHEN status='APPROVED' THEN 1 ELSE 0 END) AS aprov_qty,
                SUM(CASE WHEN status='APPROVED' THEN amount ELSE 0 END) AS aprov_amount,
                SUM(CASE WHEN status IN ('FOLLOWUP','OPEN') THEN amount ELSE 0 END) AS pend_amount
            FROM core_estimates
            WHERE tenant_id = :tid AND patient_external_id = :pid AND is_deleted = 0
        """),
        {"tid": tenant_id, "pid": patient_external_id},
    )
    orc_row = orc_q.one()
    aprov_qty = int(orc_row.aprov_qty or 0)
    aprov_amount = float(orc_row.aprov_amount or 0)
    pend_amount = float(orc_row.pend_amount or 0)

    # 3) Histórico de consultas (top 20 desc)
    cons_q = await db.execute(
        text("""
            SELECT
                a.external_id,
                a.appointment_datetime AS dt,
                p.name                 AS prof_name,
                a.category_description AS category,
                a.is_efetiva, a.is_falta, a.is_canceled, a.is_indefinida
            FROM fato_agenda a
            LEFT JOIN dim_profissional p
                ON p.tenant_id = a.tenant_id
               AND CAST(p.external_id AS UNSIGNED) = a.professional_external_id
            WHERE a.tenant_id = :tid AND a.patient_external_id = :pid
            ORDER BY a.appointment_datetime DESC
            LIMIT 20
        """),
        {"tid": tenant_id, "pid": patient_external_id},
    )
    consultas: List[PacienteHistoricoConsulta] = []
    for r in cons_q.all():
        if r.is_efetiva:
            desfecho = "efetiva"
        elif r.is_falta:
            desfecho = "falta"
        elif r.is_canceled:
            desfecho = "cancelada"
        elif r.is_indefinida:
            desfecho = "indefinida"
        else:
            desfecho = "outro"
        consultas.append(PacienteHistoricoConsulta(
            appointment_external_id=int(r.external_id),
            date=r.dt,
            professional_name=r.prof_name,
            category=r.category,
            desfecho=desfecho,
        ))

    # 4) Histórico de orçamentos (top 10 desc)
    orc_hist_q = await db.execute(
        text("""
            SELECT
                external_id, estimate_date, professional_name, amount, status
            FROM core_estimates
            WHERE tenant_id = :tid AND patient_external_id = :pid AND is_deleted = 0
            ORDER BY estimate_date DESC
            LIMIT 10
        """),
        {"tid": tenant_id, "pid": patient_external_id},
    )
    orcamentos: List[PacienteHistoricoOrcamento] = [
        PacienteHistoricoOrcamento(
            treatment_external_id=int(r.external_id),
            estimate_date=r.estimate_date,
            professional_name=r.professional_name,
            amount=float(r.amount or 0),
            status=r.status,
        )
        for r in orc_hist_q.all()
    ]

    paciente = PacienteDetalhe(
        external_id=int(pac_row.external_id),
        name=pac_row.name,
        mobile_phone=pac_row.mobile_phone,
        email=pac_row.email,
        gender=pac_row.gender,
        birth_date=pac_row.birth_date,
        age=age,
        bucket=bucket,
        days_since_last_seen=days,
        first_seen_at=pac_row.first_seen_at,
        last_seen_at=pac_row.last_seen_at,
    )
    metricas = PacienteMetricas(
        ltv=ltv,
        qtd_consultas=int(pac_row.total_appointments or 0),
        qtd_consultas_efetivas=qtd_efet,
        qtd_orcamentos=int(pac_row.total_estimates or 0),
        qtd_orcamentos_aprovados=aprov_qty,
        qtd_pagamentos=int(pac_row.total_payments or 0),
        ticket_medio_orcamento=round(aprov_amount / aprov_qty, 2) if aprov_qty else 0.0,
        valor_orcado_pendente=round(pend_amount, 2),
    )
    return PacienteHistoricoResponse(
        paciente=paciente,
        metricas=metricas,
        consultas=consultas,
        orcamentos=orcamentos,
    )


# ── Captação & Origem (Frente A — HowDidMeet) ───────────────────


def _normaliza_canal(raw: str) -> str:
    """Agrupa variações textuais em buckets consistentes (Facebook, Instagram, Google, Indicação, Outros)."""
    if not raw:
        return "Outros"
    s = raw.strip().lower()
    if not s or s in ("...", "-", "n/a", "na"):
        return "Outros"
    if "face" in s or "fb" == s:
        return "Facebook"
    if "insta" in s or "ig" == s:
        return "Instagram"
    if "google" in s or "search" in s or "pesquis" in s:
        return "Google"
    if "indica" in s or "amigo" in s or "boca" in s:
        return "Indicação"
    if "outro" in s:
        return "Outros"
    return raw.strip()


async def get_captacao_origem(
    db: AsyncSession, tenant_id: str,
) -> CaptacaoOrigemResponse:
    """Distribuição de canais de captação (HowDidMeet) — vida toda da clínica.

    Sem filtro temporal porque preenchimento é raro (~0,1% em Parente).
    """
    # 1) Total e preenchidos
    base_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN how_did_meet IS NOT NULL AND how_did_meet != ''
                         THEN 1 ELSE 0 END) AS com_origem
            FROM core_appointments
            WHERE tenant_id = :tid AND is_deleted = 0
        """),
        {"tid": tenant_id},
    )
    base = base_q.one()
    total = int(base.total or 0)
    com_origem = int(base.com_origem or 0)
    pct_preenchimento = (com_origem / total * 100) if total else 0.0

    # 2) Distribuição por canal (com normalização)
    can_q = await db.execute(
        text("""
            SELECT
                how_did_meet                       AS raw_canal,
                COUNT(*)                           AS qtd,
                COUNT(DISTINCT patient_external_id) AS qtd_pac
            FROM core_appointments
            WHERE tenant_id = :tid AND is_deleted = 0
              AND how_did_meet IS NOT NULL AND how_did_meet != ''
            GROUP BY how_did_meet
        """),
        {"tid": tenant_id},
    )
    # Agrupa por canal normalizado
    grupos: dict[str, dict] = {}
    for r in can_q.all():
        canal = _normaliza_canal(r.raw_canal)
        g = grupos.setdefault(canal, {"qtd": 0, "qtd_pac_set": set()})
        g["qtd"] += int(r.qtd or 0)
        # Aproximação: somamos pacientes distintos por bucket bruto.
        # Se o mesmo paciente aparece em 2 buckets normalizados iguais, conta 2x.
        # Erro tolerável dada a raridade (22 linhas em Parente).
        g["qtd_pac_set"].add((r.raw_canal, int(r.qtd_pac or 0)))

    canais: List[CaptacaoOrigemItem] = []
    for canal, g in grupos.items():
        qtd_pac = sum(p[1] for p in g["qtd_pac_set"])
        canais.append(CaptacaoOrigemItem(
            canal=canal,
            qtd_consultas=g["qtd"],
            qtd_pacientes=qtd_pac,
            pct=round(g["qtd"] / com_origem * 100, 1) if com_origem else 0.0,
        ))
    canais.sort(key=lambda c: c.qtd_consultas, reverse=True)

    # 3) Indicações nominais (IndicationSource agrupado por nome)
    ind_q = await db.execute(
        text("""
            SELECT
                indication_source                   AS nome,
                COUNT(*)                            AS qtd,
                COUNT(DISTINCT patient_external_id) AS qtd_pac
            FROM core_appointments
            WHERE tenant_id = :tid AND is_deleted = 0
              AND indication_source IS NOT NULL AND indication_source != ''
            GROUP BY indication_source
            ORDER BY qtd DESC
            LIMIT 15
        """),
        {"tid": tenant_id},
    )
    indicacoes: List[IndicacaoNominal] = [
        IndicacaoNominal(
            nome_indicador=r.nome.strip(),
            qtd_consultas=int(r.qtd or 0),
            qtd_pacientes=int(r.qtd_pac or 0),
        )
        for r in ind_q.all()
    ]

    return CaptacaoOrigemResponse(
        total_consultas=total,
        total_com_origem=com_origem,
        pct_preenchimento=round(pct_preenchimento, 2),
        canais=canais,
        indicacoes_nominais=indicacoes,
    )
