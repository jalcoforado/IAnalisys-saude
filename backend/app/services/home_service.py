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

from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy import bindparam as sa_bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.home import (
    AgendaItem,
    AgendaSection,
    AppointmentTagBrief,
    CapacityProfBucket,
    CapacitySection,
    EncaixeSlot,
    PendenciaBucket,
    PendenciaItem,
    PendenciasOperacionaisSection,
    RiskSection,
    RiskTopPatient,
    StrategicDayKPIs,
    StrategicOverview,
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
    WaitlistItem,
    WaitlistSection,
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
        "operations": {"agenda", "recall", "pendencias"},
        "financial": {"resumo_dia", "inadimplencia_critica"},
        "commercial": {"orcamentos_parados", "recall", "top_profs_semana"},
    }
    return section in matrix.get(role, set())


# ── Capacidade (P95 90d) ────────────────────────────────────────


CAPACITY_HISTORY_DAYS = 90
CAPACITY_MIN_HISTORY_DAYS = 14    # abaixo disso o P95 não é confiável
CAPACITY_ENCAIXE_MIN_GAP = 30     # piso — janelas menores não rendem encaixe
CAPACITY_ENCAIXE_MAX_GAP = 90     # teto — gaps maiores são almoço/expediente,
                                  # não janelas reais; cap evita inflar o número.
CAPACITY_PROFS_DESTAQUE = 5       # quantos profs com mais folga mostrar


def _percentile(values: list[float], p: float) -> float:
    """P-percentil sem dependências externas. p em [0, 100]. Lista pode estar
    desordenada. Empty list retorna 0.0.
    """
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    # Método "nearest rank" — suficiente pra capacidade de uso humano.
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return float(s[k])


async def _capacity(
    db: AsyncSession, tenant_id: str, target_date: date, items: list[AgendaItem],
) -> CapacitySection:
    """Computa capacidade da clínica baseada em P95 dos últimos 90 dias.

    P95 evita outliers (1 feirão = 1 dia atípico distorcendo o teto). Ignora
    o próprio dia alvo do cálculo histórico — comparar hoje com hoje seria
    redondo.

    `items` é a agenda do dia já carregada — usamos pra computar ocupação
    atual e detectar janelas de encaixe sem nova query.
    """
    since = target_date - timedelta(days=CAPACITY_HISTORY_DAYS)

    # ── Histórico clínica (consultas/dia + horas-cadeira/dia) ────
    hist_q = await db.execute(
        text("""
            SELECT
                date_key,
                COUNT(*) AS qtd,
                COALESCE(SUM(NULLIF(duration_minutes, 0)), 0) AS dur
            FROM fato_agenda
            WHERE tenant_id = :tid
              AND is_canceled = 0
              AND date_key BETWEEN :since AND :until
              AND date_key <> :target
            GROUP BY date_key
            HAVING qtd > 0
        """),
        {"tid": tenant_id, "since": since, "until": target_date, "target": target_date},
    )
    dias = hist_q.all()
    qtd_series = [int(r.qtd) for r in dias]
    dur_series = [int(r.dur or 0) for r in dias]

    historico_efetivo = len(qtd_series)
    if historico_efetivo >= CAPACITY_MIN_HISTORY_DAYS:
        consultas_teto = int(round(_percentile(qtd_series, 95)))
        horas_teto = int(round(_percentile(dur_series, 95)))
    else:
        # Histórico insuficiente — retorna 0 (front mostra "histórico em construção").
        consultas_teto = 0
        horas_teto = 0

    # Bloqueios (NÃO AGENDAR, Pendência) aparecem como appointments mas não
    # são consultas reais — não devem inflar contagem nem horas-cadeira.
    items_efetivos = [it for it in items if it.category_group != "bloqueio"]
    consultas_hoje = len(items_efetivos)
    horas_hoje = sum((it.duration_minutes or 0) for it in items_efetivos)

    consultas_pct = int(round(min(100.0, 100.0 * consultas_hoje / consultas_teto))) if consultas_teto > 0 else 0
    horas_pct = int(round(min(100.0, 100.0 * horas_hoje / horas_teto))) if horas_teto > 0 else 0

    # ── Histórico por profissional (P95 individual + janela de trabalho) ──
    # Pega tanto a contagem por dia quanto os horários efetivamente atendidos.
    # P5/P95 dos horários dão a "janela típica" do prof — usada pra filtrar
    # encaixes fora do expediente dele (Clinicorp não expõe horário oficial).
    prof_hist_q = await db.execute(
        text("""
            SELECT
                professional_external_id,
                date_key,
                COUNT(*) AS qtd,
                MIN(TIME_TO_SEC(TIME(appointment_datetime))) / 60 AS first_min,
                MAX(TIME_TO_SEC(TIME(appointment_datetime))) / 60 AS last_min
            FROM fato_agenda
            WHERE tenant_id = :tid
              AND is_canceled = 0
              AND professional_external_id IS NOT NULL
              AND appointment_datetime IS NOT NULL
              AND date_key BETWEEN :since AND :until
              AND date_key <> :target
            GROUP BY professional_external_id, date_key
        """),
        {"tid": tenant_id, "since": since, "until": target_date, "target": target_date},
    )
    prof_series: dict[int, list[int]] = {}
    prof_first_minutes: dict[int, list[float]] = {}
    prof_last_minutes: dict[int, list[float]] = {}
    for row in prof_hist_q.all():
        if row.professional_external_id is None:
            continue
        pid = int(row.professional_external_id)
        prof_series.setdefault(pid, []).append(int(row.qtd))
        if row.first_min is not None:
            prof_first_minutes.setdefault(pid, []).append(float(row.first_min))
        if row.last_min is not None:
            prof_last_minutes.setdefault(pid, []).append(float(row.last_min))

    # Janela típica = P5 do primeiro horário, P95 do último horário.
    # Margem de 30min nos dois lados pra acomodar variação natural.
    prof_window: dict[int, tuple[int, int]] = {}
    for pid, firsts in prof_first_minutes.items():
        lasts = prof_last_minutes.get(pid, [])
        if len(firsts) >= 5 and len(lasts) >= 5:
            start = max(0, int(_percentile(firsts, 5)) - 30)
            end = min(24 * 60, int(_percentile(lasts, 95)) + 30)
            if end > start:
                prof_window[pid] = (start, end)

    # Ocupação por prof no dia + nome (do próprio items_efetivos pra excluir
    # bloqueios da contagem; nome ainda vem dos items completos)
    prof_today: dict[int, int] = {}
    prof_name: dict[int, str] = {}
    for it in items_efetivos:
        if it.profissional_external_id is None:
            continue
        prof_today[it.profissional_external_id] = prof_today.get(it.profissional_external_id, 0) + 1
        if it.profissional_nome:
            prof_name.setdefault(it.profissional_external_id, it.profissional_nome)
    for it in items:
        if it.profissional_external_id is not None and it.profissional_nome:
            prof_name.setdefault(it.profissional_external_id, it.profissional_nome)

    profs_buckets: list[CapacityProfBucket] = []
    for pid, hoje in prof_today.items():
        serie = prof_series.get(pid, [])
        teto = int(round(_percentile(serie, 95))) if len(serie) >= CAPACITY_MIN_HISTORY_DAYS else 0
        ocup = int(round(min(100.0, 100.0 * hoje / teto))) if teto > 0 else 0
        profs_buckets.append(CapacityProfBucket(
            professional_external_id=pid,
            professional_nome=prof_name.get(pid),
            consultas_hoje=hoje,
            consultas_teto_p95=teto,
            ocupacao_pct=ocup,
        ))
    # Profs com folga = ocupação mais baixa primeiro (e teto > 0 pra ser comparável)
    profs_com_folga = sorted(
        [p for p in profs_buckets if p.consultas_teto_p95 > 0],
        key=lambda p: p.ocupacao_pct,
    )[:CAPACITY_PROFS_DESTAQUE]

    # ── Encaixes: gaps entre [30, 90]min entre consultas/bloqueios ──
    # Inclui bloqueios na sequência pra que ocupem o slot e não gerem
    # falsos encaixes. O teto de 90min descarta janelas grandes (almoço,
    # fim de expediente) que provavelmente não são encaixáveis.
    by_prof: dict[int, list[AgendaItem]] = {}
    for it in items:
        if it.profissional_external_id is None or not it.horario:
            continue
        by_prof.setdefault(it.profissional_external_id, []).append(it)

    encaixes: list[EncaixeSlot] = []
    for pid, lst in by_prof.items():
        lst_sorted = sorted(lst, key=lambda x: _hhmm_to_min(x.horario or "00:00"))
        # Janela típica do prof (do histórico). Sem janela = aceita qualquer
        # horário (prof novo ou com pouco histórico).
        window = prof_window.get(pid)
        for prev, nxt in zip(lst_sorted, lst_sorted[1:]):
            prev_end = _hhmm_to_min(prev.horario or "00:00") + (prev.duration_minutes or 30)
            nxt_start = _hhmm_to_min(nxt.horario or "00:00")
            gap = nxt_start - prev_end
            if not (CAPACITY_ENCAIXE_MIN_GAP <= gap <= CAPACITY_ENCAIXE_MAX_GAP):
                continue
            # Filtra por janela típica do prof — encaixe deve estar inteiramente
            # dentro da faixa em que ele atende habitualmente. Sem isso, gaps
            # gerados por bloqueios (faixa cinza Clinicorp que não vem na API)
            # virariam falsas oportunidades.
            if window is not None:
                w_start, w_end = window
                if prev_end < w_start or nxt_start > w_end:
                    continue
            encaixes.append(EncaixeSlot(
                professional_external_id=pid,
                professional_nome=prof_name.get(pid),
                inicio=_min_to_hhmm(prev_end),
                fim=_min_to_hhmm(nxt_start),
                duracao_min=gap,
            ))
    encaixes.sort(key=lambda e: e.duracao_min, reverse=True)

    return CapacitySection(
        historico_dias=CAPACITY_HISTORY_DAYS,
        historico_dias_efetivo=historico_efetivo,
        consultas_teto_p95=consultas_teto,
        consultas_hoje=consultas_hoje,
        consultas_ocupacao_pct=consultas_pct,
        horas_cadeira_teto_p95=horas_teto,
        horas_cadeira_hoje=horas_hoje,
        horas_cadeira_ocupacao_pct=horas_pct,
        profs_com_folga=profs_com_folga,
        encaixes=encaixes,
        encaixe_total_min=sum(e.duracao_min for e in encaixes),
    )


def _hhmm_to_min(s: str) -> int:
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return 0


def _min_to_hhmm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


# ── Risco de no-show (18g) ──────────────────────────────────────


RISK_HISTORY_DAYS = 90              # janela base
RISK_PATIENT_FULL_WEIGHT = 5        # nº de visitas pra confiança 100% no histórico individual
RISK_NEW_PATIENT_BUMP = 0.20        # 1ª consulta = +20% sobre o baseline
RISK_NO_CONFIRMATION_BUMP = 0.15    # ainda Agendado (sem CONFIRMED) = +15%
RISK_LATE_HISTORY_BUMP = 0.10       # paciente com histórico de atraso = +10%
RISK_HIGH_THRESHOLD = 30            # >= 30% entra na lista de "alto risco"
RISK_TOP_N = 6                      # quantos mostrar no card


async def _risk(
    db: AsyncSession,
    tenant_id: str,
    target_date: date,
    items: list[AgendaItem],
) -> RiskSection:
    """Computa risco de no-show por paciente.

    Heurística sem ML — baseline da clínica + taxa pessoal × peso de confiança.
    Pacientes com poucos dados (< 5 visitas) são puxados pro baseline.
    Ajustes adicionais: 1ª consulta, sem confirmação, histórico de atraso.

    Mutação: popula `risco_pct` e `risco_razao` em `items` (in-place) pra
    a matriz mostrar o badge no chip.
    """
    since = target_date - timedelta(days=RISK_HISTORY_DAYS)

    # ── 1. Baseline da clínica (% MISSED dentre os finalizados) ──
    base_q = await db.execute(
        text("""
            SELECT
              SUM(status_type = 'MISSED') AS faltou,
              SUM(status_type = 'CHECKOUT') AS atendido
            FROM fato_agenda
            WHERE tenant_id = :tid
              AND is_canceled = 0
              AND date_key BETWEEN :since AND :until
              AND status_type IN ('MISSED', 'CHECKOUT')
        """),
        {"tid": tenant_id, "since": since, "until": target_date},
    )
    base_row = base_q.one_or_none()
    faltou = int(base_row.faltou or 0) if base_row else 0
    atendido = int(base_row.atendido or 0) if base_row else 0
    base_total = faltou + atendido
    baseline = (faltou / base_total) if base_total > 0 else 0.0

    # IDs dos pacientes do dia (apenas os identificados)
    pids = [it.paciente_external_id for it in items if it.paciente_external_id is not None]
    pids_unique = list({pid for pid in pids if pid is not None})

    # ── 2. Histórico por paciente do dia ─────────────────────────
    hist_map: dict[int, dict] = {}
    if pids_unique:
        # MySQL aceita IN com lista grande mas vamos chunk por segurança
        chunk = 500
        for i in range(0, len(pids_unique), chunk):
            batch = pids_unique[i:i + chunk]
            placeholders = ",".join([f":pid_{j}" for j in range(len(batch))])
            params = {f"pid_{j}": p for j, p in enumerate(batch)}
            params["tid"] = tenant_id
            params["target"] = target_date
            q = await db.execute(
                text(f"""
                    SELECT
                      patient_external_id,
                      COUNT(*) AS total,
                      SUM(status_type = 'MISSED') AS faltou,
                      SUM(status_type = 'CHECKOUT') AS atendido,
                      SUM(status_type = 'LATE') AS atrasou
                    FROM fato_agenda
                    WHERE tenant_id = :tid
                      AND is_canceled = 0
                      AND date_key < :target
                      AND patient_external_id IN ({placeholders})
                      AND status_type IN ('MISSED', 'CHECKOUT', 'LATE')
                    GROUP BY patient_external_id
                """),
                params,
            )
            for row in q.all():
                hist_map[int(row.patient_external_id)] = {
                    "total": int(row.total or 0),
                    "faltou": int(row.faltou or 0),
                    "atendido": int(row.atendido or 0),
                    "atrasou": int(row.atrasou or 0),
                }

    # ── 3. Calcula risco de cada item ────────────────────────────
    avaliadas = 0
    soma_risco = 0.0
    altos: list[RiskTopPatient] = []

    for it in items:
        pid = it.paciente_external_id
        if pid is None:
            continue
        # Não tenta avaliar se já foi resolvido — quem chegou ou foi atendido
        # já não é incerto; quem faltou é fato.
        if it.status_type in ("CHECKOUT", "ARRIVED", "IN_SESSION", "MISSED", "LATE"):
            continue

        h = hist_map.get(pid)
        total_h = h["total"] if h else 0
        faltou_h = h["faltou"] if h else 0
        atrasou_h = h["atrasou"] if h else 0

        # Taxa pessoal de no-show (entre as consultas finalizadas)
        finalizadas = (h["faltou"] + h["atendido"]) if h else 0
        taxa_pessoal = (faltou_h / finalizadas) if finalizadas > 0 else 0.0

        # Peso da experiência: 0 quando sem histórico, 1.0 quando >= 5
        peso = min(1.0, total_h / RISK_PATIENT_FULL_WEIGHT)
        risco = baseline * (1 - peso) + taxa_pessoal * peso

        razoes: list[str] = []
        if total_h == 0:
            risco += RISK_NEW_PATIENT_BUMP
            razoes.append("1ª consulta")
        else:
            razoes.append(f"Faltou {faltou_h} de {finalizadas}")

        if atrasou_h > 0:
            risco += RISK_LATE_HISTORY_BUMP
            razoes.append(f"{atrasou_h} atraso{'s' if atrasou_h > 1 else ''}")

        if it.status_type is None:  # Agendado, sem confirmar
            risco += RISK_NO_CONFIRMATION_BUMP
            razoes.append("não confirmou")

        risco = max(0.0, min(1.0, risco))
        risco_pct = int(round(risco * 100))
        razao = " · ".join(razoes[:2])  # primeiras 2 razões

        it.risco_pct = risco_pct
        it.risco_razao = razao
        avaliadas += 1
        soma_risco += risco

        if risco_pct >= RISK_HIGH_THRESHOLD:
            altos.append(RiskTopPatient(
                paciente_external_id=pid,
                paciente_nome=it.paciente_nome,
                horario=it.horario,
                profissional_nome=it.profissional_nome,
                risco_pct=risco_pct,
                no_show_rate_pct=int(round(taxa_pessoal * 100)),
                total_historico=total_h,
                razao=razao,
            ))

    # Ordena alto risco por % desc
    altos.sort(key=lambda r: r.risco_pct, reverse=True)

    # Intervalo esperado de faltas: ±20% sobre a soma
    faltas_esp = soma_risco
    faltas_min = max(0, int(round(faltas_esp * 0.8)))
    faltas_max = int(round(faltas_esp * 1.2))

    return RiskSection(
        historico_dias=RISK_HISTORY_DAYS,
        baseline_pct=int(round(baseline * 100)),
        consultas_avaliadas=avaliadas,
        faltas_esperadas_min=faltas_min,
        faltas_esperadas_max=faltas_max,
        pacientes_alto_risco=altos[:RISK_TOP_N],
    )


# ── Agenda ──────────────────────────────────────────────────────


async def _agenda(
    db: AsyncSession,
    tenant_id: str,
    today: date,
    now_local: datetime,
    target_date: date | None = None,
) -> AgendaSection:
    """Agenda de um dia. Se `target_date` for passado, usa exatamente ele
    (sem fallback) — caso de uso do seletor Hoje/Amanhã. Se None, mantém
    comportamento legado: tenta hoje, faz fallback pro próximo dia com
    dados nos 7d seguintes (HomePage exibe sempre algo útil).

    is_today reflete se a data exibida bate com `today` (relógio local do
    tenant), independente de ter sido escolhida explicitamente ou via
    fallback.
    """
    if target_date is not None:
        target = target_date
        is_today = (target_date == today)
    else:
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
                fa.category_group,
                fa.status_type,
                fa.status_description,
                fa.status_color,
                COALESCE(NULLIF(fa.category_description, ''), 'Sem categoria') AS categoria,
                MAX(dp.name) AS paciente_nome,
                MAX(dp.birth_date) AS paciente_birth_date,
                MAX(dp.gender) AS paciente_gender,
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
                     fa.appointment_datetime, fa.duration_minutes, fa.category_color,
                     fa.category_description, fa.category_group,
                     fa.status_type, fa.status_description, fa.status_color
            ORDER BY fa.appointment_datetime ASC
        """),
        {"tid": tenant_id, "d": target},
    )

    items: List[AgendaItem] = []
    appt_ids: list[str] = []
    for r in items_q.all():
        horario = r.appointment_datetime.strftime("%H:%M") if r.appointment_datetime else None
        items.append(AgendaItem(
            external_id=str(r.external_id),
            paciente_external_id=r.patient_external_id,
            paciente_nome=r.paciente_nome or (f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"),
            paciente_birth_date=r.paciente_birth_date,
            paciente_gender=r.paciente_gender,
            profissional_external_id=r.professional_external_id,
            profissional_nome=r.prof_nome,
            horario=horario,
            categoria=r.categoria,
            category_color=r.category_color,
            category_group=r.category_group,
            duration_minutes=r.duration_minutes,
            status_type=r.status_type,
            status_description=r.status_description,
            status_color=r.status_color,
        ))
        appt_ids.append(str(r.external_id))

    # Tags operacionais (Aguardado vaga, Encaixe, Lembrete...) por appointment.
    # Filtra tag_class != 'outro' pra não poluir UI com tags ad-hoc.
    if appt_ids:
        tags_q = await db.execute(
            text("""
                SELECT appointment_external_id, name, color, tag_class
                FROM core_appointment_tags
                WHERE tenant_id = :tid
                  AND is_deleted = 0
                  AND tag_class IS NOT NULL
                  AND tag_class <> 'outro'
                  AND appointment_external_id IN :ids
                ORDER BY appointment_external_id, tag_class
            """).bindparams(sa_bindparam("ids", expanding=True)),
            {"tid": tenant_id, "ids": appt_ids},
        )
        tags_by_appt: dict[str, list[AppointmentTagBrief]] = {}
        for tr in tags_q.all():
            tags_by_appt.setdefault(str(tr.appointment_external_id), []).append(
                AppointmentTagBrief(name=tr.name or "", color=tr.color, tag_class=tr.tag_class)
            )
        for it in items:
            it.tags = tags_by_appt.get(it.external_id, [])

    occ = 0
    nxt = 0
    for it in items:
        if it.horario:
            h, m = it.horario.split(":")
            slot = now_local.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
            if is_today and slot < now_local:
                occ += 1
            else:
                nxt += 1
        else:
            nxt += 1

    capacity = await _capacity(db, tenant_id, target, items)
    risk = await _risk(db, tenant_id, target, items)  # popula items[i].risco_pct in-place
    waitlist = await _waitlist(db, tenant_id, target)

    return AgendaSection(
        date_iso=target.isoformat(),
        is_today=is_today,
        total=len(items),
        horarios_ocupados=occ,
        proximas=nxt,
        items=items,
        capacity=capacity,
        risk=risk,
        waitlist=waitlist,
    )


# ── Lista de espera (tags Aguardado vaga / Encaixe) ─────────────


async def _waitlist(
    db: AsyncSession, tenant_id: str, target: date,
) -> WaitlistSection:
    """Pacientes com tag 'Aguardado vaga' ou 'Encaixe' no Clinicorp.
    A tag aplica em UM appointment específico (vaga tentativa). Quando o
    Clinicorp marca, geralmente está num horário sobreposto a outro paciente
    OU em horário tentativo.

    Retorna janela de ±7 dias (passado conta como aguardando há mais tempo,
    futuro mostra quem JÁ tem vaga marcada e está na fila).
    """
    sql = text("""
        SELECT
            t.appointment_external_id,
            t.tag_class,
            t.color,
            t.external_updated_at,
            fa.appointment_datetime,
            fa.date_key,
            fa.patient_external_id,
            fa.professional_external_id,
            dp.name AS paciente_nome,
            dpr.name AS prof_nome
        FROM core_appointment_tags t
        JOIN fato_agenda fa
            ON fa.tenant_id = t.tenant_id AND fa.external_id = t.appointment_external_id
        LEFT JOIN dim_paciente dp
            ON dp.tenant_id = fa.tenant_id
           AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
        LEFT JOIN dim_profissional dpr
            ON dpr.tenant_id = fa.tenant_id
           AND CAST(dpr.external_id AS UNSIGNED) = fa.professional_external_id
        WHERE t.tenant_id = :tid
          AND t.is_deleted = 0
          AND t.tag_class IN ('waitlist', 'encaixe')
          AND fa.is_canceled = 0
          AND fa.date_key BETWEEN DATE_SUB(:d, INTERVAL 7 DAY) AND DATE_ADD(:d, INTERVAL 14 DAY)
        ORDER BY t.tag_class, fa.appointment_datetime ASC
    """)
    rows = (await db.execute(sql, {"tid": tenant_id, "d": target})).all()

    # Agrupa por appointment (1 appointment pode ter as 2 tags juntas)
    by_appt: dict[str, dict] = {}
    for r in rows:
        appt = str(r.appointment_external_id)
        if appt not in by_appt:
            by_appt[appt] = {
                "patient_id": r.patient_external_id,
                "patient_name": r.paciente_nome or (
                    f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"
                ),
                "prof_id": r.professional_external_id,
                "prof_name": r.prof_nome,
                "datetime": r.appointment_datetime,
                "date_key": r.date_key,
                "is_waitlist": False,
                "is_encaixe": False,
                "color": r.color,
                "tag_at": r.external_updated_at,
            }
        if r.tag_class == "waitlist":
            by_appt[appt]["is_waitlist"] = True
        elif r.tag_class == "encaixe":
            by_appt[appt]["is_encaixe"] = True

    items: list[WaitlistItem] = []
    waitlist_count = 0
    encaixe_count = 0
    for appt, d in by_appt.items():
        horario = d["datetime"].strftime("%H:%M") if d["datetime"] else None
        dias_aguard = (target - d["tag_at"].date()).days if d["tag_at"] else 0
        if dias_aguard < 0:
            dias_aguard = 0
        items.append(WaitlistItem(
            appointment_external_id=appt,
            paciente_external_id=d["patient_id"],
            paciente_nome=d["patient_name"],
            profissional_external_id=d["prof_id"],
            profissional_nome=d["prof_name"],
            horario=horario,
            appointment_date_iso=d["date_key"].isoformat() if d["date_key"] else "",
            is_waitlist=d["is_waitlist"],
            is_encaixe=d["is_encaixe"],
            dias_aguardando=dias_aguard,
            tag_color=d["color"],
        ))
        if d["is_waitlist"]:
            waitlist_count += 1
        if d["is_encaixe"]:
            encaixe_count += 1

    # Ordena: maior dias_aguardando primeiro, depois mais próximos
    items.sort(key=lambda it: (-it.dias_aguardando, it.appointment_date_iso))

    return WaitlistSection(
        total=len(items),
        waitlist_count=waitlist_count,
        encaixe_count=encaixe_count,
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


# ── Pendências operacionais (tags do Clinicorp) ────────────────


# Classes que representam ação pendente. financeiro_conferido é positivo
# (já conferido), e `outro` é tag ad-hoc que não merece destaque.
_PENDENCIA_CLASSES_ORDER = (
    "orcamento_pendente",
    "retorno_pendente",
    "remarcar",
    "lembrete",
)
_PENDENCIA_CLASS_LABEL = {
    "orcamento_pendente": "Orçamentos a contatar",
    "retorno_pendente": "Retornos pendentes",
    "remarcar": "Remarcações pendentes",
    "lembrete": "Lembretes ativos",
}


async def _pendencias_operacionais(
    db: AsyncSession, tenant_id: str, top_per_bucket: int = 5,
) -> PendenciasOperacionaisSection:
    """Agrega tags de ação pendente em buckets por classe.
    Para cada classe traz top N mais antigos (maior dias_aplicada).
    Considera apenas tags em appointments NÃO cancelados — appointment cancelado
    e que ainda tem tag 'orçamento a contatar' pode ser ruído de banco.
    """
    sql = text("""
        SELECT
            t.appointment_external_id,
            t.name AS tag_name,
            t.tag_class,
            t.external_updated_at AS tag_at,
            fa.appointment_datetime,
            fa.date_key,
            fa.patient_external_id,
            dp.name AS paciente_nome,
            dpr.name AS prof_nome
        FROM core_appointment_tags t
        JOIN fato_agenda fa
            ON fa.tenant_id = t.tenant_id AND fa.external_id = t.appointment_external_id
        LEFT JOIN dim_paciente dp
            ON dp.tenant_id = fa.tenant_id
           AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
        LEFT JOIN dim_profissional dpr
            ON dpr.tenant_id = fa.tenant_id
           AND CAST(dpr.external_id AS UNSIGNED) = fa.professional_external_id
        WHERE t.tenant_id = :tid
          AND t.is_deleted = 0
          AND t.tag_class IN ('orcamento_pendente','retorno_pendente','remarcar','lembrete')
          AND fa.is_canceled = 0
        ORDER BY t.tag_class, t.external_updated_at ASC
    """)
    rows = (await db.execute(sql, {"tid": tenant_id})).all()

    # Agrupa por classe
    by_class: dict[str, list[PendenciaItem]] = {c: [] for c in _PENDENCIA_CLASSES_ORDER}
    counts: dict[str, int] = {c: 0 for c in _PENDENCIA_CLASSES_ORDER}
    today = date.today()
    for r in rows:
        c = r.tag_class
        if c not in by_class:
            continue
        counts[c] += 1
        # Só os top N mais antigos por bucket
        if len(by_class[c]) >= top_per_bucket:
            continue
        dias = (today - r.tag_at.date()).days if r.tag_at else 0
        if dias < 0:
            dias = 0
        by_class[c].append(PendenciaItem(
            appointment_external_id=str(r.appointment_external_id),
            paciente_external_id=r.patient_external_id,
            paciente_nome=r.paciente_nome or (
                f"Paciente #{r.patient_external_id}" if r.patient_external_id else "Sem paciente"
            ),
            profissional_nome=r.prof_nome,
            appointment_date_iso=r.date_key.isoformat() if r.date_key else None,
            horario=r.appointment_datetime.strftime("%H:%M") if r.appointment_datetime else None,
            tag_name=r.tag_name or "",
            tag_class=c,
            dias_aplicada=dias,
        ))

    buckets: list[PendenciaBucket] = []
    for c in _PENDENCIA_CLASSES_ORDER:
        total = counts[c]
        if total > 0:
            buckets.append(PendenciaBucket(
                tag_class=c,
                label=_PENDENCIA_CLASS_LABEL[c],
                total=total,
                items=by_class[c],
            ))
    # Maior bucket primeiro (mais "barulho" pra resolver)
    buckets.sort(key=lambda b: b.total, reverse=True)
    return PendenciasOperacionaisSection(
        total=sum(counts.values()),
        buckets=buckets,
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


async def get_agenda_section(
    db: AsyncSession,
    tenant_id: str,
    now_local: datetime,
    target_date: date | None = None,
) -> AgendaSection:
    """Endpoint dedicado pro seletor de data (Hoje/Amanhã).

    target_date=None → comportamento legado (today + fallback até 7d à frente).
    target_date passada → usa exatamente essa data.
    """
    today = now_local.date()
    return await _agenda(db, tenant_id, today, now_local, target_date=target_date)


async def get_home_dashboard(
    db: AsyncSession,
    tenant_id: str,
    role: str,
    user_full_name: str,
    now_local: datetime | None = None,
) -> HomeDashboardResponse:
    # `now_local` é o relógio do tenant (route resolve via ZoneInfo). Default
    # mantém compatibilidade com chamadas antigas, mas pode ficar errado em
    # servidor UTC após 21h BRT.
    if now_local is None:
        now_local = datetime.now()
    today = now_local.date()

    agenda = await _agenda(db, tenant_id, today, now_local) if _can_see(role, "agenda") else None
    recall = await _recall(db, tenant_id, today) if _can_see(role, "recall") else None
    orc_parados = await _orcamentos_parados(db, tenant_id, today) if _can_see(role, "orcamentos_parados") else None
    inad = await _inadimplencia_critica(db, tenant_id) if _can_see(role, "inadimplencia_critica") else None
    resumo = await _resumo_dia(db, tenant_id, today) if _can_see(role, "resumo_dia") else None
    top_profs = await _top_profs_semana(db, tenant_id, today) if _can_see(role, "top_profs_semana") else None
    pendencias = await _pendencias_operacionais(db, tenant_id) if _can_see(role, "pendencias") else None

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
        pendencias=pendencias,
    )


# ── Strategic overview (HomePage do dono) ──────────────────────


def _summarize_day(label: str, agenda: AgendaSection) -> StrategicDayKPIs:
    """Reduz uma AgendaSection completa em KPIs estratégicos compactos."""
    confirmados = sum(1 for it in agenda.items if it.status_type == "CONFIRMED")
    # Pendentes = ainda incertos (não atendidos, não em curso, não faltaram)
    pendentes = sum(
        1 for it in agenda.items
        if it.status_type not in ("CHECKOUT", "ARRIVED", "IN_SESSION", "MISSED", "LATE")
    )
    confirmados_pct = int(round(100 * confirmados / pendentes)) if pendentes > 0 else 0
    riscos_altos = sum(1 for it in agenda.items if (it.risco_pct or 0) >= 30)
    cap = agenda.capacity
    return StrategicDayKPIs(
        date_iso=agenda.date_iso,
        label=label,
        is_today=agenda.is_today,
        total=agenda.total,
        ocupacao_pct=cap.consultas_ocupacao_pct if cap else 0,
        faltas_esperadas_min=agenda.risk.faltas_esperadas_min if agenda.risk else 0,
        faltas_esperadas_max=agenda.risk.faltas_esperadas_max if agenda.risk else 0,
        confirmados=confirmados,
        confirmados_pct=confirmados_pct,
        riscos_altos=riscos_altos,
        encaixe_min=cap.encaixe_total_min if cap else 0,
        horas_cadeira_hoje=cap.horas_cadeira_hoje if cap else 0,
    )


async def get_strategic_overview(
    db: AsyncSession, tenant_id: str, now_local: datetime,
) -> StrategicOverview:
    """Visão consolidada Hoje + Amanhã + Depois para a HomePage do dono.

    Faz 3 chamadas a _agenda completa (com capacity + risk) — cálculo P95 é
    cacheável em produção; por ora rodamos a cada request. Trade-off aceitável:
    ~3 queries por dia × 3 dias = 9 queries pequenas, dá ~200ms.
    """
    today = now_local.date()
    labels = [("Hoje", 0), ("Amanhã", 1), ("Depois", 2)]

    days: list[StrategicDayKPIs] = []
    profs_acc: dict[int, CapacityProfBucket] = {}  # menor ocupação por prof
    riscos_acc: dict[int, RiskTopPatient] = {}     # maior risco por paciente
    baseline_pct = 0
    waitlist_acc = 0
    encaixe_acc = 0

    for label, offset in labels:
        target = today + timedelta(days=offset)
        agenda = await _agenda(db, tenant_id, today, now_local, target_date=target)
        days.append(_summarize_day(label, agenda))

        # Acumula profs ociosos (mantém o de menor ocupação se prof aparece em vários dias)
        if agenda.capacity:
            for p in agenda.capacity.profs_com_folga:
                cur = profs_acc.get(p.professional_external_id)
                if cur is None or p.ocupacao_pct < cur.ocupacao_pct:
                    profs_acc[p.professional_external_id] = p

        # Acumula riscos altos (mantém maior risco se paciente em vários dias)
        if agenda.risk:
            baseline_pct = max(baseline_pct, agenda.risk.baseline_pct)
            for r in agenda.risk.pacientes_alto_risco:
                cur = riscos_acc.get(r.paciente_external_id)
                if cur is None or r.risco_pct > cur.risco_pct:
                    riscos_acc[r.paciente_external_id] = r

        # Waitlist do dia (cada agenda já carrega a janela ±7/+14 — somar geraria
        # duplicação. Em vez disso, contamos só itens cuja appointment_date_iso
        # cai exatamente no dia consultado.)
        if agenda.waitlist:
            for w in agenda.waitlist.items:
                if w.appointment_date_iso == target.isoformat():
                    if w.is_waitlist:
                        waitlist_acc += 1
                    if w.is_encaixe:
                        encaixe_acc += 1

    top_profs = sorted(profs_acc.values(), key=lambda p: p.ocupacao_pct)[:5]
    top_riscos = sorted(riscos_acc.values(), key=lambda r: r.risco_pct, reverse=True)[:5]

    return StrategicOverview(
        days=days,
        total_3d=sum(d.total for d in days),
        faltas_esperadas_3d_min=sum(d.faltas_esperadas_min for d in days),
        faltas_esperadas_3d_max=sum(d.faltas_esperadas_max for d in days),
        encaixe_total_3d_min=sum(d.encaixe_min for d in days),
        waitlist_3d=waitlist_acc,
        encaixe_3d=encaixe_acc,
        top_pacientes_risco=top_riscos,
        top_profs_ociosos=top_profs,
        baseline_pct=baseline_pct,
    )
