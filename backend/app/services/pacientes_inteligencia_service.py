"""
Inteligência de Pacientes — agrega 6 visões analíticas numa única tela.

Endpoint público: GET /analise/pacientes/inteligencia?days=90

Visões:
1. **Acurácia preditiva**  — backtest da heurística de risco em `home_service._risk`.
   Recomputa o score pra cada appointment finalizado nos últimos N dias usando
   APENAS dados anteriores à data do compromisso (sem vazamento). Cruza com
   `is_falta` pra medir precisão/recall.

2. **Top faltosos**         — ranking dos pacientes com mais MISSED no período.

3. **Curva de retenção**    — % pacientes cuja 1ª consulta foi há ≥ X dias
   e que voltaram dentro da janela X (X ∈ {30,60,90,180,365}).

4. **Risco de evasão**      — pacientes ativos (≥3 visitas em 12m) sem voltar há >90d.

5. **Heatmap no-show**      — taxa de falta por (dia da semana × hora).

6. **Eficácia da confirmação** — compara no-show entre `has_lembrete=1/0`.

Convenções:
- Backtest exclui o próprio compromisso da janela histórica (`date_key < target`).
- Status considerados "finalizados": MISSED, CHECKOUT, LATE.
- LATE conta como "veio" no backtest (foi atendido, só atrasou).
- Limitação: `RISK_NO_CONFIRMATION_BUMP` não se aplica no backtest (não temos
  histórico de qual era o status_type no momento da predição).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.pacientes_inteligencia import (
    AcuraciaBucket,
    AcuraciaPaciente,
    AcuraciaSection,
    EficaciaConfirmacao,
    EvasaoPaciente,
    HeatmapCelula,
    HeatmapSection,
    InteligenciaPacientesResponse,
    RetencaoBucket,
    RetencaoSection,
    TopFaltosoItem,
)


# Constantes alinhadas ao home_service._risk
RISK_HISTORY_DAYS = 90
RISK_PATIENT_FULL_WEIGHT = 5
RISK_NEW_PATIENT_BUMP = 0.20
RISK_LATE_HISTORY_BUMP = 0.10
RISK_HIGH_THRESHOLD = 30
RISK_MEDIUM_THRESHOLD = 15

RETENCAO_JANELAS = [30, 60, 90, 180, 365]
EVASAO_DIAS_LIMIAR = 90
EVASAO_VISITAS_MIN = 3
EVASAO_TOP_N = 30
TOP_FALTOSOS_N = 20


# ── Helpers ───────────────────────────────────────────────────────


def _bucket_for(risco_pct: int) -> str:
    if risco_pct >= RISK_HIGH_THRESHOLD:
        return "alto"
    if risco_pct >= RISK_MEDIUM_THRESHOLD:
        return "medio"
    return "baixo"


def _safe_pct(num: int, den: int) -> int:
    if den <= 0:
        return 0
    return int(round((num / den) * 100))


# ── 1. Acurácia preditiva (backtest) ──────────────────────────────


async def _backtest_acuracia(
    db: AsyncSession,
    tenant_id: str,
    today: date,
    days: int,
) -> AcuraciaSection:
    """Recomputa risco pra cada appointment finalizado nos últimos `days` dias.

    Estratégia: 1 query carrega TUDO (período + janela histórica de 90d
    anterior). Em Python, separa "avaliar" vs "histórico" e aplica a fórmula
    de `home_service._risk` usando apenas dados com `date_key < target`.
    """
    since_avaliar = today - timedelta(days=days)
    since_total = since_avaliar - timedelta(days=RISK_HISTORY_DAYS)

    q = await db.execute(
        text("""
            SELECT
              fa.patient_external_id,
              fa.date_key,
              fa.status_type,
              fa.is_falta,
              COALESCE(dp.name, CONCAT('Paciente #', fa.patient_external_id)) AS paciente_nome
            FROM fato_agenda fa
            LEFT JOIN dim_paciente dp
              ON dp.tenant_id = fa.tenant_id
             AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            WHERE fa.tenant_id = :tid
              AND fa.is_canceled = 0
              AND fa.date_key BETWEEN :since_total AND :today
              AND fa.status_type IN ('MISSED', 'CHECKOUT', 'LATE')
              AND fa.patient_external_id IS NOT NULL
            ORDER BY fa.patient_external_id, fa.date_key
        """),
        {"tid": tenant_id, "since_total": since_total, "today": today},
    )
    rows = q.all()

    # Agrupa por paciente, mantendo ordem temporal
    por_paciente: dict[int, list[tuple]] = defaultdict(list)
    for r in rows:
        por_paciente[int(r.patient_external_id)].append((
            r.date_key, r.status_type, int(r.is_falta or 0), r.paciente_nome,
        ))

    # Baseline geral (taxa de falta) nos últimos 90d ANTES do período de avaliação
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
        {
            "tid": tenant_id,
            "since": since_total,
            "until": since_avaliar,
        },
    )
    base_row = base_q.one_or_none()
    base_faltou = int(base_row.faltou or 0) if base_row else 0
    base_atendido = int(base_row.atendido or 0) if base_row else 0
    base_total = base_faltou + base_atendido
    baseline = (base_faltou / base_total) if base_total > 0 else 0.0

    # Pra cada paciente, varre os appointments e avalia os que caem no período
    avaliados: list[AcuraciaPaciente] = []
    for pid, lista in por_paciente.items():
        for idx, (dk, status, is_falta, nome) in enumerate(lista):
            if dk < since_avaliar:
                continue  # serve só como histórico

            # Histórico = tudo do paciente com date_key < dk (mesmo dia não conta)
            hist_total = 0
            hist_faltou = 0
            hist_atendido = 0
            hist_atrasou = 0
            for (d2, s2, _, _) in lista[:idx]:
                if d2 >= dk:
                    break
                hist_total += 1
                if s2 == "MISSED":
                    hist_faltou += 1
                elif s2 == "CHECKOUT":
                    hist_atendido += 1
                elif s2 == "LATE":
                    hist_atrasou += 1

            # Mesma fórmula do home_service._risk
            finalizadas = hist_faltou + hist_atendido
            taxa_pessoal = (hist_faltou / finalizadas) if finalizadas > 0 else 0.0
            peso = min(1.0, hist_total / RISK_PATIENT_FULL_WEIGHT)
            risco = baseline * (1 - peso) + taxa_pessoal * peso

            razoes: list[str] = []
            if hist_total == 0:
                risco += RISK_NEW_PATIENT_BUMP
                razoes.append("1ª consulta")
            else:
                razoes.append(f"Faltou {hist_faltou} de {finalizadas}")
            if hist_atrasou > 0:
                risco += RISK_LATE_HISTORY_BUMP
                razoes.append(f"{hist_atrasou} atraso{'s' if hist_atrasou > 1 else ''}")
            # RISK_NO_CONFIRMATION_BUMP não é simulável no backtest (sem snapshot
            # do status_type no momento da predição)

            risco = max(0.0, min(1.0, risco))
            risco_pct = int(round(risco * 100))
            bucket = _bucket_for(risco_pct)

            avaliados.append(AcuraciaPaciente(
                paciente_external_id=pid,
                paciente_nome=nome,
                data=dk,
                risco_pct=risco_pct,
                bucket=bucket,
                razao=" · ".join(razoes[:2]),
                realmente_faltou=bool(is_falta),
            ))

    # Estatísticas agregadas
    total = len(avaliados)
    if total == 0:
        return AcuraciaSection(
            appointments_avaliados=0,
            baseline_pct=int(round(baseline * 100)),
            acuracia_pct=0,
            precisao_alto_pct=0,
            recall_alto_pct=0,
            buckets=[
                AcuraciaBucket(bucket=b, total=0, faltou=0, veio=0, taxa_falta_pct=0)
                for b in ("alto", "medio", "baixo")
            ],
            matriz=[[0, 0, 0], [0, 0, 0]],
            acertos_alto_risco=[],
            escapes=[],
        )

    counts = defaultdict(lambda: {"total": 0, "faltou": 0, "veio": 0})
    for a in avaliados:
        c = counts[a.bucket]
        c["total"] += 1
        if a.realmente_faltou:
            c["faltou"] += 1
        else:
            c["veio"] += 1

    buckets_out = [
        AcuraciaBucket(
            bucket=b,
            total=counts[b]["total"],
            faltou=counts[b]["faltou"],
            veio=counts[b]["veio"],
            taxa_falta_pct=_safe_pct(counts[b]["faltou"], counts[b]["total"]),
        )
        for b in ("alto", "medio", "baixo")
    ]

    # Matriz 2x3: linhas [faltou, veio] × colunas [alto, medio, baixo]
    matriz = [
        [counts["alto"]["faltou"], counts["medio"]["faltou"], counts["baixo"]["faltou"]],
        [counts["alto"]["veio"],   counts["medio"]["veio"],   counts["baixo"]["veio"]],
    ]

    # Acertos = predito alto + faltou (true positive) + medio/baixo + veio (true negative)
    acertos = counts["alto"]["faltou"] + counts["medio"]["veio"] + counts["baixo"]["veio"]
    acuracia = _safe_pct(acertos, total)

    alto_total = counts["alto"]["total"]
    total_faltou = sum(c["faltou"] for c in counts.values())
    precisao_alto = _safe_pct(counts["alto"]["faltou"], alto_total)
    recall_alto = _safe_pct(counts["alto"]["faltou"], total_faltou)

    acertos_alto = sorted(
        [a for a in avaliados if a.bucket == "alto" and a.realmente_faltou],
        key=lambda x: (-x.risco_pct, x.data),
    )[:30]
    escapes = sorted(
        [a for a in avaliados if a.realmente_faltou and a.bucket in ("medio", "baixo")],
        key=lambda x: x.data,
        reverse=True,
    )[:30]

    return AcuraciaSection(
        appointments_avaliados=total,
        baseline_pct=int(round(baseline * 100)),
        acuracia_pct=acuracia,
        precisao_alto_pct=precisao_alto,
        recall_alto_pct=recall_alto,
        buckets=buckets_out,
        matriz=matriz,
        acertos_alto_risco=acertos_alto,
        escapes=escapes,
    )


# ── 2. Top faltosos ────────────────────────────────────────────────


async def _top_faltosos(
    db: AsyncSession,
    tenant_id: str,
    today: date,
    days: int,
) -> list[TopFaltosoItem]:
    since = today - timedelta(days=days)
    q = await db.execute(
        text("""
            SELECT
              fa.patient_external_id,
              COALESCE(dp.name, CONCAT('Paciente #', fa.patient_external_id)) AS paciente_nome,
              SUM(fa.status_type = 'MISSED') AS faltas,
              SUM(fa.status_type IN ('CHECKOUT', 'LATE')) AS atendimentos,
              COUNT(*) AS total,
              MAX(CASE WHEN fa.status_type = 'MISSED' THEN fa.date_key END) AS ultima_falta
            FROM fato_agenda fa
            LEFT JOIN dim_paciente dp
              ON dp.tenant_id = fa.tenant_id
             AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            WHERE fa.tenant_id = :tid
              AND fa.is_canceled = 0
              AND fa.date_key BETWEEN :since AND :today
              AND fa.status_type IN ('MISSED', 'CHECKOUT', 'LATE')
              AND fa.patient_external_id IS NOT NULL
            GROUP BY fa.patient_external_id, paciente_nome
            HAVING faltas > 0
            ORDER BY faltas DESC, faltas / NULLIF(total, 0) DESC
            LIMIT :limit
        """),
        {"tid": tenant_id, "since": since, "today": today, "limit": TOP_FALTOSOS_N},
    )
    out: list[TopFaltosoItem] = []
    for r in q.all():
        total = int(r.total or 0)
        faltas = int(r.faltas or 0)
        out.append(TopFaltosoItem(
            paciente_external_id=int(r.patient_external_id),
            paciente_nome=r.paciente_nome,
            faltas=faltas,
            atendimentos=int(r.atendimentos or 0),
            total=total,
            taxa_falta_pct=_safe_pct(faltas, total),
            ultima_falta=r.ultima_falta,
        ))
    return out


# ── 3. Curva de retenção ──────────────────────────────────────────


async def _retencao(
    db: AsyncSession,
    tenant_id: str,
    today: date,
) -> RetencaoSection:
    """Pra cada janela X, conta pacientes cuja 1ª consulta foi há ≥ X dias e
    que voltaram dentro de X dias da primeira visita.

    Considera apenas appointments CHECKOUT/LATE (efetivos) na determinação da
    1ª visita — alguém marcou e faltou na primeira não conta como "novo".
    """
    buckets: list[RetencaoBucket] = []

    for janela in RETENCAO_JANELAS:
        cutoff = today - timedelta(days=janela)
        q = await db.execute(
            text("""
                WITH primeira AS (
                  SELECT
                    patient_external_id,
                    MIN(date_key) AS first_dk
                  FROM fato_agenda
                  WHERE tenant_id = :tid
                    AND is_canceled = 0
                    AND status_type IN ('CHECKOUT', 'LATE')
                    AND patient_external_id IS NOT NULL
                  GROUP BY patient_external_id
                  HAVING first_dk <= :cutoff
                )
                SELECT
                  COUNT(*) AS elegiveis,
                  SUM(EXISTS (
                    SELECT 1 FROM fato_agenda fa2
                    WHERE fa2.tenant_id = :tid
                      AND fa2.patient_external_id = p.patient_external_id
                      AND fa2.is_canceled = 0
                      AND fa2.status_type IN ('CHECKOUT', 'LATE')
                      AND fa2.date_key > p.first_dk
                      AND fa2.date_key <= DATE_ADD(p.first_dk, INTERVAL :janela DAY)
                  )) AS retornaram
                FROM primeira p
            """),
            {"tid": tenant_id, "cutoff": cutoff, "janela": janela},
        )
        row = q.one_or_none()
        elegiveis = int(row.elegiveis or 0) if row else 0
        retornaram = int(row.retornaram or 0) if row else 0
        buckets.append(RetencaoBucket(
            janela_dias=janela,
            elegiveis=elegiveis,
            retornaram=retornaram,
            taxa_pct=_safe_pct(retornaram, elegiveis),
        ))

    return RetencaoSection(buckets=buckets)


# ── 4. Risco de evasão ────────────────────────────────────────────


async def _evasao(
    db: AsyncSession,
    tenant_id: str,
    today: date,
) -> list[EvasaoPaciente]:
    """Pacientes com ≥3 visitas finalizadas em 12m mas sem voltar há >90d.

    Ordena pelos mais antigos sem voltar (pior caso).
    """
    ano_atras = today - timedelta(days=365)
    limite_ultima = today - timedelta(days=EVASAO_DIAS_LIMIAR)

    q = await db.execute(
        text("""
            SELECT
              fa.patient_external_id,
              COALESCE(dp.name, CONCAT('Paciente #', fa.patient_external_id)) AS paciente_nome,
              COUNT(*) AS visitas_12m,
              MAX(fa.date_key) AS ultima_visita
            FROM fato_agenda fa
            LEFT JOIN dim_paciente dp
              ON dp.tenant_id = fa.tenant_id
             AND CAST(dp.external_id AS UNSIGNED) = fa.patient_external_id
            WHERE fa.tenant_id = :tid
              AND fa.is_canceled = 0
              AND fa.date_key BETWEEN :ano_atras AND :today
              AND fa.status_type IN ('CHECKOUT', 'LATE')
              AND fa.patient_external_id IS NOT NULL
            GROUP BY fa.patient_external_id, paciente_nome
            HAVING visitas_12m >= :min_visitas AND MAX(fa.date_key) < :limite_ultima
            ORDER BY MAX(fa.date_key) ASC
            LIMIT :limit
        """),
        {
            "tid": tenant_id,
            "ano_atras": ano_atras,
            "today": today,
            "min_visitas": EVASAO_VISITAS_MIN,
            "limite_ultima": limite_ultima,
            "limit": EVASAO_TOP_N,
        },
    )
    out: list[EvasaoPaciente] = []
    for r in q.all():
        ultima = r.ultima_visita
        out.append(EvasaoPaciente(
            paciente_external_id=int(r.patient_external_id),
            paciente_nome=r.paciente_nome,
            visitas_12m=int(r.visitas_12m or 0),
            ultima_visita=ultima,
            dias_sem_voltar=(today - ultima).days,
        ))
    return out


# ── 5. Heatmap no-show ────────────────────────────────────────────


async def _heatmap(
    db: AsyncSession,
    tenant_id: str,
    today: date,
    days: int,
) -> HeatmapSection:
    since = today - timedelta(days=days)
    q = await db.execute(
        text("""
            SELECT
              WEEKDAY(fa.date_key) AS dow,
              HOUR(fa.appointment_datetime) AS hora,
              COUNT(*) AS total,
              SUM(fa.status_type = 'MISSED') AS faltas
            FROM fato_agenda fa
            WHERE fa.tenant_id = :tid
              AND fa.is_canceled = 0
              AND fa.date_key BETWEEN :since AND :today
              AND fa.status_type IN ('MISSED', 'CHECKOUT', 'LATE')
              AND fa.appointment_datetime IS NOT NULL
            GROUP BY dow, hora
            ORDER BY dow, hora
        """),
        {"tid": tenant_id, "since": since, "today": today},
    )
    celulas: list[HeatmapCelula] = []
    total_global = 0
    faltas_global = 0
    for r in q.all():
        total = int(r.total or 0)
        faltas = int(r.faltas or 0)
        total_global += total
        faltas_global += faltas
        celulas.append(HeatmapCelula(
            dow=int(r.dow),
            hora=int(r.hora),
            total=total,
            faltas=faltas,
            taxa_falta_pct=_safe_pct(faltas, total),
        ))
    return HeatmapSection(
        celulas=celulas,
        total_global=total_global,
        faltas_global=faltas_global,
    )


# ── 6. Eficácia da confirmação ────────────────────────────────────


async def _eficacia_confirmacao(
    db: AsyncSession,
    tenant_id: str,
    today: date,
    days: int,
) -> EficaciaConfirmacao:
    since = today - timedelta(days=days)
    q = await db.execute(
        text("""
            SELECT
              has_lembrete,
              COUNT(*) AS total,
              SUM(status_type = 'MISSED') AS faltas
            FROM fato_agenda
            WHERE tenant_id = :tid
              AND is_canceled = 0
              AND date_key BETWEEN :since AND :today
              AND status_type IN ('MISSED', 'CHECKOUT', 'LATE')
            GROUP BY has_lembrete
        """),
        {"tid": tenant_id, "since": since, "today": today},
    )
    com_total = com_faltas = sem_total = sem_faltas = 0
    for r in q.all():
        if int(r.has_lembrete or 0) == 1:
            com_total = int(r.total or 0)
            com_faltas = int(r.faltas or 0)
        else:
            sem_total = int(r.total or 0)
            sem_faltas = int(r.faltas or 0)

    com_pct = _safe_pct(com_faltas, com_total)
    sem_pct = _safe_pct(sem_faltas, sem_total)
    total_geral = com_total + sem_total

    return EficaciaConfirmacao(
        com_lembrete_total=com_total,
        com_lembrete_faltas=com_faltas,
        com_lembrete_taxa_pct=com_pct,
        sem_lembrete_total=sem_total,
        sem_lembrete_faltas=sem_faltas,
        sem_lembrete_taxa_pct=sem_pct,
        diferenca_pp=sem_pct - com_pct,
        cobertura_lembrete_pct=_safe_pct(com_total, total_geral),
    )


# ── Orquestrador ──────────────────────────────────────────────────


async def get_inteligencia_pacientes(
    db: AsyncSession,
    tenant_id: str,
    days: int = 90,
) -> InteligenciaPacientesResponse:
    today = date.today()

    acuracia = await _backtest_acuracia(db, tenant_id, today, days)
    top_falt = await _top_faltosos(db, tenant_id, today, days)
    retencao = await _retencao(db, tenant_id, today)
    evasao = await _evasao(db, tenant_id, today)
    heatmap = await _heatmap(db, tenant_id, today, days)
    eficacia = await _eficacia_confirmacao(db, tenant_id, today, days)

    return InteligenciaPacientesResponse(
        periodo_dias=days,
        gerado_em=datetime.now(),
        acuracia=acuracia,
        top_faltosos=top_falt,
        retencao=retencao,
        evasao_risco=evasao,
        heatmap=heatmap,
        eficacia_confirmacao=eficacia,
    )
