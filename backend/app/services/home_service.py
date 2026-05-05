"""
Cockpit Operacional — service da HomePage.

Cada role tem um subset de cards. Manager/tenant_admin/saas_admin veem todos.

Roles → seções:
- operations:    agenda, recall
- financial:     resumo_dia, inadimplencia_critica
- commercial:    orcamentos_parados, recall, top_profs_semana
- manager:       todos
- tenant_admin:  todos
- saas_admin:    todos
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.home import (
    AgendaItem,
    AgendaSection,
    HomeDashboardResponse,
    InadimplenciaCriticaItem,
    InadimplenciaCriticaSection,
    OrcamentoParadoItem,
    OrcamentosParadosSection,
    RecallItem,
    RecallSection,
    ResumoDiaSection,
    TopProfissionalSemanaItem,
    TopProfsSemanaSection,
)


_ROLE_LABELS = {
    "operations": "Operações",
    "financial": "Financeiro",
    "commercial": "Comercial",
    "manager": "Gestão",
    "tenant_admin": "Administrador",
    "saas_admin": "SaaS Admin",
}

_FULL_VIEW_ROLES = {"manager", "tenant_admin", "saas_admin"}


def _can_see(role: str, section: str) -> bool:
    if role in _FULL_VIEW_ROLES:
        return True
    matrix = {
        "operations": {"agenda", "recall"},
        "financial": {"resumo_dia", "inadimplencia_critica"},
        "commercial": {"orcamentos_parados", "recall", "top_profs_semana"},
    }
    return section in matrix.get(role, set())


# ── Agenda ──────────────────────────────────────────────────────


async def _agenda(db: AsyncSession, tenant_id: str, today: date) -> AgendaSection:
    """Agenda de hoje. Se vazio, faz fallback pro próximo dia com dados (até 7d)."""
    target = today
    is_today = True

    # Conta hoje
    q = await db.execute(
        text("""
            SELECT COUNT(*) AS qtd
            FROM fato_agenda
            WHERE tenant_id = :tid AND date_key = :d AND is_canceled = 0
        """),
        {"tid": tenant_id, "d": today},
    )
    if int(q.scalar_one() or 0) == 0:
        # Fallback: primeiro dia com agenda nos próximos 7
        fallback_q = await db.execute(
            text("""
                SELECT MIN(date_key) AS d FROM fato_agenda
                WHERE tenant_id = :tid AND is_canceled = 0
                  AND date_key BETWEEN :d AND DATE_ADD(:d, INTERVAL 7 DAY)
            """),
            {"tid": tenant_id, "d": today},
        )
        fallback = fallback_q.scalar_one_or_none()
        if fallback:
            target = fallback
            is_today = False

    items_q = await db.execute(
        text("""
            SELECT
                fa.external_id,
                fa.patient_external_id,
                fa.professional_external_id,
                fa.appointment_datetime,
                fa.duration_minutes,
                fa.category_color,
                COALESCE(NULLIF(fa.category_description, ''), 'Sem categoria') AS categoria,
                MAX(dp.name) AS paciente_nome,
                MAX(dpr.name) AS prof_nome
            FROM fato_agenda fa
            LEFT JOIN dim_paciente dp
                ON dp.tenant_id = fa.tenant_id
               AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            LEFT JOIN dim_profissional dpr
                ON dpr.tenant_id = fa.tenant_id
               AND CAST(dpr.external_id AS UNSIGNED) = fa.professional_external_id
            WHERE fa.tenant_id = :tid AND fa.date_key = :d AND fa.is_canceled = 0
            GROUP BY fa.id, fa.external_id, fa.patient_external_id, fa.professional_external_id,
                     fa.appointment_datetime, fa.duration_minutes, fa.category_color, fa.category_description
            ORDER BY fa.appointment_datetime ASC
        """),
        {"tid": tenant_id, "d": target},
    )

    items: List[AgendaItem] = []
    for r in items_q.all():
        horario = r.appointment_datetime.strftime("%H:%M") if r.appointment_datetime else None
        items.append(AgendaItem(
            external_id=str(r.external_id),
            paciente_external_id=r.patient_external_id,
            paciente_nome=r.paciente_nome or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            profissional_external_id=r.professional_external_id,
            profissional_nome=r.prof_nome,
            horario=horario,
            categoria=r.categoria,
            category_color=r.category_color,
            duration_minutes=r.duration_minutes,
        ))

    from datetime import datetime
    now = datetime.now()
    occ = 0
    nxt = 0
    for it in items:
        if it.horario:
            h, m = it.horario.split(":")
            slot = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            if is_today and slot < now:
                occ += 1
            else:
                nxt += 1
        else:
            nxt += 1

    return AgendaSection(
        date_iso=target.isoformat(),
        is_today=is_today,
        total=len(items),
        horarios_ocupados=occ,
        proximas=nxt,
        items=items,
    )


# ── Recall ──────────────────────────────────────────────────────


async def _recall(db: AsyncSession, tenant_id: str, today: date, top_n: int = 20) -> RecallSection:
    """Heurística por histórico de consultas. Filtra zona útil:
    - >= 3 consultas, intervalo médio >= 30 dias
    - dias desde última entre 30 e 270 (1 mês a 9 meses)
    - dias desde > intervalo médio × 1.3
    - sem agenda futura
    Ordena por qtd_consultas DESC (paciente fiel primeiro), depois atraso DESC.
    """
    sql = text("""
        WITH metricas AS (
            SELECT
                fa.patient_external_id,
                COUNT(*) AS qtd,
                DATEDIFF(MAX(fa.date_key), MIN(fa.date_key)) AS span,
                MAX(fa.date_key) AS ultima
            FROM fato_agenda fa
            WHERE fa.tenant_id = :tid
              AND fa.is_canceled = 0
              AND fa.patient_external_id IS NOT NULL
            GROUP BY fa.patient_external_id
            HAVING COUNT(*) >= 3 AND DATEDIFF(MAX(fa.date_key), MIN(fa.date_key)) > 0
        ),
        elegiveis AS (
            SELECT
                m.patient_external_id,
                m.qtd,
                m.ultima,
                DATEDIFF(:today, m.ultima) AS dias_desde,
                ROUND(m.span / (m.qtd - 1), 0) AS intervalo
            FROM metricas m
            WHERE ROUND(m.span / (m.qtd - 1), 0) >= 30
              AND DATEDIFF(:today, m.ultima) BETWEEN 30 AND 270
              AND DATEDIFF(:today, m.ultima) > ROUND(m.span / (m.qtd - 1), 0) * 1.3
        )
        SELECT
            e.patient_external_id,
            e.qtd,
            e.intervalo,
            e.dias_desde,
            e.ultima,
            ROUND(e.dias_desde / e.intervalo, 2) AS atraso_rel,
            COALESCE(dp.name, CONCAT('Paciente #', e.patient_external_id)) AS nome,
            COALESCE(dp.total_payments, 0) AS payments
        FROM elegiveis e
        INNER JOIN dim_paciente dp
            ON dp.tenant_id = :tid
           AND CAST(dp.external_id AS UNSIGNED) = e.patient_external_id
        WHERE dp.is_active = 1
          AND NOT EXISTS (
              SELECT 1 FROM fato_agenda fa2
              WHERE fa2.tenant_id = :tid
                AND fa2.patient_external_id = e.patient_external_id
                AND fa2.date_key >= :today
                AND fa2.is_canceled = 0
          )
        ORDER BY e.qtd DESC, atraso_rel DESC
        LIMIT :lim
    """)
    q = await db.execute(sql, {"tid": tenant_id, "today": today, "lim": top_n})
    items = [
        RecallItem(
            paciente_external_id=int(r.patient_external_id),
            paciente_nome=r.nome,
            qtd_consultas=int(r.qtd or 0),
            intervalo_medio_dias=int(r.intervalo or 0),
            dias_desde_ultima=int(r.dias_desde or 0),
            atraso_relativo=float(r.atraso_rel or 0),
            ultima_consulta_iso=r.ultima.isoformat(),
            total_payments=int(r.payments or 0),
        )
        for r in q.all()
    ]

    # Total elegíveis (sem LIMIT) — separado pra mostrar "X de N"
    cnt_q = await db.execute(
        text("""
            SELECT COUNT(*) FROM (
                SELECT m.patient_external_id FROM (
                    SELECT patient_external_id, COUNT(*) qtd,
                           DATEDIFF(MAX(date_key), MIN(date_key)) span,
                           MAX(date_key) ultima
                    FROM fato_agenda
                    WHERE tenant_id = :tid AND is_canceled = 0
                      AND patient_external_id IS NOT NULL
                    GROUP BY patient_external_id
                    HAVING COUNT(*) >= 3 AND DATEDIFF(MAX(date_key), MIN(date_key)) > 0
                ) m
                INNER JOIN dim_paciente dp
                    ON dp.tenant_id = :tid
                   AND CAST(dp.external_id AS UNSIGNED) = m.patient_external_id
                WHERE dp.is_active = 1
                  AND ROUND(m.span/(m.qtd-1), 0) >= 30
                  AND DATEDIFF(:today, m.ultima) BETWEEN 30 AND 270
                  AND DATEDIFF(:today, m.ultima) > ROUND(m.span/(m.qtd-1), 0) * 1.3
                  AND NOT EXISTS (
                      SELECT 1 FROM fato_agenda fa2
                      WHERE fa2.tenant_id = :tid
                        AND fa2.patient_external_id = m.patient_external_id
                        AND fa2.date_key >= :today AND fa2.is_canceled = 0
                  )
            ) t
        """),
        {"tid": tenant_id, "today": today},
    )
    total = int(cnt_q.scalar_one() or 0)

    return RecallSection(total_elegiveis=total, items=items)


# ── Orçamentos parados ─────────────────────────────────────────


async def _orcamentos_parados(db: AsyncSession, tenant_id: str, today: date, top_n: int = 10) -> OrcamentosParadosSection:
    """Aprovados há 30-90 dias sem nova consulta agendada."""
    sql = text("""
        SELECT
            fo.external_id,
            fo.patient_external_id,
            fo.amount,
            fo.date_key AS data_aprovacao,
            DATEDIFF(:today, fo.date_key) AS dias_aprovado,
            COALESCE(dp.name, CONCAT('Paciente #', fo.patient_external_id)) AS paciente_nome,
            MAX(dpr.name) AS prof_nome
        FROM fato_orcamentos fo
        LEFT JOIN dim_paciente dp
            ON dp.tenant_id = fo.tenant_id
           AND CAST(dp.external_id AS UNSIGNED) = fo.patient_external_id
        LEFT JOIN dim_profissional dpr
            ON dpr.tenant_id = fo.tenant_id
           AND CAST(dpr.external_id AS UNSIGNED) = fo.professional_external_id
        WHERE fo.tenant_id = :tid
          AND fo.is_approved = 1
          AND fo.date_key BETWEEN DATE_SUB(:today, INTERVAL 90 DAY) AND DATE_SUB(:today, INTERVAL 30 DAY)
          AND NOT EXISTS (
              SELECT 1 FROM fato_agenda fa
              WHERE fa.tenant_id = fo.tenant_id
                AND fa.patient_external_id = fo.patient_external_id
                AND fa.date_key > fo.date_key
                AND fa.is_canceled = 0
          )
        GROUP BY fo.id, fo.external_id, fo.patient_external_id, fo.amount, fo.date_key, dp.name
        ORDER BY fo.amount DESC, fo.date_key ASC
        LIMIT :lim
    """)
    q = await db.execute(sql, {"tid": tenant_id, "today": today, "lim": top_n})
    items = []
    for r in q.all():
        items.append(OrcamentoParadoItem(
            external_id=str(r.external_id),
            paciente_external_id=r.patient_external_id,
            paciente_nome=r.paciente_nome,
            profissional_nome=r.prof_nome,
            amount=float(r.amount or 0),
            dias_aprovado=int(r.dias_aprovado or 0),
            data_aprovacao_iso=r.data_aprovacao.isoformat(),
        ))

    # Totais (sem LIMIT)
    tot_q = await db.execute(
        text("""
            SELECT COUNT(*) qtd, COALESCE(SUM(fo.amount), 0) total
            FROM fato_orcamentos fo
            WHERE fo.tenant_id = :tid AND fo.is_approved = 1
              AND fo.date_key BETWEEN DATE_SUB(:today, INTERVAL 90 DAY) AND DATE_SUB(:today, INTERVAL 30 DAY)
              AND NOT EXISTS (
                  SELECT 1 FROM fato_agenda fa
                  WHERE fa.tenant_id = fo.tenant_id
                    AND fa.patient_external_id = fo.patient_external_id
                    AND fa.date_key > fo.date_key
                    AND fa.is_canceled = 0
              )
        """),
        {"tid": tenant_id, "today": today},
    )
    row = tot_q.one()

    return OrcamentosParadosSection(
        total=int(row.qtd or 0),
        valor_total=float(row.total or 0),
        items=items,
    )


# ── Inadimplência crítica ──────────────────────────────────────


async def _inadimplencia_critica(db: AsyncSession, tenant_id: str, top_n: int = 10) -> InadimplenciaCriticaSection:
    """Vencido > 60 dias, valor > R$ 500. Aggrega por parcela_external_id (já que fato_caixa é granular no rateio)."""
    sql = text("""
        SELECT
            fc.parcela_external_id,
            MAX(ef.pessoa_nome) AS pessoa_nome,
            MAX(dc.nome) AS categoria,
            MIN(fc.date_key) AS data_venc,
            MAX(fc.dias_atraso) AS dias_atraso,
            SUM(fc.valor_em_aberto_rateado) AS valor_aberto
        FROM fato_caixa fc
        LEFT JOIN core_ca_eventos_financeiros ef
            ON ef.tenant_id = fc.tenant_id AND ef.external_id = fc.parcela_external_id
        LEFT JOIN dim_categoria_ca dc
            ON dc.tenant_id = fc.tenant_id AND dc.external_id = fc.categoria_external_id
        WHERE fc.tenant_id = :tid
          AND fc.tipo = 'RECEITA'
          AND fc.is_vencido = 1
          AND fc.dias_atraso > 60
        GROUP BY fc.parcela_external_id
        HAVING SUM(fc.valor_em_aberto_rateado) > 500
        ORDER BY valor_aberto DESC
        LIMIT :lim
    """)
    q = await db.execute(sql, {"tid": tenant_id, "lim": top_n})
    items = [
        InadimplenciaCriticaItem(
            parcela_external_id=str(r.parcela_external_id),
            pessoa_nome=r.pessoa_nome or "Sem nome",
            categoria=r.categoria,
            valor_em_aberto=float(r.valor_aberto or 0),
            dias_atraso=int(r.dias_atraso or 0),
            data_vencimento_iso=r.data_venc.isoformat(),
        )
        for r in q.all()
    ]
    tot_q = await db.execute(
        text("""
            SELECT COUNT(*) qtd, COALESCE(SUM(t.valor), 0) total FROM (
                SELECT SUM(valor_em_aberto_rateado) valor
                FROM fato_caixa
                WHERE tenant_id = :tid AND tipo='RECEITA' AND is_vencido=1 AND dias_atraso > 60
                GROUP BY parcela_external_id HAVING SUM(valor_em_aberto_rateado) > 500
            ) t
        """),
        {"tid": tenant_id},
    )
    row = tot_q.one()
    return InadimplenciaCriticaSection(
        total=int(row.qtd or 0),
        valor_total=float(row.total or 0),
        items=items,
    )


# ── Resumo do dia ──────────────────────────────────────────────


async def _resumo_dia(db: AsyncSession, tenant_id: str, today: date) -> ResumoDiaSection:
    q = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(CASE WHEN tipo='RECEITA' AND is_em_aberto=1 THEN valor_em_aberto_rateado ELSE 0 END), 0) AS entradas,
                COALESCE(SUM(CASE WHEN tipo='DESPESA' AND is_em_aberto=1 THEN valor_em_aberto_rateado ELSE 0 END), 0) AS saidas,
                COUNT(*) AS qtd
            FROM fato_caixa
            WHERE tenant_id = :tid AND date_key = :d
        """),
        {"tid": tenant_id, "d": today},
    )
    r = q.one()
    entradas = float(r.entradas or 0)
    saidas = float(r.saidas or 0)
    return ResumoDiaSection(
        entradas_previstas=entradas,
        saidas_previstas=saidas,
        saldo_previsto=round(entradas - saidas, 2),
        qtd_parcelas_hoje=int(r.qtd or 0),
    )


# ── Top profissionais semana ───────────────────────────────────


async def _top_profs_semana(db: AsyncSession, tenant_id: str, today: date, top_n: int = 5) -> TopProfsSemanaSection:
    """Semana corrente: segunda a domingo (ISO)."""
    weekday = today.isoweekday()  # 1=segunda, 7=domingo
    inicio = today - timedelta(days=weekday - 1)
    fim = inicio + timedelta(days=6)

    q = await db.execute(
        text("""
            SELECT
                fo.professional_external_id,
                MAX(dpr.name) AS nome,
                COALESCE(SUM(CASE WHEN fo.is_approved = 1 THEN fo.amount ELSE 0 END), 0) AS valor,
                COALESCE(SUM(CASE WHEN fo.is_approved = 1 THEN 1 ELSE 0 END), 0) AS qtd
            FROM fato_orcamentos fo
            LEFT JOIN dim_profissional dpr
                ON dpr.tenant_id = fo.tenant_id
               AND CAST(dpr.external_id AS UNSIGNED) = fo.professional_external_id
            WHERE fo.tenant_id = :tid
              AND fo.date_key BETWEEN :ini AND :fim
              AND fo.professional_external_id IS NOT NULL
            GROUP BY fo.professional_external_id
            HAVING valor > 0
            ORDER BY valor DESC
            LIMIT :lim
        """),
        {"tid": tenant_id, "ini": inicio, "fim": fim, "lim": top_n},
    )
    items = [
        TopProfissionalSemanaItem(
            external_id=int(r.professional_external_id),
            nome=r.nome or f"Prof. #{r.professional_external_id}",
            valor_aprovado=float(r.valor or 0),
            qtd_aprovados=int(r.qtd or 0),
        )
        for r in q.all()
    ]
    return TopProfsSemanaSection(
        inicio_iso=inicio.isoformat(),
        fim_iso=fim.isoformat(),
        items=items,
    )


# ── Orquestrador ────────────────────────────────────────────────


async def get_home_dashboard(
    db: AsyncSession, tenant_id: str, role: str, user_full_name: str,
) -> HomeDashboardResponse:
    today = date.today()

    agenda = await _agenda(db, tenant_id, today) if _can_see(role, "agenda") else None
    recall = await _recall(db, tenant_id, today) if _can_see(role, "recall") else None
    orc_parados = await _orcamentos_parados(db, tenant_id, today) if _can_see(role, "orcamentos_parados") else None
    inad = await _inadimplencia_critica(db, tenant_id) if _can_see(role, "inadimplencia_critica") else None
    resumo = await _resumo_dia(db, tenant_id, today) if _can_see(role, "resumo_dia") else None
    top_profs = await _top_profs_semana(db, tenant_id, today) if _can_see(role, "top_profs_semana") else None

    return HomeDashboardResponse(
        role=role,
        role_label=_ROLE_LABELS.get(role, role),
        user_full_name=user_full_name,
        today_iso=today.isoformat(),
        agenda=agenda,
        recall=recall,
        orcamentos_parados=orc_parados,
        inadimplencia_critica=inad,
        resumo_dia=resumo,
        top_profs_semana=top_profs,
    )
