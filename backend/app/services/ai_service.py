"""
IA narrativa da agenda — Sub-PR 17b.

Recebe um StrategicOverview (3 dias agregados + top riscos + profs ociosos)
+ contexto da clínica e devolve prosa em pt-BR pra HomePage do dono.

Princípios:
- Determinístico no input: o backend já fez todas as contas. A IA SÓ traduz
  números em prosa. Não inventa, não recalcula, não opina sobre dados que
  não foram fornecidos.
- Curto: 3-4 frases. Dono não lê parágrafo.
- Ações > descrições: "Ligar pra X" > "X tem risco alto".
- Cache em Redis com TTL curto (5min) — chamadas repetidas no mesmo refresh
  da página pegam do cache.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from anthropic import AsyncAnthropic, APIError

from app.core.config import settings
from app.schemas.home import StrategicOverview

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """Você é um assistente analítico para gestores de clínica odontológica.
Recebe um snapshot da agenda dos próximos 3 dias e devolve um resumo curto em português brasileiro.

REGRAS:
- 3 a 4 frases curtas. Direto, sem floreio.
- Use APENAS os números fornecidos. Nunca invente paciente, prof ou métrica.
- Foque em ação: o que o dono deve FAZER hoje. Ex: "Ligar para X antes do horário".
- Comece destacando o ponto mais relevante: capacidade alta? risco alto? folga grande?
- Use nomes próprios quando aparecerem (paciente em risco, prof ocioso).
- NÃO repita os números já visíveis no card. Comente o que eles SIGNIFICAM.
- NÃO use bullets, headers, markdown. Texto corrido.
- Tom: confiável, conciso, parceiro do gestor."""


def _build_user_prompt(overview: StrategicOverview, clinic_name: Optional[str]) -> str:
    """Serializa o overview num formato denso e legível pela IA."""
    lines: list[str] = []
    lines.append(f"Clínica: {clinic_name or 'sem nome'}")
    lines.append(f"Baseline histórica de no-show: {overview.baseline_pct}%")
    lines.append("")
    lines.append("=== AGENDA POR DIA ===")
    for d in overview.days:
        line = (
            f"- {d.label} ({d.date_iso}): {d.total} consultas, "
            f"ocupação {d.ocupacao_pct}% do P95"
        )
        if d.faltas_esperadas_max > 0:
            line += f", {d.faltas_esperadas_min}–{d.faltas_esperadas_max} faltas esperadas"
        if d.confirmados > 0:
            line += f", {d.confirmados} confirmados ({d.confirmados_pct}% dos pendentes)"
        if d.riscos_altos > 0:
            line += f", {d.riscos_altos} pacientes com risco ≥ 30%"
        if d.encaixe_min > 0:
            h, m = divmod(d.encaixe_min, 60)
            line += f", janela livre de {h}h{m:02d}min entre consultas"
        lines.append(line)
    lines.append("")

    if overview.top_pacientes_risco:
        lines.append("=== PACIENTES EM RISCO (top 5 nos 3 dias) ===")
        for p in overview.top_pacientes_risco:
            lines.append(
                f"- {p.paciente_nome} {p.horario or '?'} com "
                f"{p.profissional_nome or 'prof'}: {p.risco_pct}% risco "
                f"({p.razao})"
            )
        lines.append("")

    if overview.top_profs_ociosos:
        lines.append("=== PROFISSIONAIS COM FOLGA (top 5 nos 3 dias) ===")
        for p in overview.top_profs_ociosos:
            lines.append(
                f"- {p.professional_nome or 'prof'}: {p.consultas_hoje}/"
                f"{p.consultas_teto_p95} consultas ({p.ocupacao_pct}% ocupação)"
            )
        lines.append("")

    if overview.waitlist_3d > 0 or overview.encaixe_3d > 0:
        lines.append("=== LISTA DE ESPERA ===")
        if overview.waitlist_3d:
            lines.append(f"- {overview.waitlist_3d} pacientes aguardando vaga nos 3 dias")
        if overview.encaixe_3d:
            lines.append(f"- {overview.encaixe_3d} marcações de encaixe explícito nos 3 dias")
        lines.append("")

    lines.append(
        "Devolva 3 a 4 frases que ajudem o gestor a decidir o que priorizar HOJE."
    )
    return "\n".join(lines)


def _cache_key(overview: StrategicOverview) -> str:
    """Hash do payload pra invalidar cache quando os números mudam."""
    payload = overview.model_dump_json()
    return "ai:agenda_summary:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


_CLIENT: Optional[AsyncAnthropic] = None


def _get_client() -> AsyncAnthropic:
    global _CLIENT
    if _CLIENT is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY não configurada no .env")
        _CLIENT = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _CLIENT


async def generate_agenda_narrative(
    overview: StrategicOverview,
    clinic_name: Optional[str] = None,
    redis=None,
) -> str:
    """Gera prosa narrativa para a HomePage do dono.

    Cache em Redis com TTL 5min — invalida automaticamente quando o snapshot
    muda (chave depende do hash do payload).
    """
    cache_key = _cache_key(overview)

    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached
        except Exception as e:
            logger.warning("Cache miss por erro Redis: %s", e)

    user_prompt = _build_user_prompt(overview, clinic_name)
    client = _get_client()

    try:
        msg = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except APIError as e:
        logger.exception("Erro chamando Anthropic API")
        raise RuntimeError(f"Anthropic API: {e}") from e

    # Extrai texto do bloco de resposta. Anthropic retorna lista de blocks.
    parts: list[str] = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    narrative = "\n".join(parts).strip()

    if not narrative:
        raise RuntimeError("Anthropic devolveu resposta vazia")

    if redis is not None:
        try:
            await redis.setex(cache_key, 300, narrative)  # 5 min TTL
        except Exception as e:
            logger.warning("Falha ao gravar cache: %s", e)

    return narrative
