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
import logging
from typing import Optional

from anthropic import AsyncAnthropic, APIError

from app.core.config import settings
from app.schemas.analise import AnaliseComercialResponse, AnaliseFinanceiroResponse
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


# ── Insights estratégicos do dashboard financeiro ───────────────


_FINANCEIRO_SYSTEM_PROMPT = """Você é um consultor financeiro sênior especializado em clínicas odontológicas.
Recebe os números de um mês de uma clínica e devolve insights estratégicos em português brasileiro para o DONO.

REGRAS:
- 4 a 6 frases curtas, em formato de bullets sem marcador (cada linha um insight).
- Use APENAS os números fornecidos. Nunca invente dado, paciente, prof.
- Cruze dimensões: ticket médio × conversão, mix de pagamento × concentração de risco, médico executante × atendente registrante. Encontre conexões NÃO óbvias.
- Aponte ação concreta quando relevante: "renegociar com X", "diversificar carteira", "investigar queda em Y".
- Foque em DONO (estratégia, riscos, oportunidades) — não em operação.
- NÃO repita números crus que já estão no card. Comente o que SIGNIFICAM.
- Tom: parceiro analítico do dono, direto, sem jargão.
- NÃO use markdown, headers, bullets. Apenas frases separadas por quebra de linha.

MÊS PARCIAL — REGRA CRÍTICA:
- Se o input indicar "MÊS EM ANDAMENTO", o mês NÃO ESTÁ FECHADO.
- Os valores absolutos (faturamento, recebido, contagens, valores por categoria/médico/forma de pagamento) refletem APENAS o acumulado parcial.
- NUNCA compare valores absolutos parciais diretamente com meses fechados.
- Use o campo "Projeção" quando fornecido. Diga explicitamente "no ritmo atual" / "projetando o mês completo" / "parcial até agora".
- Os MoM de mix_pagamento e categorias JÁ usam projeção do parcial vs mês anterior fechado — interprete com confiança.
- Variações negativas extremas (-80%, -90%) em mês muito recém-iniciado (ex: 7/31 dias) são esperadas e não significam queda real."""


def _build_financeiro_prompt(
    data: AnaliseFinanceiroResponse,
    clinic_name: Optional[str],
) -> str:
    """Serializa o dashboard financeiro num formato denso pra IA cruzar dimensões."""
    lines: list[str] = []
    lines.append(f"Clínica: {clinic_name or 'sem nome'}")
    lines.append(f"Período: {data.period.label}")

    fat = data.kpis.faturamento
    conv = data.kpis.conversao
    ticket = data.kpis.ticket_medio
    receb = data.kpis.recebido

    # Bloco crítico: avisa explicitamente quando é mês em andamento
    if fat.is_partial and fat.partial_days and fat.partial_days_in_month:
        progress_pct = int((fat.partial_progress or 0) * 100)
        lines.append("")
        lines.append("⚠ MÊS EM ANDAMENTO ⚠")
        lines.append(
            f"Hoje é dia {fat.partial_days} de {fat.partial_days_in_month} ({progress_pct}% do mês). "
            f"Os valores absolutos refletem APENAS o acumulado parcial."
        )
        lines.append(
            "MoM de mix_pagamento e top_categorias JÁ aplicam projeção (parcial × dias_no_mês / dias_decorridos) "
            "vs mês anterior fechado, então pode interpretá-los normalmente."
        )
        lines.append(
            "MoM dos KPIs principais (faturamento/recebido) também usa projeção. "
            "Use linguagem de projeção: 'no ritmo atual', 'projetando o mês completo'."
        )
    lines.append("")

    lines.append("=== KPIs PRINCIPAIS ===")
    fat_line = f"- Faturamento (orçamentos aprovados): {fat.value_label}"
    if fat.is_partial and fat.projected_label:
        fat_line += f" → projeção fim do mês: {fat.projected_label}"
    lines.append(fat_line)
    if fat.mom_pct is not None:
        suffix = " (projeção)" if fat.is_partial else ""
        if fat.yoy_pct is not None:
            lines.append(f"  MoM {fat.mom_pct:+.1f}% | YoY {fat.yoy_pct:+.1f}%{suffix}")
        else:
            lines.append(f"  MoM {fat.mom_pct:+.1f}%{suffix}")
    lines.append(f"- Conversão (R$): {conv.value_label} (insight backend: {conv.insight or 'n/a'})")
    lines.append(f"- Ticket médio: {ticket.value_label}")
    if ticket.mom_pct is not None:
        lines.append(f"  MoM {ticket.mom_pct:+.1f}%")
    receb_line = f"- Recebido (caixa): {receb.value_label}"
    if receb.is_partial and receb.projected_label:
        receb_line += f" → projeção: {receb.projected_label}"
    lines.append(receb_line)
    if receb.mom_pct is not None:
        suffix = " (projeção)" if receb.is_partial else ""
        lines.append(f"  MoM {receb.mom_pct:+.1f}%{suffix}")
    lines.append("")

    funil = data.funil
    lines.append("=== FUNIL DE ORÇAMENTOS ===")
    lines.append(f"- Gerados: {funil.gerados_qty} ({funil.gerados_amount:.0f})")
    lines.append(f"- Aprovados: {funil.aprovados_qty} ({funil.aprovados_amount:.0f})")
    lines.append(f"- Conversão por R$: {funil.conversao_aprovacao_valor_pct}% | por qtd: {funil.conversao_aprovacao_pct}%")
    lines.append("")

    if data.top_medicos:
        lines.append("=== TOP MÉDICOS (executantes) ===")
        for m in data.top_medicos[:5]:
            lines.append(
                f"- {m.nome}: R${m.faturamento:.0f} ({m.pct_total}%), "
                f"{m.qtd_procedimentos} proc, ticket {m.ticket_medio_procedimento:.0f}/proc"
            )
        lines.append("")

    if data.top_profissionais:
        lines.append("=== TOP ATENDENTES (registrantes) ===")
        for p in data.top_profissionais[:5]:
            lines.append(
                f"- {p.nome}: R${p.faturamento:.0f} ({p.pct_total}%), "
                f"conversão {p.taxa_conversao_valor_pct}% R$ / {p.taxa_conversao_pct}% qtd"
            )
        lines.append("")

    if data.top_categorias:
        lines.append("=== TOP CATEGORIAS ===")
        for c in data.top_categorias[:5]:
            mom = f", MoM {c.mom_pct:+.1f}%" if c.mom_pct is not None else ""
            lines.append(f"- {c.categoria}: R${c.faturamento:.0f} ({c.pct_total}%){mom}")
        lines.append("")

    if data.mix_pagamento:
        lines.append("=== MIX DE PAGAMENTO ===")
        for m in data.mix_pagamento[:5]:
            mom = f", MoM {m.mom_pct:+.1f}%" if m.mom_pct is not None else ""
            lines.append(f"- {m.forma_pagamento}: R${m.valor:.0f} ({m.pct}%){mom}")
        lines.append("")

    lines.append("Devolva 4 a 6 insights cruzando dimensões. Foque em conexões não óbvias e ações para o dono.")
    return "\n".join(lines)


def _financeiro_cache_key(data: AnaliseFinanceiroResponse) -> str:
    payload = data.model_dump_json()
    return "ai:financeiro_insights:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


async def generate_financeiro_insights(
    data: AnaliseFinanceiroResponse,
    clinic_name: Optional[str] = None,
    redis=None,
) -> str:
    """Gera insights estratégicos cruzados pro dashboard financeiro.

    Cache Redis 5min — chave hasheia o payload, então só refaz a chamada
    quando os números mudam.
    """
    cache_key = _financeiro_cache_key(data)

    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached
        except Exception as e:
            logger.warning("Cache miss financeiro: %s", e)

    user_prompt = _build_financeiro_prompt(data, clinic_name)
    client = _get_client()

    try:
        msg = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=600,
            system=_FINANCEIRO_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except APIError as e:
        logger.exception("Erro Anthropic API (financeiro)")
        raise RuntimeError(f"Anthropic API: {e}") from e

    parts: list[str] = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    narrative = "\n".join(parts).strip()

    if not narrative:
        raise RuntimeError("Anthropic devolveu resposta vazia")

    if redis is not None:
        try:
            await redis.setex(cache_key, 300, narrative)
        except Exception as e:
            logger.warning("Falha ao gravar cache financeiro: %s", e)

    return narrative


# ── Insights estratégicos do dashboard COMERCIAL ────────────────


_COMERCIAL_SYSTEM_PROMPT = """Você é um consultor de operações comerciais sênior em clínicas odontológicas.
Recebe os números operacionais de um mês e devolve insights estratégicos em português brasileiro para o DONO.

FOCO COMERCIAL (não confundir com financeiro):
- Volume de consultas, absenteísmo, ocupação dos profissionais
- Conversão consulta → orçamento → aprovação (a "máquina de vendas")
- Procedimentos mais executados, especialidades em demanda
- Mix de categorias (consulta x retorno x manutenção)
- Encaixe, retornos pendentes, perda potencial em cancelamentos

REGRAS:
- 4 a 6 frases curtas, formato bullet sem marcador (cada linha um insight).
- Use APENAS os números fornecidos. Nunca invente paciente, prof ou métrica.
- Cruze dimensões: absenteísmo × profissional, conversão × especialidade, encaixe × demanda. Conexões NÃO óbvias.
- Aponte ação: "investir em remarcar X", "redirecionar agenda do prof Y", "explorar capacidade ociosa em Z".
- Foque em DONO da operação — riscos, gargalos, oportunidades de capacidade.
- NÃO repita números crus visíveis. Comente o SIGNIFICADO.
- NÃO use markdown, headers, bullets. Só frases separadas por quebra de linha.
- Tom: parceiro analítico do gestor.

MÊS PARCIAL — REGRA CRÍTICA:
- Se houver "MÊS EM ANDAMENTO", o mês ainda NÃO FECHOU.
- Valores absolutos (consultas, pacientes únicos, procedimentos) refletem APENAS o acumulado parcial.
- KPIs de PERCENTUAL (absenteísmo, conversão) já são proporcionais e podem ser interpretados normalmente.
- MoM de mix_categorias JÁ usa projeção do parcial vs mês fechado.
- Use linguagem "no ritmo atual", "projetando o mês completo" para volumes."""


def _build_comercial_prompt(
    data: AnaliseComercialResponse,
    clinic_name: Optional[str],
) -> str:
    """Serializa o dashboard comercial num formato denso para a IA cruzar dimensões."""
    lines: list[str] = []
    lines.append(f"Clínica: {clinic_name or 'sem nome'}")
    lines.append(f"Período: {data.period.label}")

    consultas = data.kpis.consultas
    absent = data.kpis.absenteismo_pct
    ticket = data.kpis.ticket_medio_consulta
    conv = data.kpis.conversao_consulta_orcamento_pct
    pac = data.kpis.pacientes_unicos

    if consultas.is_partial and consultas.partial_days and consultas.partial_days_in_month:
        progress_pct = int((consultas.partial_progress or 0) * 100)
        lines.append("")
        lines.append("⚠ MÊS EM ANDAMENTO ⚠")
        lines.append(
            f"Hoje é dia {consultas.partial_days} de {consultas.partial_days_in_month} ({progress_pct}% do mês)."
        )
        lines.append(
            "Volumes (consultas, pacientes) são parciais — KPIs principais usam projeção. "
            "MoM de mix_categorias já aplica projeção (parcial × dias_no_mês / dias_decorridos) vs mês fechado."
        )
    lines.append("")

    lines.append("=== KPIs PRINCIPAIS ===")
    cline = f"- Consultas executadas: {consultas.value_label}"
    if consultas.is_partial and consultas.projected_label:
        cline += f" → projeção: {consultas.projected_label}"
    lines.append(cline)
    if consultas.mom_pct is not None:
        suf = " (projeção)" if consultas.is_partial else ""
        lines.append(f"  MoM {consultas.mom_pct:+.1f}%{suf}")
    lines.append(f"- Absenteísmo: {absent.value_label} (insight: {absent.insight or 'n/a'})")
    if absent.mom_pct is not None:
        lines.append(f"  MoM {absent.mom_pct:+.1f}pp")
    lines.append(f"- Ticket médio por consulta executada: {ticket.value_label}")
    lines.append(f"- Conversão consulta → orçamento aprovado: {conv.value_label}")
    pline = f"- Pacientes únicos atendidos: {pac.value_label}"
    if pac.is_partial and pac.projected_label:
        pline += f" → projeção: {pac.projected_label}"
    lines.append(pline)
    lines.append("")

    funil = data.funil
    lines.append("=== FUNIL COMERCIAL (por paciente) ===")
    lines.append(
        f"- Consultas executadas: {funil.consultas_executadas} | "
        f"Pacientes com orçamento gerado: {funil.com_orcamento_qty} | "
        f"Pacientes com orçamento aprovado: {funil.aprovados_qty} (R${funil.aprovados_amount:.0f})"
    )
    lines.append(
        f"- Taxa de oferta de orçamento: {funil.taxa_oferta_pct}% | "
        f"Taxa de aprovação: {funil.taxa_aprovacao_pct}% | "
        f"Conversão total consulta→aprovado: {funil.taxa_conversao_total_pct}%"
    )
    if funil.tempo_medio_consulta_aprov_dias is not None:
        lines.append(f"- Tempo médio consulta → aprovação: {funil.tempo_medio_consulta_aprov_dias:.0f} dias")
    lines.append("")

    if data.top_procedimentos:
        lines.append("=== TOP PROCEDIMENTOS EXECUTADOS ===")
        for p in data.top_procedimentos[:5]:
            lines.append(
                f"- {p.procedure_name}: {p.qtd_executados} executados ({p.pct_volume}%), "
                f"R${p.faturamento:.0f}, ticket {p.ticket_medio:.0f}"
            )
        lines.append("")

    if data.top_especialidades:
        lines.append("=== TOP ESPECIALIDADES EM DEMANDA ===")
        for e in data.top_especialidades[:5]:
            lines.append(
                f"- {e.especialidade}: {e.qtd_procedimentos} procedimentos "
                f"({e.pct_volume}%), R${e.faturamento:.0f}"
            )
        lines.append("")

    if data.top_profissionais:
        lines.append("=== TOP PROFISSIONAIS POR VOLUME DE CONSULTAS ===")
        for prof in data.top_profissionais[:5]:
            lines.append(
                f"- {prof.nome}: {prof.qtd_consultas} consultas ({prof.pct_volume}%), "
                f"{prof.qtd_canceladas} canceladas ({prof.absenteismo_pct}% absenteísmo), "
                f"{prof.pacientes_distintos} pacientes únicos"
            )
        lines.append("")

    if data.mix_categorias:
        lines.append("=== MIX DE CATEGORIAS DE CONSULTA ===")
        for c in data.mix_categorias[:6]:
            mom = f", MoM {c.mom_pct:+.1f}%" if c.mom_pct is not None else ""
            lines.append(
                f"- {c.categoria}: {c.qtd} ({c.pct}%), "
                f"{c.canceladas} canceladas ({c.absenteismo_pct}%){mom}"
            )
        lines.append("")

    op = data.operacional
    lines.append("=== OPERACIONAL ===")
    lines.append(
        f"- Encaixe: {op.encaixe_qty} ({op.encaixe_pct}%) | "
        f"Retorno pendente: {op.retorno_pendente_qty} | "
        f"Marcadas pra remarcar: {op.remarcar_qty}"
    )
    lines.append(
        f"- Cancelados: {op.cancelados_qty} | "
        f"Perda potencial estimada (cancelados × ticket médio): R${op.cancelados_amount_estimado:.0f}"
    )
    lines.append("")

    lines.append("Devolva 4 a 6 insights cruzando dimensões. Foque em ações operacionais para o dono.")
    return "\n".join(lines)


def _comercial_cache_key(data: AnaliseComercialResponse) -> str:
    payload = data.model_dump_json()
    return "ai:comercial_insights:" + hashlib.sha256(payload.encode()).hexdigest()[:16]


async def generate_comercial_insights(
    data: AnaliseComercialResponse,
    clinic_name: Optional[str] = None,
    redis=None,
) -> str:
    """Gera insights estratégicos cruzados pro dashboard comercial.

    Cache Redis 5min — chave hasheia o payload, refaz só quando os números mudam.
    """
    cache_key = _comercial_cache_key(data)

    if redis is not None:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return cached.decode() if isinstance(cached, bytes) else cached
        except Exception as e:
            logger.warning("Cache miss comercial: %s", e)

    user_prompt = _build_comercial_prompt(data, clinic_name)
    client = _get_client()

    try:
        msg = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=600,
            system=_COMERCIAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except APIError as e:
        logger.exception("Erro Anthropic API (comercial)")
        raise RuntimeError(f"Anthropic API: {e}") from e

    parts: list[str] = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    narrative = "\n".join(parts).strip()

    if not narrative:
        raise RuntimeError("Anthropic devolveu resposta vazia")

    if redis is not None:
        try:
            await redis.setex(cache_key, 300, narrative)
        except Exception as e:
            logger.warning("Falha ao gravar cache comercial: %s", e)

    return narrative
