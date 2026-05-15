"""
SonIA-Insight — geração de insights narrativos via DeepSeek.

Arquitetura:
- Backend roteador por `page_key`. Cada página suportada tem um "snapshot
  builder" que extrai do response do dashboard só os números essenciais
  (não manda o JSON inteiro pra IA — economiza tokens).
- Snapshot vai pro prompt da DeepSeek com persona SonIA + schema de
  output obrigatório (JSON). Resposta volta como `SonIAInsightDTO`.
- Fallback: se DeepSeek não está configurada OU falhar, **retorna None**
  e o frontend cai pra sua heurística local (não usamos heurística
  redundante aqui).

Páginas suportadas (incrementais):
- ✅ /analise/financeiro
- ⏳ outras serão adicionadas conforme testarmos

Persona SonIA (consistente em todas as páginas):
- Mulher de ~30 anos, doce, discreta, cordial, gentil
- Tom: sugestão > ordem; verbos suaves (notei, reparei, encontrei)
- Sem jargão corporativo; sem alarmismo
- Saudação cordial sempre ("Oi, {nome}." quando há nome)
"""
from __future__ import annotations

import json
import logging
import random
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.deepseek import DeepSeekClient, DeepSeekError
from app.schemas.sonia_insight import SonIABulletDTO, SonIAInsightDTO

logger = logging.getLogger(__name__)


# Páginas que o backend sabe analisar com IA. Outras retornam None → frontend
# usa heurística local.
_SUPPORTED_PAGES = {
    "/analise/financeiro",
    "/analise/comercial",
    "/financeiro",
    "/financeiro/dre",
    "/pacientes",
    "/agenda",
    "/",  # MY-Analisys (home customizada) — exige user_id pra ler layout do user
    "/marketing/visao-geral",  # painel executivo Meta (Sub-PR 21e+)
}


async def generate_insight(
    db: AsyncSession,
    *,
    tenant_id: str,
    page_key: str,
    year: int,
    month: int,
    user_first_name: Optional[str] = None,
    clinic_name: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[SonIAInsightDTO]:
    """
    Gera insight da SonIA pra (page_key, year, month).

    Roteamento de provedores (em ordem de preferência):
    1. DeepSeek (DEEPSEEK_API_KEY configurada) — mais barato, padrão
    2. Claude/Anthropic (ANTHROPIC_API_KEY configurada) — fallback temporário
    3. Nenhum provedor disponível → retorna None (frontend usa heurística local)

    Caller (route): tratar None como 404 com mensagem amigável.
    """
    if page_key not in _SUPPORTED_PAGES:
        logger.debug("page_key %s ainda não suportado pela IA backend", page_key)
        return None

    snapshot = await _build_snapshot(db, tenant_id, page_key, year, month, user_id=user_id)
    if snapshot is None:
        return None

    user_prompt = _build_user_prompt(page_key, snapshot, user_first_name, clinic_name)

    # 1) DeepSeek (preferido)
    ds = DeepSeekClient()
    if ds.is_configured:
        try:
            payload = await ds.complete_json(
                system=_SYSTEM_PROMPT, user=user_prompt,
                temperature=0.3, max_tokens=1200,
            )
            return _payload_to_dto(payload, source="DeepSeek")
        except DeepSeekError as e:
            logger.warning("DeepSeek falhou em %s/%d-%d: %s — tentando Claude", page_key, year, month, e)

    # 2) Claude (fallback)
    if settings.ANTHROPIC_API_KEY:
        try:
            payload = await _call_claude(system=_SYSTEM_PROMPT, user=user_prompt)
            model_short = settings.ANTHROPIC_MODEL.split("-")
            label = f"Claude {model_short[1].capitalize()}" if len(model_short) > 1 else "Claude"
            return _payload_to_dto(payload, source=label)
        except Exception as e:
            logger.warning("Claude falhou em %s/%d-%d: %s — frontend cai pra heurística", page_key, year, month, e)

    # 3) Nada disponível
    logger.info("Nenhum provedor de IA configurado — frontend deve usar fallback heurístico")
    return None


_VALID_TONES = {"neutral", "positive", "negative", "warning"}
_VALID_MOODS = {"default", "thinking", "alert", "happy", "curious"}

# Mapas de sanitização — IA às vezes inventa palavras próximas. Mapeamos pro
# vocabulário válido pra evitar falha de validação Pydantic.
_TONE_ALIASES = {
    "curious": "neutral", "info": "neutral", "informative": "neutral",
    "ok": "positive", "good": "positive", "success": "positive", "great": "positive",
    "bad": "negative", "error": "negative", "critical": "negative", "danger": "negative",
    "caution": "warning", "alert": "warning", "attention": "warning",
}
_MOOD_ALIASES = {
    "neutral": "default", "positive": "happy", "negative": "alert", "warning": "alert",
}


def _payload_to_dto(payload: dict[str, Any], *, source: str) -> Optional[SonIAInsightDTO]:
    """Valida e converte o JSON da IA pra DTO. Retorna None se vier malformado.

    Sanitiza tones/moods inválidos via aliases — mais robusto que confiar 100%
    no prompt (LLMs ocasionalmente inventam vocabulário próximo).
    """
    def _safe_tone(t: Any) -> str:
        s = (str(t) if t is not None else "neutral").strip().lower()
        if s in _VALID_TONES:
            return s
        return _TONE_ALIASES.get(s, "neutral")

    def _safe_mood(m: Any) -> str:
        s = (str(m) if m is not None else "default").strip().lower()
        if s in _VALID_MOODS:
            return s
        return _MOOD_ALIASES.get(s, "default")

    try:
        return SonIAInsightDTO(
            mood=_safe_mood(payload.get("mood")),
            headline=(payload.get("headline") or "").strip(),
            detail=(payload.get("detail") or "").strip(),
            bullets=[
                SonIABulletDTO(text=(b.get("text") or "").strip(), tone=_safe_tone(b.get("tone")))
                for b in (payload.get("bullets") or [])
                if b.get("text")
            ],
            cta_href=payload.get("cta_href"),
            cta_label=payload.get("cta_label"),
            source=source,
        )
    except Exception as e:  # pragma: no cover — defesa contra JSON estranho
        logger.warning("Payload inválido do provedor (%s): %s", source, e)
        return None


async def _call_claude(*, system: str, user: str) -> dict[str, Any]:
    """
    Chama Claude (Anthropic) com o mesmo prompt. Força JSON via prompt
    explícito + parse robusto (Claude às vezes envolve em ```json ... ```).
    Modelo: settings.ANTHROPIC_MODEL (Haiku 4.5 atual).

    Atenção: Haiku é fraco em análise numérica. Aceitável só como fallback
    temporário até DEEPSEEK_API_KEY estar configurada.
    """
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=800,
        system=system + "\n\nIMPORTANTE: Retorne APENAS o JSON, sem markdown, sem ```json, sem texto antes ou depois.",
        messages=[{"role": "user", "content": user}],
    )

    text = response.content[0].text.strip()  # type: ignore[union-attr]

    # Defesa: Claude às vezes envolve em fences mesmo quando dizemos pra não
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text[3:]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()

    return json.loads(text)


# ── Snapshot builders ───────────────────────────────────────────


async def _build_snapshot(
    db: AsyncSession, tenant_id: str, page_key: str, year: int, month: int,
    *, user_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Roteador: chama o builder certo pra cada page_key suportado."""
    if page_key == "/analise/financeiro":
        return await _snapshot_analise_financeiro(db, tenant_id, year, month)
    if page_key == "/analise/comercial":
        return await _snapshot_analise_comercial(db, tenant_id, year, month)
    if page_key == "/financeiro":
        return await _snapshot_fluxo_caixa(db, tenant_id, year, month)
    if page_key == "/financeiro/dre":
        return await _snapshot_dre(db, tenant_id, year, month)
    if page_key == "/pacientes":
        return await _snapshot_analise_pacientes(db, tenant_id, year, month)
    if page_key == "/agenda":
        return await _snapshot_agenda(db, tenant_id)
    if page_key == "/":
        if user_id is None:
            return None  # home exige user_id pra ler layout
        return await _snapshot_home(db, tenant_id, user_id, year, month)
    if page_key == "/marketing/visao-geral":
        return await _snapshot_marketing(db, tenant_id)
    return None


# ── Helpers de estatística (média/desvio 6m a partir da sparkline 12m) ───


def _compute_6m_stats(
    sparkline_12m: list[float],
    *,
    current_value: float,
    projected_value: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """
    Calcula média/desvio dos últimos 6 meses FECHADOS (excluindo o atual)
    e compara com o valor de referência (projeção se mês parcial, atual
    se fechado). Retorna None se a sparkline não tem histórico suficiente.

    `is_excepcional`: True quando |ref - media| > 2σ — mês fora da curva
    histórica recente, IA deve destacar.
    """
    if not sparkline_12m or len(sparkline_12m) < 7:
        return None
    last_6 = sparkline_12m[-7:-1]  # M-6 a M-1
    if not last_6:
        return None
    media = sum(last_6) / len(last_6)
    variance = sum((x - media) ** 2 for x in last_6) / len(last_6)
    desvio = variance ** 0.5

    ref = projected_value if projected_value is not None else current_value
    vs_pct = ((ref - media) / media * 100) if media != 0 else None
    is_excepcional = bool(desvio > 0 and abs(ref - media) > 2 * desvio)

    return {
        "media_6m": media,
        "desvio_6m": desvio,
        "vs_media_6m_pct": vs_pct,
        "is_excepcional": is_excepcional,
    }


def _fmt_like(value: float, template: str) -> str:
    """Formata `value` no mesmo padrão de `template` (que vem do KPI atual).

    Heurísticas:
    - Template começa com "R$":
        - >= 1M  → "R$ X.XXM"
        - >= 10k → "R$ Xk"        (arredondado, ex: R$ 437k)
        - >= 1k  → "R$ X.Xk"      (decimal pra preservar precisão: R$ 1.7k em vez de R$ 2k)
        - < 1k   → "R$ X" (inteiro)
    - Template termina com "%" → percentual com 1 decimal
    - Default → número inteiro
    """
    t = (template or "").strip()
    if t.startswith("R$"):
        absv = abs(value)
        if absv >= 1_000_000:
            return f"R$ {value / 1_000_000:.2f}M"
        if absv >= 10_000:
            return f"R$ {value / 1_000:.0f}k"
        if absv >= 1_000:
            return f"R$ {value / 1_000:.1f}k"
        return f"R$ {value:.0f}"
    if t.endswith("%"):
        return f"{value:.1f}%"
    return f"{value:.0f}"


def _kpi_with_history(kpi: Any) -> dict[str, Any]:
    """Empacota um KpiCard pro snapshot já com média 6m + desvio + flag excepcional."""
    base: dict[str, Any] = {
        "valor": kpi.value_label,
        "mom_pct": kpi.mom_pct,
        "yoy_pct": kpi.yoy_pct,
        "trend": kpi.trend,
    }
    stats = _compute_6m_stats(
        kpi.sparkline_12m,
        current_value=kpi.value,
        projected_value=kpi.projected_value,
    )
    if stats is not None:
        base["media_6m_label"] = _fmt_like(stats["media_6m"], kpi.value_label)
        base["vs_media_6m_pct"] = (
            round(stats["vs_media_6m_pct"], 1) if stats["vs_media_6m_pct"] is not None else None
        )
        base["is_excepcional_vs_6m"] = stats["is_excepcional"]
    return base


async def _snapshot_analise_financeiro(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> Optional[dict[str, Any]]:
    """Snapshot do /analise/financeiro.

    Estrutura:
    - `kpis_principais` (heroes): SEMPRE no prompt — 4 KPIs com 3 ângulos (MoM, YoY, média 6m)
    - `kpis_secundarios` (pool): N aleatórios escolhidos a cada chamada → traz variedade
      e cobertura ao longo das visitas. ~10 itens no pool atualmente.
    """
    from app.services.analise_financeiro_service import get_analise_financeiro

    data = await get_analise_financeiro(db, tenant_id, year, month)
    if data is None:
        return None

    k = data.kpis
    fat, conv, tk, rec = k.faturamento, k.conversao, k.ticket_medio, k.recebido

    # Pool de secundários — cada item tem label + valor + (opcional) MoM/nota
    secundarios: dict[str, dict[str, Any]] = {}

    f = data.funil
    secundarios["funil_aprovacao"] = {
        "label": "Taxa de aprovação dos orçamentos",
        "valor": f"{f.conversao_aprovacao_pct:.1f}% ({f.aprovados_qty} de {f.gerados_qty})",
        "mom_pct": f.aprovacao_mom_pct,
        "nota": "do que entra no funil, quanto vira orçamento aprovado",
    }
    secundarios["funil_pagamento"] = {
        "label": "Conversão aprovado → pago",
        "valor": f"{f.conversao_pagamento_pct:.1f}% ({f.pagos_qty} de {f.aprovados_qty} aprovados)",
        "mom_pct": f.pagamento_mom_pct,
        "nota": "do que foi aprovado, quanto efetivamente teve pagamento",
    }

    p = data.prazos
    secundarios["prazo_medio"] = {
        "label": "Prazo médio de recebimento",
        "valor": f"{p.prazo_medio_dias:.0f} dias (do orçamento ao vencimento da parcela)",
        "nota": "horizonte de caixa: quanto tempo até o dinheiro entrar",
    }
    secundarios["pct_a_vista"] = {
        "label": "% à vista",
        "valor": f"{p.pct_a_vista_valor:.1f}% do valor (qtd: {p.pct_a_vista_qtd:.1f}%)",
        "mom_pct": p.mom_a_vista_pct,
        "nota": "quanto do faturamento vem em pagamento único",
    }

    tx = data.taxas
    secundarios["taxa_adquirencia"] = {
        "label": "Taxa efetiva de adquirência",
        "valor": f"{tx.taxa_efetiva_pct:.2f}% (R$ {tx.taxas_total:.0f} de R$ {tx.bruto_com_taxa:.0f})",
        "mom_pct": tx.mom_efetiva_pct,
        "nota": "% que as maquininhas cobram sobre o volume passível de taxa",
    }

    d = data.descontos
    secundarios["desconto_efetivo"] = {
        "label": "Desconto efetivo concedido",
        "valor": f"{d.desconto_total_pct:.1f}% ({d.qtd_orcamentos_aprovados} orçamentos)",
        "mom_pct": d.mom_total_pct,
        "nota": "negociação + tabela; quanto a equipe está descontando",
    }
    if d.escopo_nao_aprovado and d.escopo_nao_aprovado > 0:
        secundarios["escopo_nao_aprovado"] = {
            "label": "Escopo sugerido mas NÃO aprovado",
            "valor": f"R$ {d.escopo_nao_aprovado:.0f}",
            "nota": "procedimentos que o dentista sugeriu e o paciente não aceitou — pipeline de venda perdida",
        }

    if data.top_medicos:
        m0 = data.top_medicos[0]
        secundarios["top_medico"] = {
            "label": "Médico líder do mês",
            "valor": f"{m0.nome} — R$ {m0.faturamento:.0f} ({m0.pct_total:.1f}% do total)",
            "nota": "quem mais produziu faturamento aprovado",
        }
    if data.top_profissionais:
        p0 = data.top_profissionais[0]
        secundarios["top_atendente"] = {
            "label": "Atendente líder em vendas",
            "valor": f"{p0.nome} — R$ {p0.faturamento:.0f} ({p0.taxa_conversao_valor_pct:.1f}% conv. R$)",
            "nota": "quem fechou mais orçamentos (atendente, não dentista)",
        }
    if data.top_categorias:
        c0 = data.top_categorias[0]
        secundarios["top_categoria"] = {
            "label": "Especialidade campeã",
            "valor": f"{c0.categoria} — R$ {c0.faturamento:.0f} ({c0.pct_total:.1f}% do total)",
            "mom_pct": c0.mom_pct,
            "nota": "categoria de procedimento que mais faturou",
        }
    if data.mix_pagamento:
        top_pay = data.mix_pagamento[0]
        secundarios["forma_dominante"] = {
            "label": "Forma de pagamento dominante",
            "valor": f"{top_pay.forma_pagamento} — {top_pay.pct:.1f}% ({top_pay.qtd_transacoes} transações)",
            "mom_pct": top_pay.mom_pct,
            "nota": "forma de pagamento mais usada no mês",
        }

    return {
        "periodo": data.period.label,
        "is_partial": fat.is_partial,
        "partial_days": fat.partial_days,
        "partial_days_in_month": fat.partial_days_in_month,
        "projected_label": fat.projected_label,
        "kpis_principais": {
            "faturamento": _kpi_with_history(fat),
            "conversao": _kpi_with_history(conv),
            "ticket_medio": _kpi_with_history(tk),
            "recebido": _kpi_with_history(rec),
        },
        "kpis_secundarios": secundarios,
    }


# ── Snapshot: /analise/comercial ────────────────────────────────


async def _snapshot_analise_comercial(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> Optional[dict[str, Any]]:
    """Snapshot do /analise/comercial — foco em volume e eficiência operacional."""
    from app.services.analise_comercial_service import get_analise_comercial

    data = await get_analise_comercial(db, tenant_id, year, month)
    if data is None:
        return None

    k = data.kpis
    cons, abst, conv, pac = k.consultas, k.absenteismo_pct, k.conversao_consulta_orcamento_pct, k.pacientes_unicos

    secundarios: dict[str, dict[str, Any]] = {}

    # Saúde da agenda (decomposição dos status)
    s = data.saude_agenda
    pct_efetivas = (s.efetivas / s.total * 100) if s.total > 0 else 0
    secundarios["saude_agenda"] = {
        "label": "Saúde da agenda",
        "valor": f"{s.efetivas} efetivas, {s.faltas} faltas, {s.canceladas} canceladas (de {s.total} total)",
        "nota": f"{pct_efetivas:.1f}% das agendas viraram atendimento efetivo",
    }

    # Funil paciente atendido → orçamento → aprovação
    f = data.funil
    secundarios["funil_oferta"] = {
        "label": "Taxa de oferta de orçamento",
        "valor": f"{f.taxa_oferta_pct:.1f}% ({f.com_orcamento_qty} de {f.pacientes_atendidos} atendidos)",
        "mom_pct": f.taxa_oferta_mom_pct,
        "nota": "dos pacientes atendidos, quantos receberam um orçamento",
    }
    secundarios["funil_aprovacao_pac"] = {
        "label": "Taxa de aprovação por paciente",
        "valor": f"{f.taxa_aprovacao_pct:.1f}% ({f.aprovados_qty} de {f.com_orcamento_qty} com orçamento)",
        "mom_pct": f.taxa_aprovacao_mom_pct,
        "nota": "dos pacientes que receberam orçamento, quantos aprovaram",
    }
    if f.tempo_medio_consulta_aprov_dias is not None:
        secundarios["tempo_consulta_aprov"] = {
            "label": "Tempo médio consulta → aprovação",
            "valor": f"{f.tempo_medio_consulta_aprov_dias:.1f} dias",
            "nota": "quanto tempo o paciente leva pra fechar o orçamento depois da consulta",
        }

    # Operacional — tempo perdido
    op = data.operacional
    secundarios["tempo_perdido"] = {
        "label": "Tempo perdido com faltas/cancelados",
        "valor": f"{op.horas_perdidas:.1f}h ({op.dias_equivalentes_8h:.1f} dias úteis de 8h)",
        "nota": f"{op.faltas_qty} faltas + {op.cancelados_qty} cancelamentos",
    }

    # Top procedimento/especialidade/profissional
    if data.top_procedimentos:
        p0 = data.top_procedimentos[0]
        secundarios["top_procedimento"] = {
            "label": "Procedimento mais executado",
            "valor": f"{p0.procedure_name} — {p0.qtd_executados}× ({p0.pct_volume:.1f}% do volume)",
            "nota": "o que mais saiu da agenda",
        }
    if data.top_especialidades:
        e0 = data.top_especialidades[0]
        secundarios["top_especialidade"] = {
            "label": "Especialidade com mais demanda",
            "valor": f"{e0.especialidade} — {e0.qtd_procedimentos} procs ({e0.pct_volume:.1f}%)",
            "nota": "categoria de procedimento com mais volume",
        }
    if data.top_profissionais:
        pr0 = data.top_profissionais[0]
        secundarios["top_profissional_cons"] = {
            "label": "Profissional com mais consultas",
            "valor": f"{pr0.nome} — {pr0.qtd_consultas} consultas ({pr0.pacientes_distintos} pacientes distintos)",
            "nota": f"absenteísmo do prof: {pr0.absenteismo_pct:.1f}%",
        }
    if data.mix_categorias:
        mc0 = data.mix_categorias[0]
        secundarios["mix_categoria_top"] = {
            "label": "Categoria de consulta dominante",
            "valor": f"{mc0.categoria} — {mc0.pct:.1f}% ({mc0.qtd} agendamentos)",
            "mom_pct": mc0.mom_pct,
            "nota": "tipo de agendamento mais frequente",
        }

    return {
        "periodo": data.period.label,
        "is_partial": cons.is_partial,
        "partial_days": cons.partial_days,
        "partial_days_in_month": cons.partial_days_in_month,
        "projected_label": cons.projected_label,
        "kpis_principais": {
            "consultas": _kpi_with_history(cons),
            "absenteismo": _kpi_with_history(abst),
            "conversao_orcamento": _kpi_with_history(conv),
            "pacientes_unicos": _kpi_with_history(pac),
        },
        "kpis_secundarios": secundarios,
    }


# ── Helper: stats 6m a partir de série livre (pra páginas sem KpiCard) ───


def _stats_from_series(
    series: list[float],
    *,
    current_value: float,
    projected_value: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """Equivalente ao `_compute_6m_stats` mas pra páginas sem KpiCard.

    `series` deve ser uma lista de 12 valores mensais (mais antigo → mais
    recente). Usa M-6 a M-1 (excluindo o atual) pra calcular a média.
    """
    if not series or len(series) < 7:
        return None
    last_6 = series[-7:-1]
    if not last_6:
        return None
    media = sum(last_6) / len(last_6)
    variance = sum((x - media) ** 2 for x in last_6) / len(last_6)
    desvio = variance ** 0.5
    ref = projected_value if projected_value is not None else current_value
    vs_pct = ((ref - media) / media * 100) if media != 0 else None
    is_excepcional = bool(desvio > 0 and abs(ref - media) > 2 * desvio)
    return {
        "media_6m": media,
        "desvio_6m": desvio,
        "vs_media_6m_pct": vs_pct,
        "is_excepcional": is_excepcional,
    }


def _fmt_brl(v: float) -> str:
    """BRL compacto: 1.2M / 437k / 1.7k / R$ 580."""
    a = abs(v)
    if a >= 1_000_000:
        return f"R$ {v / 1_000_000:.2f}M"
    if a >= 10_000:
        return f"R$ {v / 1_000:.0f}k"
    if a >= 1_000:
        return f"R$ {v / 1_000:.1f}k"
    return f"R$ {v:.0f}"


# ── Snapshot: /financeiro (Fluxo de Caixa — Conta Azul) ─────────


async def _snapshot_fluxo_caixa(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> Optional[dict[str, Any]]:
    """Snapshot do /financeiro (Conta Azul). Sem KpiCard (campos float diretos);
    calculamos média 6m a partir do `data.evolution` (12 meses)."""
    from app.services.financeiro_service import get_financeiro_overview

    data = await get_financeiro_overview(db, tenant_id, year, month)
    if data is None:
        return None

    k, kp = data.kpis, data.kpis_previous

    # Séries 12m pra média histórica
    entradas_series = [p.entradas for p in data.evolution]
    saidas_series = [p.saidas for p in data.evolution]
    saldo_series = [p.saldo for p in data.evolution]

    def _hero(current: float, prev: float, series: list[float]) -> dict[str, Any]:
        mom_pct = ((current - prev) / abs(prev) * 100) if prev != 0 else None
        stats = _stats_from_series(series, current_value=current)
        out: dict[str, Any] = {
            "valor": _fmt_brl(current),
            "mom_pct": round(mom_pct, 1) if mom_pct is not None else None,
            "yoy_pct": None,  # não temos YoY aqui sem nova query
        }
        if stats is not None:
            out["media_6m_label"] = _fmt_brl(stats["media_6m"])
            out["vs_media_6m_pct"] = round(stats["vs_media_6m_pct"], 1) if stats["vs_media_6m_pct"] is not None else None
            out["is_excepcional_vs_6m"] = stats["is_excepcional"]
        return out

    secundarios: dict[str, dict[str, Any]] = {}

    secundarios["a_receber"] = {
        "label": "A receber",
        "valor": f"{_fmt_brl(k.a_receber)} (em aberto)",
        "nota": "valor lançado mas ainda não recebido",
    }
    secundarios["a_pagar"] = {
        "label": "A pagar",
        "valor": f"{_fmt_brl(k.a_pagar)} (em aberto)",
        "nota": "compromissos lançados ainda não pagos",
    }
    secundarios["inadimplencia"] = {
        "label": "Inadimplência",
        "valor": f"{k.inadimplencia_pct:.1f}% ({k.qtd_parcelas_vencidas} parcelas vencidas)",
        "nota": "% do total a receber que está vencido",
    }
    if (k.encargos_entradas + k.encargos_saidas) > 0:
        secundarios["encargos"] = {
            "label": "Encargos do mês",
            "valor": f"{_fmt_brl(k.encargos_entradas)} entradas, {_fmt_brl(k.encargos_saidas)} saídas",
            "nota": "juros + multa - desconto dos pagamentos detalhados",
        }
    if data.top_receitas:
        r0 = data.top_receitas[0]
        secundarios["top_receita"] = {
            "label": "Categoria de receita líder",
            "valor": f"{r0.nome} — {_fmt_brl(r0.total)} ({r0.pct:.1f}%)",
            "nota": "de onde vem mais dinheiro",
        }
    if data.top_despesas:
        d0 = data.top_despesas[0]
        secundarios["top_despesa"] = {
            "label": "Categoria de despesa líder",
            "valor": f"{d0.nome} — {_fmt_brl(d0.total)} ({d0.pct:.1f}%)",
            "nota": "pra onde vai mais dinheiro",
        }
    if data.metodos_pagamento and data.metodos_pagamento.metodos:
        m0 = data.metodos_pagamento.metodos[0]
        secundarios["metodo_dominante"] = {
            "label": "Forma de recebimento dominante",
            "valor": f"{m0.label} — {m0.pct_valor:.1f}% ({_fmt_brl(m0.valor_total)})",
            "nota": "como o dinheiro mais entra",
        }
    if data.conciliacao and data.conciliacao.qtd_total > 0:
        secundarios["conciliacao"] = {
            "label": "Conciliação bancária",
            "valor": f"{data.conciliacao.pct_conciliado:.1f}% conciliado ({data.conciliacao.qtd_conciliadas} de {data.conciliacao.qtd_total})",
            "nota": "quanto das baixas bate com extrato bancário",
        }
    if data.transferencias and data.transferencias.qtd > 0:
        secundarios["transferencias"] = {
            "label": "Transferências internas",
            "valor": f"{data.transferencias.qtd} movimentos, {_fmt_brl(data.transferencias.valor_total)} movidos",
            "nota": "trânsito entre contas próprias — não é receita nem despesa",
        }

    return {
        "periodo": data.period.label,
        "is_partial": False,  # /financeiro não publica parcial; pode evoluir
        "partial_days": None,
        "partial_days_in_month": None,
        "projected_label": None,
        "kpis_principais": {
            "entradas": _hero(k.entradas, kp.entradas, entradas_series),
            "saidas": _hero(k.saidas, kp.saidas, saidas_series),
            "saldo": _hero(k.saldo_liquido, kp.saldo_liquido, saldo_series),
        },
        "kpis_secundarios": secundarios,
    }


# ── Snapshot: /financeiro/dre ───────────────────────────────────


async def _snapshot_dre(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> Optional[dict[str, Any]]:
    """Snapshot da DRE estruturada — grupos com totais; calcula resultado.
    Usa `_dre_block` direto (não há entry-point público; mesma estratégia que a rota)."""
    from app.services.financeiro_service import _dre_block

    ym = f"{year:04d}-{month:02d}"
    label_periodo = f"{['', 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'][month]}/{year}"

    dre = await _dre_block(db, tenant_id, ym)
    if dre is None:
        return None

    grupos_by_code = {g.codigo: g for g in dre.grupos if g.codigo}

    receita_op = sum(g.total for kk, g in grupos_by_code.items() if kk in ("01", "02"))
    custos_var = abs(grupos_by_code["03"].total) if "03" in grupos_by_code else 0
    desp_fix = abs(grupos_by_code["04"].total) if "04" in grupos_by_code else 0
    resultado = receita_op - custos_var - desp_fix
    margem = (resultado / receita_op * 100) if receita_op > 0 else 0

    secundarios: dict[str, dict[str, Any]] = {}

    # Top 4 grupos por volume absoluto
    tops = sorted(dre.grupos, key=lambda g: abs(g.total), reverse=True)[:4]
    for i, g in enumerate(tops):
        if not g.codigo:
            continue
        secundarios[f"grupo_top_{i}"] = {
            "label": f"Grupo DRE: {g.descricao}",
            "valor": f"{_fmt_brl(abs(g.total))} ({len(g.subgrupos)} subgrupos)",
            "nota": f"código {g.codigo}",
        }

    if dre.total_nao_classificado > 0:
        secundarios["nao_classificado"] = {
            "label": "Lançamentos não classificados",
            "valor": _fmt_brl(dre.total_nao_classificado),
            "nota": "fato_caixa sem categoria DRE atribuída — limpar essa carteira ajuda a DRE",
        }

    return {
        "periodo": label_periodo,
        "is_partial": False,
        "partial_days": None,
        "partial_days_in_month": None,
        "projected_label": None,
        "kpis_principais": {
            "receita_operacional": {"valor": _fmt_brl(receita_op)},
            "custos_variaveis": {"valor": _fmt_brl(custos_var)},
            "despesas_fixas": {"valor": _fmt_brl(desp_fix)},
            "resultado": {"valor": f"{_fmt_brl(resultado)} (margem {margem:.1f}%)"},
        },
        "kpis_secundarios": secundarios,
    }


# ── Snapshot: /pacientes ────────────────────────────────────────


async def _snapshot_analise_pacientes(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> Optional[dict[str, Any]]:
    """Snapshot de /pacientes — retenção, LTV, oportunidade de resgate."""
    from app.services.analise_pacientes_service import get_analise_pacientes

    data = await get_analise_pacientes(db, tenant_id, year, month)
    if data is None:
        return None

    k = data.kpis

    secundarios: dict[str, dict[str, Any]] = {}

    s = data.saude_base
    secundarios["saude_base"] = {
        "label": "Saúde da base de pacientes",
        "valor": f"{s.ativo_qty} ativos, {s.em_risco_qty} em risco, {s.inativo_qty} inativos, {s.perdido_qty} perdidos (de {s.total})",
        "nota": "buckets de retenção por dias desde última visita",
    }

    nr = data.novos_recorrentes
    secundarios["novos_recorrentes"] = {
        "label": "Novos vs Recorrentes",
        "valor": f"{nr.novos_qty} novos, {nr.recorrentes_qty} recorrentes (de {nr.total} no mês)",
        "nota": f"ticket novos: {_fmt_brl(nr.novos_ticket_medio)}; recorrentes: {_fmt_brl(nr.recorrentes_ticket_medio)}",
    }

    # Curva ABC (Pareto)
    if data.curva_abc:
        a = next((c for c in data.curva_abc if c.classe == "A"), None)
        if a:
            secundarios["curva_abc_a"] = {
                "label": "Classe A (80% do faturamento)",
                "valor": f"{a.qtd_pacientes} pacientes ({a.pct_pacientes:.1f}% da base) geram {a.pct_faturamento:.1f}% do faturamento",
                "nota": "os pacientes mais valiosos — vale tratamento VIP",
            }

    if data.para_resgatar:
        secundarios["para_resgatar"] = {
            "label": "Pacientes a resgatar",
            "valor": f"{len(data.para_resgatar)} pacientes em risco/inativo com LTV alto",
            "nota": "oportunidade clara: já gastaram bem e estão sumindo",
        }
    if data.orcamentos_pendentes:
        total_pend = sum(o.amount for o in data.orcamentos_pendentes)
        secundarios["orcamentos_pendentes"] = {
            "label": "Orçamentos pendentes (a fechar)",
            "valor": f"{len(data.orcamentos_pendentes)} pacientes — {_fmt_brl(total_pend)} em jogo",
            "nota": "follow-up rápido tem alta chance de fechar",
        }
    if data.top_ltv:
        t0 = data.top_ltv[0]
        secundarios["top_ltv"] = {
            "label": "Paciente com maior LTV",
            "valor": f"{t0.name or 'sem nome'} — {_fmt_brl(t0.ltv)} ({t0.qtd_consultas_total} consultas, status: {t0.bucket})",
            "nota": "o paciente mais valioso da clínica",
        }
    if data.novos_do_mes:
        aprovaram = [n for n in data.novos_do_mes if n.aprovou]
        secundarios["novos_do_mes"] = {
            "label": "Pacientes novos no mês",
            "valor": f"{len(data.novos_do_mes)} novos; {len(aprovaram)} já aprovaram orçamento",
            "nota": "qualidade da captação: quantos novos viram cliente fechado",
        }

    return {
        "periodo": data.period.label,
        "is_partial": k.pacientes_ativos.is_partial,
        "partial_days": k.pacientes_ativos.partial_days,
        "partial_days_in_month": k.pacientes_ativos.partial_days_in_month,
        "projected_label": k.pacientes_ativos.projected_label,
        "kpis_principais": {
            "pacientes_ativos": _kpi_with_history(k.pacientes_ativos),
            "taxa_recorrencia": _kpi_with_history(k.taxa_recorrencia_pct),
            "ltv_medio": _kpi_with_history(k.ltv_medio),
            "em_risco": _kpi_with_history(k.em_risco_qty),
        },
        "kpis_secundarios": secundarios,
    }


# ── Snapshot: /agenda ───────────────────────────────────────────


async def _snapshot_agenda(
    db: AsyncSession, tenant_id: str,
) -> Optional[dict[str, Any]]:
    """Snapshot da agenda DO DIA (não mensal).

    Compara o dia atual com baseline histórico (P95 90d) em vez de média 6m.
    """
    from datetime import datetime
    from app.services.home_service import get_agenda_section

    data = await get_agenda_section(db, tenant_id, now_local=datetime.now(), target_date=None)
    if data is None:
        return None

    status_counts: dict[str, int] = {}
    for it in data.items:
        key = it.status_type or "AGENDADO"
        status_counts[key] = status_counts.get(key, 0) + 1

    confirmados = status_counts.get("CONFIRMED", 0)
    arrived = status_counts.get("ARRIVED", 0) + status_counts.get("IN_SESSION", 0) + status_counts.get("CHECKOUT", 0)
    faltas = status_counts.get("MISSED", 0)
    total = data.total

    kpis_principais: dict[str, dict[str, Any]] = {
        "total_agenda": {"valor": f"{total} agendamentos"},
        "confirmados": {"valor": f"{confirmados} confirmados ({(confirmados / total * 100) if total else 0:.0f}% do dia)"},
        "ja_realizadas": {"valor": f"{arrived} já em atendimento/atendidas"},
    }

    if data.capacity:
        cap = data.capacity
        kpis_principais["ocupacao"] = {
            "valor": f"{cap.consultas_hoje}/{cap.consultas_teto_p95} consultas ({cap.consultas_ocupacao_pct}% do teto P95 dos últimos {cap.historico_dias_efetivo}d)",
        }

    secundarios: dict[str, dict[str, Any]] = {}

    if faltas > 0:
        secundarios["faltas"] = {
            "label": "Faltas já registradas",
            "valor": f"{faltas} faltas marcadas ({(faltas / total * 100) if total else 0:.1f}% do dia)",
            "nota": "ações que não viraram atendimento por ausência do paciente",
        }
    if data.risk:
        r = data.risk
        secundarios["risco_faltas"] = {
            "label": "Risco de no-show",
            "valor": f"baseline da clínica {r.baseline_pct}%; previsão {r.faltas_esperadas_min}-{r.faltas_esperadas_max} faltas hoje",
            "nota": "estimativa baseada em histórico + perfil dos pacientes do dia",
        }
        if r.pacientes_alto_risco:
            secundarios["pacientes_alto_risco"] = {
                "label": "Pacientes em alto risco hoje",
                "valor": f"{len(r.pacientes_alto_risco)} pacientes com risco elevado",
                "nota": "confirmação prévia ajuda — chance maior de não comparecer",
            }
    if data.capacity:
        cap = data.capacity
        if cap.encaixe_total_min > 0:
            secundarios["encaixe"] = {
                "label": "Janela disponível para encaixe",
                "valor": f"{cap.encaixe_total_min // 60}h{cap.encaixe_total_min % 60:02d}min de folga no calendário",
                "nota": "pode ser usado pra encaixar lista de espera",
            }
        if cap.profs_com_folga:
            p0 = cap.profs_com_folga[0]
            secundarios["prof_com_folga"] = {
                "label": "Profissional com mais folga",
                "valor": f"{p0.professional_nome} — {p0.consultas_hoje}/{p0.consultas_teto_p95} consultas",
                "nota": f"ocupação de {p0.ocupacao_pct}% do teto histórico dele",
            }
    if data.waitlist and data.waitlist.total > 0:
        secundarios["waitlist"] = {
            "label": "Lista de espera",
            "valor": f"{data.waitlist.total} pacientes ({data.waitlist.waitlist_count} aguardando vaga, {data.waitlist.encaixe_count} encaixe)",
            "nota": "candidatos pra preencher janelas livres",
        }

    return {
        "periodo": f"agenda de {data.date_iso}" + (" (hoje)" if data.is_today else ""),
        "is_partial": False,
        "is_diaria": True,  # flag pro prompt builder mudar tom
        "partial_days": None,
        "partial_days_in_month": None,
        "projected_label": None,
        "kpis_principais": kpis_principais,
        "kpis_secundarios": secundarios,
    }


# ── Snapshot: /marketing/visao-geral (painel executivo Meta) ─────


def _wow_pct(cur: Optional[int], prev: Optional[int]) -> Optional[float]:
    """Calcula variação % week-over-week. None se prev é 0 ou ausente."""
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / prev * 100, 1)


def _fmt_wow(cur: Optional[int], prev: Optional[int], unit: str = "") -> str:
    """Formata `cur (vs prev) — Δ%`. Ex: '78.786 (vs 61.586) — +27,9% WoW'."""
    if cur is None:
        return "—"
    base = f"{cur:,}".replace(",", ".") + (f" {unit}" if unit else "")
    pct = _wow_pct(cur, prev)
    if pct is None or prev is None:
        return base
    prev_label = f"{prev:,}".replace(",", ".") + (f" {unit}" if unit else "")
    sign = "+" if pct >= 0 else ""
    return f"{base} (vs {prev_label} 7d antes) — {sign}{pct}% WoW"


async def _snapshot_marketing(
    db: AsyncSession, tenant_id: str,
) -> Optional[dict[str, Any]]:
    """Snapshot do painel executivo Meta (7d atual vs 7d anterior).

    Não usa comparativos mensais — é uma visão SEMANAL. Inclui alcance,
    engajamento, ganho de seguidores e top post pra DeepSeek narrar.
    """
    # Reusa os helpers do endpoint /meta/dashboard pra não duplicar SQL
    from app.api.v1.routes.meta import (
        _ig_insights_window, _fb_insights_window, _posts_count_window,
        _ig_top_posts, _fb_top_posts,
    )
    from app.models.staging_meta import StgMetaFbPosts, StgMetaIgPerfil, StgMetaIgPosts

    # Snapshots básicos pra obter @username / nome
    ig_perfil = (await db.execute(
        select(StgMetaIgPerfil)
        .where(StgMetaIgPerfil.tenant_id == tenant_id)
        .order_by(StgMetaIgPerfil.data_referencia.desc())
        .limit(1)
    )).scalar_one_or_none()

    ig_win = await _ig_insights_window(db, tenant_id)
    fb_win = await _fb_insights_window(db, tenant_id)
    ig_posts_cur, ig_posts_prev = await _posts_count_window(db, StgMetaIgPosts, tenant_id)
    fb_posts_cur, fb_posts_prev = await _posts_count_window(db, StgMetaFbPosts, tenant_id)
    top_ig = await _ig_top_posts(db, tenant_id, limit=1)
    top_fb = await _fb_top_posts(db, tenant_id, limit=1)

    # Sem dados de insights = sem snapshot (SonIA cairá pra heurística front)
    if not ig_win and not fb_win:
        return None

    ig_username = (ig_perfil.raw_data or {}).get("username") if ig_perfil else None
    followers_total = (ig_perfil.raw_data or {}).get("followers_count") if ig_perfil else None

    kpis_principais: dict[str, dict[str, Any]] = {
        "alcance_ig_7d": {"valor": _fmt_wow(ig_win.get("reach_7d"), ig_win.get("reach_7d_prev"), "contas")},
        "alcance_fb_7d": {"valor": _fmt_wow(fb_win.get("reach_7d"), fb_win.get("reach_7d_prev"), "contas")},
        "seguidores_ig_ganho_7d": {
            "valor": _fmt_wow(ig_win.get("followers_gained_7d"), ig_win.get("followers_gained_7d_prev"), "novos")
            + (f" · total {followers_total:,}".replace(",", ".") if followers_total else ""),
        },
        "engajamento_fb_7d": {"valor": _fmt_wow(fb_win.get("engagement_7d"), fb_win.get("engagement_7d_prev"), "interações")},
    }

    secundarios: dict[str, dict[str, Any]] = {
        "ritmo_publicacao_ig": {
            "label": "Ritmo de publicação Instagram",
            "valor": f"{ig_posts_cur} posts em 7d (vs {ig_posts_prev} na semana anterior)",
            "nota": "frequência de publicações orgânicas no IG",
        },
        "ritmo_publicacao_fb": {
            "label": "Ritmo de publicação Facebook",
            "valor": f"{fb_posts_cur} posts em 7d (vs {fb_posts_prev} na semana anterior)",
            "nota": "frequência de publicações orgânicas no FB",
        },
    }

    if top_ig:
        p = top_ig[0]
        legenda = (p.caption or "").replace("\n", " ").strip()[:120]
        secundarios["top_post_ig"] = {
            "label": "Top post Instagram (lifetime)",
            "valor": f"{p.reach:,} contas alcançadas".replace(",", ".") +
                     (f" · {p.likes} curtidas" if p.likes else "") +
                     (f" · {p.shares} compart." if p.shares else ""),
            "nota": f"legenda: \"{legenda}\"" if legenda else "post sem legenda",
        }
    if top_fb:
        p = top_fb[0]
        legenda = (p.caption or "").replace("\n", " ").strip()[:120]
        secundarios["top_post_fb"] = {
            "label": "Top post Facebook (lifetime)",
            "valor": f"{p.reach:,} pessoas alcançadas".replace(",", ".") +
                     (f" · {p.likes} reações" if p.likes else ""),
            "nota": f"legenda: \"{legenda}\"" if legenda else "post sem legenda",
        }

    return {
        "periodo": "últimos 7 dias (comparado com 7 dias anteriores)",
        "is_partial": False,
        "is_semanal_marketing": True,  # flag nova pro prompt builder
        "partial_days": None,
        "partial_days_in_month": None,
        "projected_label": None,
        "ig_username": ig_username,
        "kpis_principais": kpis_principais,
        "kpis_secundarios": secundarios,
    }


# ── Snapshot: / (MY-Analisys — home customizada por user) ───────


async def _snapshot_home(
    db: AsyncSession, tenant_id: str, user_id: str, year: int, month: int,
) -> Optional[dict[str, Any]]:
    """Snapshot do MY-Analisys.

    Lê o layout salvo do user e monta `kpis_secundarios` SÓ pros widgets
    presentes. Os widgets vêm de fontes diferentes (home/analise/financeiro),
    então fazemos fetch apenas dos services necessários conforme o layout.
    """
    from datetime import datetime
    from app.repositories.home_layout_repository import get_layout
    from app.services.home_service import get_home_dashboard

    layout = await get_layout(db, tenant_id, user_id)
    if layout is None or not layout.layout_json:
        return None

    widget_ids = {item["widget_id"] for item in layout.layout_json if "widget_id" in item}
    if not widget_ids:
        return None

    # Conjuntos pra decidir quais services chamar
    HOME_WIDGETS = {"agenda_summary", "agenda_strategic", "recall", "pendencias",
                    "orcamentos_parados", "inadimplencia_critica", "top_profs"}
    FIN_WIDGETS = {"kpi_fin_faturamento", "kpi_fin_recebido", "kpi_fin_ticket",
                   "kpi_fin_conversao", "evolucao_faturamento", "funil_orcamentos"}
    COM_WIDGETS = {"kpi_com_consultas", "kpi_com_absenteismo", "kpi_com_conversao",
                   "kpi_com_pacientes_unicos", "evolucao_consultas", "top_procedimentos"}
    PAC_WIDGETS = {"kpi_pac_ativos", "kpi_pac_recorrencia", "kpi_pac_ltv",
                   "kpi_pac_em_risco", "saude_base", "top_ltv", "para_resgatar"}

    now_local = datetime.now()
    home_data = None
    fin_data = None
    com_data = None
    pac_data = None

    if widget_ids & HOME_WIDGETS:
        home_data = await get_home_dashboard(
            db, tenant_id=tenant_id, role="tenant_admin",
            user_full_name="", now_local=now_local,
        )
    if widget_ids & FIN_WIDGETS:
        from app.services.analise_financeiro_service import get_analise_financeiro
        fin_data = await get_analise_financeiro(db, tenant_id, year, month)
    if widget_ids & COM_WIDGETS:
        from app.services.analise_comercial_service import get_analise_comercial
        com_data = await get_analise_comercial(db, tenant_id, year, month)
    if widget_ids & PAC_WIDGETS:
        from app.services.analise_pacientes_service import get_analise_pacientes
        pac_data = await get_analise_pacientes(db, tenant_id, year, month)

    secundarios: dict[str, dict[str, Any]] = {}

    def _kpi_line(kpi: Any, *, sufixo: str = "") -> str:
        # Em mês parcial, mostra parcial + projeção pro mês fechado. O LLM
        # já é instruído (system prompt) a NÃO comparar MoM diretamente quando
        # is_partial=true — então não imprimimos MoM nesse caso.
        if getattr(kpi, "is_partial", False):
            parts = [f"PARCIAL {kpi.value_label}{sufixo}"]
            if getattr(kpi, "projected_label", None):
                parts.append(f"projeção mês fechado: {kpi.projected_label}")
            if getattr(kpi, "partial_days", None) and getattr(kpi, "partial_days_in_month", None):
                parts.append(f"dia {kpi.partial_days}/{kpi.partial_days_in_month}")
            return " · ".join(parts)
        parts = [f"{kpi.value_label}{sufixo}"]
        if kpi.mom_pct is not None:
            parts.append(f"MoM {kpi.mom_pct:+.1f}%")
        if kpi.yoy_pct is not None:
            parts.append(f"YoY {kpi.yoy_pct:+.1f}%")
        return " · ".join(parts)

    # ── Home dashboard widgets ─────────────────────────────────
    if home_data is not None:
        d = home_data
        if ("agenda_summary" in widget_ids or "agenda_strategic" in widget_ids) and d.agenda:
            secundarios["agenda_dia"] = {
                "label": "Agenda do dia",
                "valor": f"{d.agenda.total} consultas no total (não há breakdown de confirmadas/pendentes — não invente)",
                "nota": "olhar de hoje",
            }
        if "recall" in widget_ids and d.recall and d.recall.total_elegiveis > 0:
            first = d.recall.items[0] if d.recall.items else None
            valor = f"{d.recall.total_elegiveis} pacientes elegíveis"
            nota = "vinham regularmente e estão atrasados"
            if first:
                nome = first.paciente_nome.split(" ")[0]
                nota = f"{nota}; mais atrasado é {nome} ({first.dias_desde_ultima}d sem visita)"
            secundarios["recall"] = {"label": "Pacientes pra recall", "valor": valor, "nota": nota}
        if "pendencias" in widget_ids and d.pendencias and d.pendencias.total > 0:
            secundarios["pendencias"] = {
                "label": "Pendências operacionais",
                "valor": f"{d.pendencias.total} pendências sinalizadas no Clinicorp",
                "nota": "tags abertas",
            }
        if "orcamentos_parados" in widget_ids and d.orcamentos_parados and d.orcamentos_parados.total > 0:
            secundarios["orcamentos_parados"] = {
                "label": "Orçamentos parados (30-90d sem retorno)",
                "valor": f"{d.orcamentos_parados.total} orçamentos · R$ {d.orcamentos_parados.valor_total:,.0f}".replace(",", "."),
                "nota": "aprovados que não viraram nova consulta",
            }
        if "inadimplencia_critica" in widget_ids and d.inadimplencia_critica and d.inadimplencia_critica.total > 0:
            secundarios["inadimplencia"] = {
                "label": "Inadimplência crítica (+60d, +R$ 500)",
                "valor": f"{d.inadimplencia_critica.total} parcelas · R$ {d.inadimplencia_critica.valor_total:,.0f}".replace(",", "."),
                "nota": "vencidas há bastante tempo",
            }
        if "top_profs" in widget_ids and d.top_profs_semana and d.top_profs_semana.items:
            top = d.top_profs_semana.items[0]
            secundarios["top_profs"] = {
                "label": "Profissional que mais aprovou esta semana",
                "valor": f"{top.nome} — R$ {top.valor_aprovado:,.0f}".replace(",", "."),
                "nota": "ranking semanal",
            }

    # ── KPIs Financeiros ───────────────────────────────────────
    if fin_data is not None:
        k = fin_data.kpis
        if "kpi_fin_faturamento" in widget_ids:
            secundarios["kpi_fat"] = {"label": "Faturamento do mês", "valor": _kpi_line(k.faturamento)}
        if "kpi_fin_recebido" in widget_ids:
            secundarios["kpi_rec"] = {"label": "Recebido (caixa do mês)", "valor": _kpi_line(k.recebido)}
        if "kpi_fin_ticket" in widget_ids:
            secundarios["kpi_tk"] = {"label": "Ticket médio", "valor": _kpi_line(k.ticket_medio)}
        if "kpi_fin_conversao" in widget_ids:
            secundarios["kpi_conv_fin"] = {"label": "Conversão R$ aprovado/gerado", "valor": _kpi_line(k.conversao)}
        if "evolucao_faturamento" in widget_ids and fin_data.evolution:
            ult = fin_data.evolution[-1]
            antep = fin_data.evolution[-2] if len(fin_data.evolution) >= 2 else None
            tendencia = ""
            if antep is not None and antep.faturamento > 0:
                delta = (ult.faturamento - antep.faturamento) / antep.faturamento * 100
                tendencia = f" ({delta:+.1f}% vs mês anterior)"
            secundarios["evol_fat"] = {
                "label": "Evolução 12 meses (faturamento)",
                "valor": f"último mês {ult.label}: R$ {ult.faturamento:,.0f}{tendencia}".replace(",", "."),
                "nota": "linha temporal completa não cabe aqui — comente só a tendência recente",
            }
        if "funil_orcamentos" in widget_ids:
            f = fin_data.funil
            secundarios["funil_orc"] = {
                "label": "Funil de orçamentos do mês",
                "valor": f"{f.gerados_qty} gerados → {f.aprovados_qty} aprovados → {f.pagos_qty} pagos",
                "nota": f"taxa aprovação R$: {f.conversao_aprovacao_valor_pct:.1f}%",
            }

    # ── KPIs Comerciais ────────────────────────────────────────
    if com_data is not None:
        k = com_data.kpis
        if "kpi_com_consultas" in widget_ids:
            secundarios["kpi_cons"] = {"label": "Consultas do mês", "valor": _kpi_line(k.consultas)}
        if "kpi_com_absenteismo" in widget_ids:
            secundarios["kpi_abs"] = {"label": "Absenteísmo (inverso: menor é melhor)", "valor": _kpi_line(k.absenteismo_pct)}
        if "kpi_com_conversao" in widget_ids:
            secundarios["kpi_conv_co"] = {"label": "Conversão consulta → orçamento", "valor": _kpi_line(k.conversao_consulta_orcamento_pct)}
        if "kpi_com_pacientes_unicos" in widget_ids:
            secundarios["kpi_pac_un"] = {"label": "Pacientes únicos atendidos", "valor": _kpi_line(k.pacientes_unicos)}
        if "evolucao_consultas" in widget_ids and com_data.evolution:
            ult = com_data.evolution[-1]
            secundarios["evol_cons"] = {
                "label": "Evolução 12 meses (agenda)",
                "valor": f"último mês {ult.label}: {ult.efetivas} efetivas, {ult.faltas} faltas, {ult.canceladas} canceladas",
                "nota": "stacked bar 12m",
            }
        if "top_procedimentos" in widget_ids and com_data.top_procedimentos:
            p0 = com_data.top_procedimentos[0]
            secundarios["top_procs"] = {
                "label": "Procedimento mais executado",
                "valor": f"{p0.procedure_name} — {p0.qtd_executados}× ({p0.pct_volume:.1f}% do volume)",
            }

    # ── KPIs Pacientes ─────────────────────────────────────────
    if pac_data is not None:
        k = pac_data.kpis
        if "kpi_pac_ativos" in widget_ids:
            secundarios["kpi_ativos"] = {"label": "Pacientes ativos (<90d)", "valor": _kpi_line(k.pacientes_ativos)}
        if "kpi_pac_recorrencia" in widget_ids:
            secundarios["kpi_recor"] = {"label": "Taxa de recorrência", "valor": _kpi_line(k.taxa_recorrencia_pct)}
        if "kpi_pac_ltv" in widget_ids:
            secundarios["kpi_ltv"] = {"label": "LTV médio", "valor": _kpi_line(k.ltv_medio)}
        if "kpi_pac_em_risco" in widget_ids:
            secundarios["kpi_risco"] = {"label": "Em risco (90-180d, inverso)", "valor": _kpi_line(k.em_risco_qty)}
        if "saude_base" in widget_ids and pac_data.saude_base:
            s = pac_data.saude_base
            secundarios["saude"] = {
                "label": "Saúde da base de pacientes",
                "valor": f"{s.total} total · {s.ativo_pct:.1f}% ativos, {s.em_risco_pct:.1f}% em risco",
            }
        if "top_ltv" in widget_ids and pac_data.top_ltv:
            secundarios["top_ltv"] = {
                "label": "Top LTV — pacientes mais valiosos",
                "valor": f"top é {pac_data.top_ltv[0].name or '#?'} com LTV R$ {pac_data.top_ltv[0].ltv:,.0f}".replace(",", "."),
            }
        if "para_resgatar" in widget_ids and pac_data.para_resgatar:
            secundarios["resgatar"] = {
                "label": "Para Resgatar",
                "valor": f"{len(pac_data.para_resgatar)} pacientes em risco com LTV alto pra reativar",
            }

    if not secundarios:
        return None

    # Detecta se algum KPI vem em mês parcial — se sim, sinaliza pro LLM via
    # `is_partial=True` (system prompt já trata: não compara MoM diretamente,
    # fala de projeção). Mês parcial vem dos /analise/* services quando year/
    # month == mês corrente.
    is_partial = False
    for src in (fin_data, com_data, pac_data):
        if src is None:
            continue
        kpis = getattr(src, "kpis", None)
        if kpis is None:
            continue
        for kpi_attr in vars(kpis).values() if hasattr(kpis, "__dict__") else []:
            if getattr(kpi_attr, "is_partial", False):
                is_partial = True
                break
        if is_partial:
            break

    # Info de progresso do mês (dia X de Y) pra o LLM proporcionar a leitura.
    partial_days = None
    partial_days_in_month = None
    if is_partial:
        for src in (fin_data, com_data, pac_data):
            if src is None:
                continue
            kpis = getattr(src, "kpis", None)
            if kpis is None:
                continue
            for kpi_attr in vars(kpis).values() if hasattr(kpis, "__dict__") else []:
                if getattr(kpi_attr, "is_partial", False):
                    partial_days = getattr(kpi_attr, "partial_days", None)
                    partial_days_in_month = getattr(kpi_attr, "partial_days_in_month", None)
                    if partial_days is not None:
                        break
            if partial_days is not None:
                break

    return {
        "periodo": now_local.strftime("%d/%m/%Y"),
        "is_partial": is_partial,
        "partial_days": partial_days,
        "partial_days_in_month": partial_days_in_month,
        # NÃO é "diária" no sentido do snapshot agenda — é home mista com
        # widgets do dia (agenda) E do mês (KPIs financeiros).
        "is_home_customizada": True,
        "widgets_no_layout": sorted(secundarios.keys()),
        "kpis_principais": {},
        "kpis_secundarios": secundarios,
    }


# ── DeepSeek call ────────────────────────────────────────────────


_SYSTEM_PROMPT = """Você é SonIA — assistente analítica de uma clínica odontológica. Sua personalidade é:

- Mulher de cerca de 30 anos, doce, discreta, cordial e gentil.
- Tom: sugestão > ordem. Use verbos suaves: "notei", "reparei", "encontrei", "selecionei", "achei", "queria te mostrar".
- Sem jargão corporativo: nunca diga "régua de cobrança", "pipeline destravar", "KPI", "ROI", "follow-up". Use linguagem cotidiana: "olhar com calma", "retomar essas conversas", "contato gentil".
- Saudação cordial sempre que houver nome do usuário: "Oi, {nome}."
- Sem alarmismo. Em alertas, seja SÉRIA mas calma. "Queria te mostrar uma coisa" funciona melhor que "ATENÇÃO!".
- Sem emojis. Sem exclamações exageradas.
- Frases curtas, com vírgulas, naturais — não staccato.

VOCÊ DEVE RETORNAR APENAS JSON VÁLIDO no formato:

{
  "mood": "default" | "thinking" | "alert" | "happy" | "curious",
  "headline": "Frase curta de abertura (até 60 caracteres)",
  "detail": "1 a 2 frases explicando o que você observou (até 240 caracteres)",
  "bullets": [
    {"text": "Observação curta (até 130 caracteres)", "tone": "neutral" | "positive" | "negative" | "warning"}
  ]
}

REGRAS sobre o `mood`:
- "alert" — situação crítica (queda forte sustentada — não só MoM, mas TAMBÉM abaixo da média histórica; ou indicador absoluto ruim)
- "happy" — resultado positivo sustentado (acima da média 6m E do mês anterior)
- "curious" — convidando a olhar, sugerindo análise, ou variação dentro do esperado
- "default" — situação neutra, equilibrada
- "thinking" — NÃO usar como mood final (só estado de loading)

REGRAS sobre os 3 ângulos comparativos (use TODOS quando disponíveis):
- **Média 6m** é a referência MAIS CONFIÁVEL: representa o "normal histórico". Compare o atual contra ela com prioridade.
- **MoM** mostra momentum imediato, mas é volátil — um mês excepcional anterior distorce a leitura. Use com cuidado.
- **YoY** revela sazonalidade real (mesmo mês ano passado).
- Se um KPI está marcado como **EXCEPCIONAL**, significa atual > 2σ da média histórica — DESTAQUE isso ("ritmo bem fora da curva", "um mês fora do comum", etc.).
- Se MoM e vs-média-6m apontam direções DIFERENTES, sempre contextualize: "abaixo de abril, mas próximo da média histórica" é muito mais útil que apenas "20% abaixo do mês passado".

REGRAS sobre os dados estruturados que você recebe:
- KPIs PRINCIPAIS (quando existirem) — comente SEMPRE 2-3 desses com os ângulos disponíveis.
- OBSERVAÇÕES DESTA SESSÃO — pool aleatório que muda a cada visita. Use 2-4 desses pra DIVERSIFICAR a leitura (espalhe entre métricas diferentes). Não comente que são aleatórios; apresente como se você tivesse "reparado" naquilo.

REGRAS sobre dados:
- Use APENAS os números fornecidos. NUNCA invente. Se não tem dado, NÃO mencione.
- Se um número for null/None, ignore silenciosamente.
- Em mês parcial (is_partial=true), NUNCA dispare alerta por MoM. Fale de valor parcial + projeção.
- **SEMPRE 4 a 6 bullets** (preferencialmente 5). Não menos de 4 se houver pool. Cada bullet com 1 número específico e contexto.
- COBERTURA: cada bullet sobre uma métrica/ângulo DIFERENTE. Nunca 2 bullets sobre a mesma coisa.
"""


def _fmt_kpi_line(kpi: dict[str, Any]) -> str:
    """Formata uma linha de KPI com os 3 ângulos comparativos (MoM, YoY, média 6m).

    Saída tipo:
      "R$ 577k (atual) — MoM +63,4%, YoY +28,0%, média 6m R$ 380k (vs +52% · EXCEPCIONAL ⚠️)"

    Campos opcionais (média 6m, YoY) são omitidos quando ausentes — IA não
    deve inventar comparações pra dados que não temos.
    """
    parts = [f"{kpi['valor']} (atual)"]
    if kpi.get("mom_pct") is not None:
        parts.append(f"MoM {kpi['mom_pct']:+.1f}%")
    if kpi.get("yoy_pct") is not None:
        parts.append(f"YoY {kpi['yoy_pct']:+.1f}%")
    if kpi.get("media_6m_label"):
        media_part = f"média 6m {kpi['media_6m_label']}"
        vs = kpi.get("vs_media_6m_pct")
        if vs is not None:
            media_part += f" (vs {vs:+.1f}%"
            if kpi.get("is_excepcional_vs_6m"):
                media_part += " · EXCEPCIONAL"
            media_part += ")"
        parts.append(media_part)
    return " — ".join(parts)


def _build_user_prompt(
    page_key: str,
    snapshot: dict[str, Any],
    user_first_name: Optional[str],
    clinic_name: Optional[str],
) -> str:
    lines: list[str] = []
    if user_first_name:
        lines.append(f"Usuário: {user_first_name}")
    if clinic_name:
        lines.append(f"Clínica: {clinic_name}")
    lines.append(f"Página: {page_key}")
    lines.append(f"Período: {snapshot.get('periodo')}")

    if snapshot.get("is_partial"):
        lines.append(
            f"⚠️ MÊS EM ANDAMENTO — dia {snapshot.get('partial_days')} de {snapshot.get('partial_days_in_month')}"
            f"; projeção do mês fechado: {snapshot.get('projected_label') or 'n/d'}"
        )
        lines.append("")
        lines.append("NÃO compare MoM% — o mês mal começou. Fale do parcial + projeção.")
    else:
        lines.append("Mês fechado — você pode comparar MoM% normalmente.")
    lines.append("")

    kp = snapshot.get("kpis_principais", {})

    # Cada page_key formata seus KPIs principais com labels apropriados.
    # KPIs com `mom_pct`/`media_6m_label` usam `_fmt_kpi_line`; KPIs simples
    # (dict com apenas "valor") imprimem direto.
    KPI_LABELS = {
        "/analise/financeiro": {
            "faturamento": "Faturamento", "conversao": "Conversão",
            "ticket_medio": "Ticket médio", "recebido": "Recebido caixa",
        },
        "/analise/comercial": {
            "consultas": "Consultas atendidas", "absenteismo": "Absenteísmo (inverso: menor é melhor)",
            "conversao_orcamento": "Conversão consulta→orçamento", "pacientes_unicos": "Pacientes únicos",
        },
        "/financeiro": {
            "entradas": "Entradas (recebimentos do mês)", "saidas": "Saídas (pagamentos do mês)",
            "saldo": "Saldo líquido",
        },
        "/financeiro/dre": {
            "receita_operacional": "Receita operacional", "custos_variaveis": "Custos variáveis",
            "despesas_fixas": "Despesas fixas", "resultado": "Resultado operacional",
        },
        "/pacientes": {
            "pacientes_ativos": "Pacientes ativos (< 90d)",
            "taxa_recorrencia": "Taxa de recorrência", "ltv_medio": "LTV médio",
            "em_risco": "Em risco (90-180d) — inverso: menor é melhor",
        },
        "/agenda": {
            "total_agenda": "Total de agendamentos", "confirmados": "Confirmados",
            "ja_realizadas": "Já em atendimento/atendidas", "ocupacao": "Ocupação vs teto histórico (P95)",
        },
        "/marketing/visao-geral": {
            "alcance_ig_7d": "Alcance Instagram (7d)",
            "alcance_fb_7d": "Alcance Facebook (7d)",
            "seguidores_ig_ganho_7d": "Ganho de seguidores Instagram (7d)",
            "engajamento_fb_7d": "Engajamento Facebook (7d)",
        },
    }
    labels = KPI_LABELS.get(page_key, {})

    if snapshot.get("is_diaria"):
        lines.append(
            "Esta é uma VISÃO DIÁRIA — você está olhando o snapshot da agenda de UM DIA "
            "(não um mês). Não use comparações com média de 6 meses. Compare contra "
            "baseline da clínica (P95 dos últimos 90 dias) que vem nos próprios KPIs."
        )
        lines.append("")

    if snapshot.get("is_semanal_marketing"):
        ig_username = snapshot.get("ig_username")
        lines.append(
            "Esta é a VISÃO SEMANAL do painel de redes sociais (Instagram + Facebook orgânico). "
            "Toda métrica vem com comparativo WoW (semana atual vs 7 dias anteriores). "
            "NÃO use comparações mensais nem média 6m. Tom executivo: foco em direção (sobe/desce/estável) e em qual canal performou melhor."
        )
        if ig_username:
            lines.append(f"O perfil é @{ig_username}.")
        lines.append("Quando o crescimento WoW for > +20%, destaque como momentum. Quando for negativo, mencione com calma (semana pode oscilar).")
        lines.append("")

    if snapshot.get("is_home_customizada"):
        lines.append(
            "Esta é a HOME CUSTOMIZADA do usuário (MY-Analisys). É uma VISÃO MISTA: "
            "alguns widgets são do DIA (agenda, recall), outros são do MÊS (KPIs financeiros/comerciais/pacientes). "
            "Trate cada observação no escopo em que ela vem: NÃO compare KPI do mês com baseline diária."
        )
        lines.append("")
        lines.append("REGRAS CRÍTICAS pra esta página:")
        lines.append(
            "1. Use APENAS os números literais que aparecem nas OBSERVAÇÕES abaixo. "
            "NUNCA invente baseline, meta, projeção, ocupação, ticket médio ou qualquer outro número "
            "que não esteja LITERALMENTE escrito ali. Copie os valores exatos."
        )
        lines.append(
            "2. Para CADA observação fornecida, gere 1 bullet. Total = 4-6 bullets (use TUDO o que tem)."
        )
        lines.append(
            "3. Headline curto e acolhedor. Tom de \"trouxe o que reparei no seu painel\"."
        )
        lines.append("")

    if kp:
        if any("mom_pct" in v or "media_6m_label" in v for v in kp.values()):
            lines.append("KPIs PRINCIPAIS (cada um com até 3 ângulos: MoM / YoY / Média 6m):")
        else:
            lines.append("KPIs PRINCIPAIS:")
        for key, val in kp.items():
            label = labels.get(key, key.replace("_", " ").capitalize())
            if "mom_pct" in val or "media_6m_label" in val:
                lines.append(f"- {label}: {_fmt_kpi_line(val)}")
            else:
                lines.append(f"- {label}: {val.get('valor', '')}")
        lines.append("")

    # Pool de secundários — escolhe N aleatórios pra trazer variedade.
    # Independente de ter kpis_principais ou não (home customizada, por exemplo,
    # tem APENAS secundários — antes esse bloco vivia dentro de `if kp:` e o
    # prompt saía sem dados, levando o LLM a alucinar tudo).
    secs: dict[str, dict[str, Any]] = snapshot.get("kpis_secundarios", {})
    if secs:
        chosen_keys = random.sample(list(secs.keys()), k=min(_N_SECUNDARIOS_ALEATORIOS, len(secs)))
        lines.append(
            f"OBSERVAÇÕES DESTA SESSÃO ({len(chosen_keys)} de {len(secs)} disponíveis — "
            "use 2-4 desses pra diversificar a leitura; copie valores LITERAIS):"
        )
        for key in chosen_keys:
            lines.append(f"- {_fmt_secundario_line(secs[key])}")
        lines.append("")

    lines.append("Devolva APENAS o JSON conforme schema, em pt-BR. Use o nome do usuário no headline ou detail quando fizer sentido.")
    return "\n".join(lines)


# Quantos secundários incluir aleatoriamente em cada chamada.
# Padrão SonIA: sempre 4-6 bullets, pool maior dá ao LLM espaço pra escolher.
_N_SECUNDARIOS_ALEATORIOS = 8


def _fmt_secundario_line(sec: dict[str, Any]) -> str:
    """Formata 1 linha de KPI secundário pro prompt: "Label: valor (MoM ±X%) — nota"."""
    parts = [f"{sec['label']}: {sec['valor']}"]
    mom = sec.get("mom_pct")
    if mom is not None:
        parts.append(f"(MoM {mom:+.1f}%)")
    nota = sec.get("nota")
    if nota:
        parts.append(f"— {nota}")
    return " ".join(parts)
