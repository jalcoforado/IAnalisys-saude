"""
Service do dashboard /analise/comercial (Sub-PR 20c).

Foco: relatório operacional para o DONO, perspectiva de VOLUME e EFICIÊNCIA.
- Consultas executadas no mês (`fato_agenda` is_canceled=0)
- Funil consulta → orçamento → aprovação (cruza fato_agenda × fato_orcamentos)
- Top procedimentos executados (core_estimate_procedures.executed=1)
- Top especialidades em demanda (core_specialties via specialty_id)
- Top profissionais por VOLUME de consultas (não por R$ — esse fica no financeiro)
- Mix de categorias de consulta + operacional (encaixe, retorno pendente, perdas)

Reutiliza helpers genéricos do analise_financeiro_service.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.analise import (
    AnaliseComercialResponse,
    ComercialEvolutionPoint,
    ComercialKpis,
    ConversaoBreakdown,
    FunilComercial,
    KpiCard,
    MixCategoriaConsulta,
    OperacionalComercial,
    SaudeAgendaSection,
    TopEspecialidadeDemanda,
    TopProcedimentoExecutado,
    TopProfissionalConsultas,
)
from app.services.analise_financeiro_service import (
    _build_kpi_card,
    _delta_pct,
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


# ── Aggregate enxuto pra 1 mês ──────────────────────────────────


@dataclass
class _ComercialAgg:
    """Agregação de 1 mês — só o que comercial precisa.

    Decomposição da agenda (universo `consultas_total`):
      consultas_efetivas (CHECKOUT) + consultas_faltas (MISSED) +
      consultas_indefinidas (NULL não-cancelado) + consultas_canceladas (is_canceled=1)
      + outros statuses não-cancelados (CONFIRMED, ARRIVED, IN_SESSION, LATE, CALL).

    `consultas_efetivas` é a base correta para top procedimentos / médicos /
    especialidades / mix — são consultas em que o paciente foi atendido.
    """
    consultas_total: int                    # todos agendamentos
    consultas_efetivas: int                 # is_efetiva=1 (CHECKOUT — base p/ tops)
    consultas_faltas: int                   # is_falta=1 (MISSED — absenteísmo real)
    consultas_canceladas: int               # is_canceled=1
    consultas_indefinidas: int              # is_indefinida=1 (status NULL não-cancelado)
    pacientes_unicos: int                   # distintos no mês (qualquer status)
    pacientes_unicos_efetivos: int          # distintos com is_efetiva=1
    pacientes_efetivos_com_aprovado: int    # subconjunto de efetivos que tiveram orçamento aprovado no mês
    profs_distintos: int
    encaixe_qty: int
    retorno_pendente_qty: int
    remarcar_qty: int
    # Cruzados com financeiro (orçamentos do mesmo mês)
    aprovados_qty: int                      # COUNT DISTINCT orçamentos aprovados no mês
    aprovados_amount: float
    # Recebido (pra ticket médio por consulta)
    recebido: float


async def _aggregate_month(
    db: AsyncSession, tenant_id: str, ym: str,
) -> _ComercialAgg:
    """3 queries: agenda, orçamentos aprovados, financeiro."""
    ag_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                SUM(is_efetiva)        AS efetivas,
                SUM(is_falta)          AS faltas,
                SUM(is_canceled)       AS canceladas,
                SUM(is_indefinida)     AS indefinidas,
                COUNT(DISTINCT patient_external_id) AS pac,
                COUNT(DISTINCT CASE WHEN is_efetiva=1 THEN patient_external_id END) AS pac_efetivos,
                COUNT(DISTINCT professional_external_id) AS profs,
                SUM(CASE WHEN has_encaixe=1 THEN 1 ELSE 0 END) AS encaixe,
                SUM(CASE WHEN has_retorno_pendente=1 THEN 1 ELSE 0 END) AS retorno_p,
                SUM(CASE WHEN has_remarcar=1 THEN 1 ELSE 0 END) AS remarcar
            FROM fato_agenda
            WHERE tenant_id=:tid AND year_month_key=:ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    ag = ag_q.one()

    orc_q = await db.execute(
        text("""
            SELECT
                COUNT(*) AS aprov_qty,
                COALESCE(SUM(amount), 0) AS aprov_amt
            FROM fato_orcamentos
            WHERE tenant_id=:tid AND year_month_key=:ym AND is_approved=1
        """),
        {"tid": tenant_id, "ym": ym},
    )
    orc = orc_q.one()

    fin_q = await db.execute(
        text("""
            SELECT COALESCE(SUM(CASE WHEN is_received=1 THEN amount ELSE 0 END), 0) AS recebido
            FROM fato_financeiro
            WHERE tenant_id=:tid AND year_month_key=:ym
        """),
        {"tid": tenant_id, "ym": ym},
    )
    recebido = float(fin_q.scalar_one() or 0)

    # Conversão correta = paciente que ATENDEU consulta E fechou orçamento no mês.
    # Contagem por PACIENTE (cardinalidade igual no num e denom) — diferente do
    # cálculo errado anterior que dividia orçamentos por consultas.
    conv_q = await db.execute(
        text("""
            SELECT COUNT(DISTINCT a.patient_external_id) AS qtd
            FROM fato_agenda a
            INNER JOIN fato_orcamentos o
                ON o.tenant_id=a.tenant_id
               AND o.year_month_key=a.year_month_key
               AND o.patient_external_id=a.patient_external_id
               AND o.is_approved=1
            WHERE a.tenant_id=:tid AND a.year_month_key=:ym
              AND a.is_efetiva=1 AND a.patient_external_id IS NOT NULL
        """),
        {"tid": tenant_id, "ym": ym},
    )
    pac_aprov = int(conv_q.scalar_one() or 0)

    return _ComercialAgg(
        consultas_total=int(ag.total or 0),
        consultas_efetivas=int(ag.efetivas or 0),
        consultas_faltas=int(ag.faltas or 0),
        consultas_canceladas=int(ag.canceladas or 0),
        consultas_indefinidas=int(ag.indefinidas or 0),
        pacientes_unicos=int(ag.pac or 0),
        pacientes_unicos_efetivos=int(ag.pac_efetivos or 0),
        pacientes_efetivos_com_aprovado=pac_aprov,
        profs_distintos=int(ag.profs or 0),
        encaixe_qty=int(ag.encaixe or 0),
        retorno_pendente_qty=int(ag.retorno_p or 0),
        remarcar_qty=int(ag.remarcar or 0),
        aprovados_qty=int(orc.aprov_qty or 0),
        aprovados_amount=float(orc.aprov_amt or 0),
        recebido=recebido,
    )


async def _aggregate_last_12(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> List[_ComercialAgg]:
    """Agrega 12 últimos meses — 3 queries batch."""
    yms = _last_12_yms(year, month)
    keys = [_ym_key(y, m) for y, m in yms]

    ag_q = await db.execute(
        text("""
            SELECT
                year_month_key,
                COUNT(*) AS total,
                SUM(is_efetiva)        AS efetivas,
                SUM(is_falta)          AS faltas,
                SUM(is_canceled)       AS canceladas,
                SUM(is_indefinida)     AS indefinidas,
                COUNT(DISTINCT patient_external_id) AS pac,
                COUNT(DISTINCT CASE WHEN is_efetiva=1 THEN patient_external_id END) AS pac_efetivos,
                COUNT(DISTINCT professional_external_id) AS profs,
                SUM(CASE WHEN has_encaixe=1 THEN 1 ELSE 0 END) AS encaixe,
                SUM(CASE WHEN has_retorno_pendente=1 THEN 1 ELSE 0 END) AS retorno_p,
                SUM(CASE WHEN has_remarcar=1 THEN 1 ELSE 0 END) AS remarcar
            FROM fato_agenda
            WHERE tenant_id=:tid AND year_month_key IN :keys
            GROUP BY year_month_key
        """),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    ag_by_ym = {r.year_month_key: r for r in ag_q.all()}

    orc_q = await db.execute(
        text("""
            SELECT
                year_month_key,
                COUNT(*) AS aprov_qty,
                COALESCE(SUM(amount), 0) AS aprov_amt
            FROM fato_orcamentos
            WHERE tenant_id=:tid AND year_month_key IN :keys AND is_approved=1
            GROUP BY year_month_key
        """),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    orc_by_ym = {r.year_month_key: r for r in orc_q.all()}

    fin_q = await db.execute(
        text("""
            SELECT
                year_month_key,
                COALESCE(SUM(CASE WHEN is_received=1 THEN amount ELSE 0 END), 0) AS recebido
            FROM fato_financeiro
            WHERE tenant_id=:tid AND year_month_key IN :keys
            GROUP BY year_month_key
        """),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    fin_by_ym = {r.year_month_key: float(r.recebido or 0) for r in fin_q.all()}

    # Conversão correta por mês (pacientes que atenderam E aprovaram orçamento)
    conv_q = await db.execute(
        text("""
            SELECT a.year_month_key, COUNT(DISTINCT a.patient_external_id) AS qtd
            FROM fato_agenda a
            INNER JOIN fato_orcamentos o
                ON o.tenant_id=a.tenant_id
               AND o.year_month_key=a.year_month_key
               AND o.patient_external_id=a.patient_external_id
               AND o.is_approved=1
            WHERE a.tenant_id=:tid AND a.year_month_key IN :keys
              AND a.is_efetiva=1 AND a.patient_external_id IS NOT NULL
            GROUP BY a.year_month_key
        """),
        {"tid": tenant_id, "keys": tuple(keys)},
    )
    conv_by_ym = {r.year_month_key: int(r.qtd or 0) for r in conv_q.all()}

    out: List[_ComercialAgg] = []
    for ym in keys:
        ag = ag_by_ym.get(ym)
        orc = orc_by_ym.get(ym)
        out.append(_ComercialAgg(
            consultas_total=int(ag.total) if ag else 0,
            consultas_efetivas=int(ag.efetivas) if ag else 0,
            consultas_faltas=int(ag.faltas) if ag else 0,
            consultas_canceladas=int(ag.canceladas) if ag else 0,
            consultas_indefinidas=int(ag.indefinidas) if ag else 0,
            pacientes_unicos=int(ag.pac) if ag else 0,
            pacientes_unicos_efetivos=int(ag.pac_efetivos) if ag else 0,
            pacientes_efetivos_com_aprovado=conv_by_ym.get(ym, 0),
            profs_distintos=int(ag.profs) if ag else 0,
            encaixe_qty=int(ag.encaixe) if ag else 0,
            retorno_pendente_qty=int(ag.retorno_p) if ag else 0,
            remarcar_qty=int(ag.remarcar) if ag else 0,
            aprovados_qty=int(orc.aprov_qty) if orc else 0,
            aprovados_amount=float(orc.aprov_amt) if orc else 0.0,
            recebido=fin_by_ym.get(ym, 0.0),
        ))
    return out


# ── Funil consulta → orçamento → aprovação ──────────────────────


async def _funil_comercial(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str,
) -> FunilComercial:
    """Funil paciente atendido → com orçamento → aprovado.

    Os 3 níveis são contados por PACIENTE distinto (não por evento de consulta).
    `total_consultas` (eventos) volta junto só pra exibir como contexto de
    volume — "X consultas em Y pacientes" — mas não entra em nenhum %.

    Conversão total = aprovados ÷ pacientes_atendidos = mesmo cálculo do KPI
    "Conversão em orçamento" (sem mistura de cardinalidades).
    """
    cur_q = await db.execute(
        text("""
            WITH atendidos AS (
                SELECT DISTINCT patient_external_id
                FROM fato_agenda
                WHERE tenant_id=:tid AND year_month_key=:ym
                  AND is_efetiva=1 AND patient_external_id IS NOT NULL
            )
            SELECT
                (SELECT COUNT(*) FROM atendidos) AS pac_atend,
                (SELECT COUNT(*) FROM fato_agenda
                 WHERE tenant_id=:tid AND year_month_key=:ym AND is_efetiva=1) AS total_cons,
                (SELECT COUNT(DISTINCT a.patient_external_id) FROM atendidos a
                 INNER JOIN fato_orcamentos o
                   ON o.tenant_id=:tid AND o.year_month_key=:ym
                  AND o.patient_external_id = a.patient_external_id
                ) AS com_orc,
                (SELECT COUNT(DISTINCT a.patient_external_id) FROM atendidos a
                 INNER JOIN fato_orcamentos o
                   ON o.tenant_id=:tid AND o.year_month_key=:ym
                  AND o.patient_external_id = a.patient_external_id
                  AND o.is_approved=1
                ) AS aprov_pac,
                (SELECT COALESCE(SUM(o.amount), 0) FROM atendidos a
                 INNER JOIN fato_orcamentos o
                   ON o.tenant_id=:tid AND o.year_month_key=:ym
                  AND o.patient_external_id = a.patient_external_id
                  AND o.is_approved=1
                ) AS aprov_amt
        """),
        {"tid": tenant_id, "ym": ym},
    )
    r = cur_q.one()
    pac_atend = int(r.pac_atend or 0)
    total_cons = int(r.total_cons or 0)
    com_orc = int(r.com_orc or 0)
    aprov = int(r.aprov_pac or 0)
    aprov_amt = float(r.aprov_amt or 0)

    # Mês anterior — só pra MoM das taxas (oferta e aprovação).
    prev_q = await db.execute(
        text("""
            WITH atendidos AS (
                SELECT DISTINCT patient_external_id
                FROM fato_agenda
                WHERE tenant_id=:tid AND year_month_key=:ym
                  AND is_efetiva=1 AND patient_external_id IS NOT NULL
            )
            SELECT
                (SELECT COUNT(*) FROM atendidos) AS pac_atend,
                (SELECT COUNT(DISTINCT a.patient_external_id) FROM atendidos a
                 INNER JOIN fato_orcamentos o
                   ON o.tenant_id=:tid AND o.year_month_key=:ym
                  AND o.patient_external_id = a.patient_external_id
                ) AS com_orc,
                (SELECT COUNT(DISTINCT a.patient_external_id) FROM atendidos a
                 INNER JOIN fato_orcamentos o
                   ON o.tenant_id=:tid AND o.year_month_key=:ym
                  AND o.patient_external_id = a.patient_external_id
                  AND o.is_approved=1
                ) AS aprov_pac
        """),
        {"tid": tenant_id, "ym": ym_prev},
    )
    rp = prev_q.one()
    prev_pac = int(rp.pac_atend or 0)
    prev_com_orc = int(rp.com_orc or 0)
    prev_aprov = int(rp.aprov_pac or 0)

    taxa_oferta = (com_orc / pac_atend * 100) if pac_atend else 0.0
    taxa_aprov = (aprov / com_orc * 100) if com_orc else 0.0
    taxa_total = (aprov / pac_atend * 100) if pac_atend else 0.0
    taxa_oferta_prev = (prev_com_orc / prev_pac * 100) if prev_pac else None
    taxa_aprov_prev = (prev_aprov / prev_com_orc * 100) if prev_com_orc else None

    # Tempo médio consulta → aprovação (proxy: external_updated_at do orçamento aprovado).
    # Usa MIN em ambos os lados: primeira consulta do paciente vs primeira aprovação.
    tempo_q = await db.execute(
        text("""
            SELECT AVG(diff) AS tempo_medio FROM (
                SELECT TIMESTAMPDIFF(DAY, MIN(a.appointment_datetime), MIN(e.external_updated_at)) AS diff
                FROM fato_agenda a
                INNER JOIN fato_orcamentos o
                    ON o.tenant_id=a.tenant_id AND o.year_month_key=a.year_month_key
                   AND o.patient_external_id = a.patient_external_id
                   AND o.is_approved=1
                INNER JOIN core_estimates e
                    ON e.tenant_id=o.tenant_id
                   AND CAST(e.external_id AS UNSIGNED) = o.external_id
                WHERE a.tenant_id=:tid AND a.year_month_key=:ym
                  AND a.is_efetiva=1 AND a.appointment_datetime IS NOT NULL
                  AND e.external_updated_at IS NOT NULL
                GROUP BY a.patient_external_id
                HAVING diff >= 0 AND diff <= 90
            ) AS t
        """),
        {"tid": tenant_id, "ym": ym},
    )
    tempo_row = tempo_q.scalar_one_or_none()
    tempo_medio = round(float(tempo_row), 1) if tempo_row is not None else None

    return FunilComercial(
        pacientes_atendidos=pac_atend,
        total_consultas=total_cons,
        com_orcamento_qty=com_orc,
        aprovados_qty=aprov,
        aprovados_amount=round(aprov_amt, 2),
        taxa_oferta_pct=round(taxa_oferta, 1),
        taxa_aprovacao_pct=round(taxa_aprov, 1),
        taxa_conversao_total_pct=round(taxa_total, 1),
        tempo_medio_consulta_aprov_dias=tempo_medio,
        taxa_oferta_mom_pct=_delta_pct(taxa_oferta, taxa_oferta_prev) if taxa_oferta_prev else None,
        taxa_aprovacao_mom_pct=_delta_pct(taxa_aprov, taxa_aprov_prev) if taxa_aprov_prev else None,
    )


# ── Top procedimentos executados ────────────────────────────────


async def _top_procedimentos(
    db: AsyncSession, tenant_id: str, ym: str, top_n: int = 10,
) -> List[TopProcedimentoExecutado]:
    """Procedimentos executados (executed=1) no mês, agrupados por nome.

    Usa `core_estimate_procedures.created_external_at` ou `external_updated_at`
    pra filtrar pelo mês — preferimos `external_updated_at` (atualizado quando
    é marcado como executado).
    """
    q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(operation_description, ''), 'Sem descrição') AS nome,
                COUNT(*) AS qtd,
                COALESCE(SUM(COALESCE(final_amount, amount, 0)), 0) AS fat
            FROM core_estimate_procedures
            WHERE tenant_id=:tid AND is_deleted=0 AND executed=1
              AND DATE_FORMAT(external_updated_at, '%Y-%m') = :ym
            GROUP BY nome
            ORDER BY qtd DESC, fat DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    rows = q.all()
    if not rows:
        return []
    total_qtd = sum(int(r.qtd or 0) for r in rows) or 1

    out: List[TopProcedimentoExecutado] = []
    for r in rows:
        qtd = int(r.qtd or 0)
        fat = float(r.fat or 0)
        out.append(TopProcedimentoExecutado(
            procedure_name=r.nome,
            qtd_executados=qtd,
            faturamento=round(fat, 2),
            pct_volume=round(qtd / total_qtd * 100, 1),
            ticket_medio=round(fat / qtd, 2) if qtd else 0.0,
        ))
    return out


# ── Top especialidades em demanda ───────────────────────────────


async def _top_especialidades(
    db: AsyncSession, tenant_id: str, ym: str, top_n: int = 8,
) -> List[TopEspecialidadeDemanda]:
    """Especialidades por volume de procedimentos (executados ou orçados aprovados)."""
    q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(s.description, ''), 'Sem categoria') AS especialidade,
                COUNT(*) AS qtd,
                COALESCE(SUM(COALESCE(ep.final_amount, ep.amount, 0)), 0) AS fat
            FROM core_estimate_procedures ep
            INNER JOIN fato_orcamentos o
                ON o.tenant_id = ep.tenant_id
               AND ep.treatment_external_id = CAST(o.external_id AS UNSIGNED)
            LEFT JOIN core_specialties s
                ON s.tenant_id = ep.tenant_id
               AND CAST(s.external_id AS UNSIGNED) = ep.specialty_id
            WHERE o.tenant_id=:tid AND o.year_month_key=:ym
              AND o.is_approved=1 AND ep.is_deleted=0
            GROUP BY especialidade
            ORDER BY qtd DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    rows = q.all()
    if not rows:
        return []
    total_qtd = sum(int(r.qtd or 0) for r in rows) or 1

    out: List[TopEspecialidadeDemanda] = []
    for r in rows:
        qtd = int(r.qtd or 0)
        out.append(TopEspecialidadeDemanda(
            especialidade=r.especialidade,
            qtd_procedimentos=qtd,
            pct_volume=round(qtd / total_qtd * 100, 1),
            faturamento=round(float(r.fat or 0), 2),
        ))
    return out


# ── Top profissionais por volume de consultas ───────────────────


async def _top_profs_consultas(
    db: AsyncSession, tenant_id: str, ym: str,
    consultas_total_clinica: int, top_n: int = 8,
) -> List[TopProfissionalConsultas]:
    """Profissionais ranqueados por volume de consultas executadas no mês."""
    q = await db.execute(
        text("""
            SELECT
                a.professional_external_id AS pid,
                MAX(p.name) AS nome,
                SUM(a.is_efetiva) AS executadas,
                SUM(a.is_falta)   AS faltas,
                SUM(a.is_canceled) AS canceladas,
                COUNT(DISTINCT CASE WHEN a.is_efetiva=1 THEN a.patient_external_id END) AS pacientes
            FROM fato_agenda a
            LEFT JOIN dim_profissional p
                ON p.tenant_id = a.tenant_id
               AND CAST(p.external_id AS UNSIGNED) = a.professional_external_id
            WHERE a.tenant_id=:tid AND a.year_month_key=:ym
              AND a.professional_external_id IS NOT NULL
            GROUP BY a.professional_external_id
            HAVING executadas > 0
            ORDER BY executadas DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    rows = q.all()
    if not rows:
        return []

    denom = consultas_total_clinica or 1
    out: List[TopProfissionalConsultas] = []
    for r in rows:
        exec_qty = int(r.executadas or 0)
        falt_qty = int(r.faltas or 0)
        # Absenteísmo clínico do profissional: faltas sobre quem teve desfecho
        # (efetivas + faltas). Cancelamentos não entram — não é absenteísmo.
        denom_abs = exec_qty + falt_qty
        out.append(TopProfissionalConsultas(
            professional_external_id=int(r.pid),
            nome=r.nome or f"Prof. #{r.pid}",
            qtd_consultas=exec_qty,
            qtd_canceladas=int(r.canceladas or 0),
            absenteismo_pct=round(falt_qty / denom_abs * 100, 1) if denom_abs else 0.0,
            pacientes_distintos=int(r.pacientes or 0),
            ocupacao_pct=None,  # Sub-PR futuro: comparar com capacidade P95
            pct_volume=round(exec_qty / denom * 100, 1),
        ))
    return out


# ── Mix de categorias de consulta ───────────────────────────────


async def _mix_categorias_consulta(
    db: AsyncSession, tenant_id: str, ym: str, ym_prev: str,
    progress: Optional[float] = None, top_n: int = 10,
) -> List[MixCategoriaConsulta]:
    """Distribuição de consultas por categoria (ex: consulta, retorno, manutenção)."""
    # Mix por categoria — base = consultas EFETIVAS (CHECKOUT). Faltas e
    # cancelamentos não entram no mix porque a categoria do que NÃO aconteceu
    # não dá leitura útil sobre demanda real.
    cur_q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(category_description, ''), 'Sem categoria') AS categoria,
                COUNT(*) AS qtd,
                SUM(is_falta) AS faltas
            FROM fato_agenda
            WHERE tenant_id=:tid AND year_month_key=:ym AND is_efetiva=1
            GROUP BY categoria
            ORDER BY qtd DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ym": ym, "lim": top_n},
    )
    cur_rows = cur_q.all()
    total = sum(int(r.qtd or 0) for r in cur_rows) or 1

    prev_q = await db.execute(
        text("""
            SELECT
                COALESCE(NULLIF(category_description, ''), 'Sem categoria') AS categoria,
                COUNT(*) AS qtd
            FROM fato_agenda
            WHERE tenant_id=:tid AND year_month_key=:ym AND is_efetiva=1
            GROUP BY categoria
        """),
        {"tid": tenant_id, "ym": ym_prev},
    )
    prev_by_cat = {r.categoria: int(r.qtd or 0) for r in prev_q.all()}

    is_partial = progress is not None and progress > 0
    out: List[MixCategoriaConsulta] = []
    for r in cur_rows:
        qtd = int(r.qtd or 0)
        compare_qty = (qtd / progress) if is_partial else qtd
        out.append(MixCategoriaConsulta(
            categoria=r.categoria,
            qtd=qtd,
            pct=round(qtd / total * 100, 1),
            canceladas=0,                 # categoria das efetivas — sem faltas/cancel aqui
            absenteismo_pct=0.0,
            mom_pct=_delta_pct(compare_qty, prev_by_cat.get(r.categoria)),
        ))
    return out


# ── Operacional ─────────────────────────────────────────────────


def _build_operacional(
    cur: _ComercialAgg, ticket_medio_consulta: float,
) -> OperacionalComercial:
    perda_estimada = cur.consultas_canceladas * ticket_medio_consulta
    encaixe_pct = (
        cur.encaixe_qty / cur.consultas_total * 100
    ) if cur.consultas_total else 0.0
    return OperacionalComercial(
        encaixe_qty=cur.encaixe_qty,
        encaixe_pct=round(encaixe_pct, 1),
        retorno_pendente_qty=cur.retorno_pendente_qty,
        remarcar_qty=cur.remarcar_qty,
        cancelados_qty=cur.consultas_canceladas,
        cancelados_amount_estimado=round(perda_estimada, 2),
    )


# ── KPI builders ────────────────────────────────────────────────


def _build_consultas_card(
    series: List[_ComercialAgg], *,
    year: int, month: int, progress: Optional[float],
) -> KpiCard:
    cur = series[-1]
    series_12 = [s.consultas_efetivas for s in series]

    projected = (cur.consultas_efetivas / progress) if progress and progress > 0 else None
    projected_label = (
        f"{int(round(projected))} projetado" if projected is not None else None
    )

    insight = None
    if len(series) >= 7:
        avg_6 = sum(s.consultas_efetivas for s in series[-7:-1]) / 6
        compare = projected if projected is not None else cur.consultas_efetivas
        if avg_6 > 0:
            diff = (compare - avg_6) / avg_6 * 100
            if abs(diff) >= 5:
                verb = "acima" if diff > 0 else "abaixo"
                qualifier = "projetado " if projected is not None else ""
                insight = f"{qualifier}{abs(diff):.0f}% {verb} da média de 6 meses"

    return _build_kpi_card(
        value=cur.consultas_efetivas,
        value_label=_fmt_int(cur.consultas_efetivas),
        series_12m=series_12,
        insight=insight,
        partial_progress=progress,
        projected_value=projected,
        projected_label=projected_label,
        year=year, month=month,
        use_projection_for_compare=True,
    )


def _build_absenteismo_card(
    series: List[_ComercialAgg], *,
    year: int, month: int, progress: Optional[float],
) -> KpiCard:
    """Absenteísmo clínico = faltas / (efetivas + faltas).

    Mede só pacientes com desfecho marcado: dos que tinham que comparecer,
    quantos não vieram. Cancelamentos NÃO entram (cancel pela clínica ou pelo
    paciente com aviso não é absenteísmo). is_inverse: menor é melhor.
    """
    series_12 = [
        (s.consultas_faltas / (s.consultas_efetivas + s.consultas_faltas) * 100)
        if (s.consultas_efetivas + s.consultas_faltas) else 0.0
        for s in series
    ]
    cur = series_12[-1]

    insight = None
    if len(series_12) >= 7:
        avg_6 = sum(series_12[-7:-1]) / 6
        if abs(cur - avg_6) >= 1:
            verb = "acima" if cur > avg_6 else "abaixo"
            insight = f"{abs(cur - avg_6):.1f}pp {verb} da média de 6m"

    return _build_kpi_card(
        value=cur,
        value_label=_fmt_pct(cur),
        series_12m=series_12,
        is_inverse=True,
        insight=insight,
        partial_progress=progress,
        year=year, month=month,
    )


def _build_conversao_consulta_orc_card(
    series: List[_ComercialAgg], *,
    year: int, month: int, progress: Optional[float],
) -> KpiCard:
    """% de pacientes que vieram à consulta E fecharam orçamento no mesmo mês.

    Cálculo correto por PACIENTE (cardinalidade igual num/denom):
        pacientes_efetivos_com_aprovado / pacientes_unicos_efetivos

    Substitui cálculo errado anterior (orçamentos / consultas), que misturava
    cardinalidades e dava leitura enganosa.
    """
    series_12 = [
        (s.pacientes_efetivos_com_aprovado / s.pacientes_unicos_efetivos * 100)
        if s.pacientes_unicos_efetivos else 0.0
        for s in series
    ]
    cur = series_12[-1]

    insight = None
    if len(series_12) >= 7:
        avg_6 = sum(series_12[-7:-1]) / 6
        if abs(cur - avg_6) >= 2:
            verb = "acima" if cur > avg_6 else "abaixo"
            insight = f"{abs(cur - avg_6):.0f}pp {verb} da média de 6m"

    return _build_kpi_card(
        value=cur,
        value_label=_fmt_pct(cur),
        series_12m=series_12,
        insight=insight,
        partial_progress=progress,
        year=year, month=month,
    )


def _build_pacientes_unicos_card(
    series: List[_ComercialAgg], *,
    year: int, month: int, progress: Optional[float],
) -> KpiCard:
    """Pacientes distintos com consulta EFETIVA no mês (CHECKOUT).

    Antes contava qualquer paciente que apareceu na agenda (incluía só faltas
    ou só cancelados) — agora só os que foram realmente atendidos.
    """
    cur = series[-1]
    series_12 = [s.pacientes_unicos_efetivos for s in series]

    projected = (cur.pacientes_unicos_efetivos / progress) if progress and progress > 0 else None
    projected_label = (
        f"{int(round(projected))} projetado" if projected is not None else None
    )

    return _build_kpi_card(
        value=cur.pacientes_unicos_efetivos,
        value_label=_fmt_int(cur.pacientes_unicos_efetivos),
        series_12m=series_12,
        partial_progress=progress,
        projected_value=projected,
        projected_label=projected_label,
        year=year, month=month,
        use_projection_for_compare=True,
    )


# ── Conversão — breakdown dos pacientes não convertidos ─────────


async def _build_conversao_breakdown(
    db: AsyncSession, tenant_id: str, ym: str,
) -> ConversaoBreakdown:
    """Decompõe os pacientes atendidos no mês em 5 status de conversão.

    Soma sempre = total_atendidos. Permite explicar o complemento dos 100%
    do KPI: dos que não converteram, quantos estão em decisão, em tratamento,
    são avulsos puros (nunca tiveram orçamento) ou têm histórico antigo.
    """
    sql = """
        WITH atendidos AS (
          SELECT DISTINCT patient_external_id
          FROM fato_agenda
          WHERE tenant_id=:tid AND year_month_key=:ym
            AND is_efetiva=1 AND patient_external_id IS NOT NULL
        ),
        orc_no_mes AS (
          SELECT patient_external_id, MAX(is_approved) AS tem_aprovado
          FROM fato_orcamentos
          WHERE tenant_id=:tid AND year_month_key=:ym
          GROUP BY patient_external_id
        ),
        qualquer_orc AS (
          SELECT DISTINCT patient_external_id
          FROM fato_orcamentos
          WHERE tenant_id=:tid
        ),
        aprovado_anterior AS (
          SELECT DISTINCT patient_external_id
          FROM fato_orcamentos
          WHERE tenant_id=:tid AND year_month_key < :ym AND is_approved=1
        )
        SELECT
          COUNT(*)                                                                                AS total,
          SUM(CASE WHEN o.tem_aprovado=1 THEN 1 ELSE 0 END)                                       AS aprovou,
          SUM(CASE WHEN o.patient_external_id IS NOT NULL AND o.tem_aprovado=0 THEN 1 ELSE 0 END) AS gerou_n_aprov,
          SUM(CASE WHEN o.patient_external_id IS NULL AND ap.patient_external_id IS NOT NULL THEN 1 ELSE 0 END) AS em_trat,
          SUM(CASE WHEN qo.patient_external_id IS NULL THEN 1 ELSE 0 END)                         AS avulso
        FROM atendidos a
        LEFT JOIN orc_no_mes o          ON o.patient_external_id  = a.patient_external_id
        LEFT JOIN aprovado_anterior ap  ON ap.patient_external_id = a.patient_external_id
        LEFT JOIN qualquer_orc qo       ON qo.patient_external_id = a.patient_external_id
    """
    r = (await db.execute(text(sql), {"tid": tenant_id, "ym": ym})).one()
    total = int(r.total or 0)
    aprovou = int(r.aprovou or 0)
    gerou_n_aprov = int(r.gerou_n_aprov or 0)
    em_trat = int(r.em_trat or 0)
    avulso = int(r.avulso or 0)
    historico = max(total - aprovou - gerou_n_aprov - em_trat - avulso, 0)
    pct = (lambda v: round(v / total * 100, 1) if total else 0.0)
    return ConversaoBreakdown(
        total_atendidos=total,
        aprovou_no_mes=aprovou,                 aprovou_no_mes_pct=pct(aprovou),
        gerou_nao_aprovou=gerou_n_aprov,        gerou_nao_aprovou_pct=pct(gerou_n_aprov),
        em_tratamento=em_trat,                  em_tratamento_pct=pct(em_trat),
        avulso_sem_orcamento=avulso,            avulso_sem_orcamento_pct=pct(avulso),
        historico_sem_aprov=historico,          historico_sem_aprov_pct=pct(historico),
    )


# ── Saúde da agenda ─────────────────────────────────────────────


def _build_saude_agenda(cur: _ComercialAgg) -> SaudeAgendaSection:
    """Decompõe o universo de agendamentos do mês em desfechos."""
    total = cur.consultas_total or 1  # evita divisão por zero
    efetivas = cur.consultas_efetivas
    faltas = cur.consultas_faltas
    canceladas = cur.consultas_canceladas
    indefinidas = cur.consultas_indefinidas
    outros = max(cur.consultas_total - (efetivas + faltas + canceladas + indefinidas), 0)
    desfecho = efetivas + faltas
    return SaudeAgendaSection(
        total=cur.consultas_total,
        efetivas=efetivas,
        faltas=faltas,
        canceladas=canceladas,
        indefinidas=indefinidas,
        outros=outros,
        pct_efetivas=round(efetivas / total * 100, 1),
        pct_faltas=round(faltas / total * 100, 1),
        pct_canceladas=round(canceladas / total * 100, 1),
        pct_indefinidas=round(indefinidas / total * 100, 1),
        pct_outros=round(outros / total * 100, 1),
        absenteismo_clinico_pct=round(faltas / desfecho * 100, 1) if desfecho else 0.0,
    )


# ── API pública ─────────────────────────────────────────────────


async def get_analise_comercial(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> AnaliseComercialResponse:
    """Builder principal — orquestra todas as queries do dashboard comercial."""
    ym = _ym_key(year, month)
    py, pm = _prev_month(year, month)
    yy, ym_yoy = _yoy_month(year, month)
    ym_prev = _ym_key(py, pm)

    series = await _aggregate_last_12(db, tenant_id, year, month)
    cur = series[-1]
    progress = _month_progress(year, month)

    # Ticket médio consulta atual (pra alimentar operacional)
    ticket_medio = (cur.recebido / cur.consultas_efetivas) if cur.consultas_efetivas else 0.0

    funil = await _funil_comercial(db, tenant_id, ym, ym_prev)
    top_procs = await _top_procedimentos(db, tenant_id, ym)
    top_esp = await _top_especialidades(db, tenant_id, ym)
    top_profs = await _top_profs_consultas(db, tenant_id, ym, cur.consultas_efetivas)
    mix_cat = await _mix_categorias_consulta(db, tenant_id, ym, ym_prev, progress=progress)
    operacional = _build_operacional(cur, ticket_medio)

    consultas_kpi = _build_consultas_card(series, year=year, month=month, progress=progress)
    abs_kpi = _build_absenteismo_card(series, year=year, month=month, progress=progress)
    conv_kpi = _build_conversao_consulta_orc_card(series, year=year, month=month, progress=progress)
    conv_breakdown = await _build_conversao_breakdown(db, tenant_id, ym)
    pac_kpi = _build_pacientes_unicos_card(series, year=year, month=month, progress=progress)

    yms_12 = _last_12_yms(year, month)
    evolution = [
        ComercialEvolutionPoint(
            year_month_key=_ym_key(y, m),
            label=_ym_short_label(y, m),
            efetivas=s.consultas_efetivas,
            faltas=s.consultas_faltas,
            canceladas=s.consultas_canceladas,
            indefinidas=s.consultas_indefinidas,
            pacientes_unicos=s.pacientes_unicos_efetivos,
        )
        for (y, m), s in zip(yms_12, series)
    ]

    return AnaliseComercialResponse(
        period=_period(year, month),
        previous=_period(py, pm),
        yoy=_period(yy, ym_yoy),
        kpis=ComercialKpis(
            consultas=consultas_kpi,
            absenteismo_pct=abs_kpi,
            conversao_consulta_orcamento_pct=conv_kpi,
            conversao_breakdown=conv_breakdown,
            pacientes_unicos=pac_kpi,
        ),
        funil=funil,
        saude_agenda=_build_saude_agenda(cur),
        top_procedimentos=top_procs,
        top_especialidades=top_esp,
        top_profissionais=top_profs,
        mix_categorias=mix_cat,
        operacional=operacional,
        evolution=evolution,
    )
