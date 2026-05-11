/**
 * Dashboard comercial segmentado (Sub-PR 20c).
 * Foco: VOLUME + EFICIÊNCIA OPERACIONAL — máquina de consultas/conversão.
 *
 * Estrutura:
 * 1. Header + PeriodSelector
 * 2. Banner mês parcial (quando aplicável)
 * 3. Insights via IA (botão sob demanda)
 * 4. KPIs principais (5 cards: consultas, absenteísmo, ticket/consulta, conversão, pacientes únicos)
 * 5. Funil comercial (consulta → orçamento → aprovação)
 * 6. Evolution chart (12 meses: consultas + canceladas)
 * 7. Top procedimentos + Top especialidades
 * 8. Top profissionais por consultas
 * 9. Mix de categorias + Operacional
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, BarChart3, Briefcase, CalendarClock,
  CheckCircle2, FileText, HelpCircle, Loader2, Target, TrendingUp, UserCheck, Users, XCircle,
} from 'lucide-react'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
} from 'recharts'

import { usePageTitle } from '@/contexts/PageTitleContext'
import { analiseService } from '@/services/analise.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageFooter } from '@/components/layout/PageFooter'
import type {
  AnaliseComercialResponse, ConversaoBreakdown, FunilComercial, MixCategoriaConsulta,
  OperacionalComercial, SaudeAgendaSection, TopEspecialidadeDemanda,
  TopProcedimentoExecutado, TopProfissionalConsultas,
} from '@/types/analise'

import { KpiCardEnriched } from '../components/KpiCardEnriched'
import { PeriodSelector } from '../components/PeriodSelector'
import { useSonIA, type SonIAInsight } from '@/components/sonia/SonIAContext'

// ── Helpers ───────────────────────────────────────────────────

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000_000)
    return `R$ ${(n / 1_000_000).toFixed(2)}M`
  if (compact && Math.abs(n) >= 1_000)
    return `R$ ${(n / 1_000).toFixed(0)}k`
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
  }).format(n)
}
const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtPct = (n: number | null | undefined) => {
  if (n === null || n === undefined) return null
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

// ── Page ──────────────────────────────────────────────────────

export default function ComercialPage() {
  usePageTitle('Análise Comercial')

  const today = new Date()
  const [period, setPeriod] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 })

  const query = useQuery({
    queryKey: ['analise', 'comercial', period.year, period.month],
    queryFn: () => analiseService.comercial(period.year, period.month),
    staleTime: 60_000,
  })

  const { publish, clear } = useSonIA()
  useEffect(() => {
    if (!query.data) return
    publish({
      pageKey: '/analise/comercial',
      pageTitle: 'Análise Comercial',
      data: { insight: buildAnaliseComercialInsight(query.data) },
    })
    return () => clear('/analise/comercial')
  }, [query.data, publish, clear])

  return (
    <PageContainer>
      <PageHeader
        eyebrow="ANÁLISE"
        title="Dashboard Comercial"
        subtitle="Volume, conversão e operação"
        icon={<Briefcase size={20} />}
        filters={
          <PeriodSelector
            year={period.year}
            month={period.month}
            onChange={(y, m) => setPeriod({ year: y, month: m })}
          />
        }
      />
      {query.isLoading && (
        <div className="flex items-center justify-center py-12 text-neutral-500 gap-2">
          <Loader2 className="animate-spin" size={18} /> Carregando análise comercial...
        </div>
      )}
      {query.isError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-800 text-sm">
          Erro ao carregar dashboard. Tente novamente.
        </div>
      )}
      {query.data && <Body data={query.data} />}
      <PageFooter dataSource="Clinicorp" />
    </PageContainer>
  )
}

// ── Body ──────────────────────────────────────────────────────

function Body({ data }: { data: AnaliseComercialResponse }) {
  const consultas = data.kpis.consultas
  return (
    <>
      {consultas.is_partial && consultas.partial_days && consultas.partial_days_in_month && (
        <PartialMonthBanner
          days={consultas.partial_days}
          daysInMonth={consultas.partial_days_in_month}
          progress={consultas.partial_progress ?? 0}
        />
      )}

      {/* KPIs principais — 4 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCardEnriched
          data={data.kpis.consultas}
          label="Consultas atendidas"
          icon={<CheckCircle2 size={14} className="text-emerald-700" />}
          iconBg="bg-emerald-50"
          emphasized
        />
        <KpiCardEnriched
          data={data.kpis.absenteismo_pct}
          label="Absenteísmo (faltas)"
          icon={<XCircle size={14} className="text-rose-700" />}
          iconBg="bg-rose-50"
        />
        <KpiCardEnriched
          data={data.kpis.conversao_consulta_orcamento_pct}
          label="Conversão em orçamento"
          icon={<Target size={14} className="text-blue-700" />}
          iconBg="bg-blue-50"
          helpTooltip={<ConversaoTooltip data={data.kpis.conversao_breakdown} />}
        />
        <KpiCardEnriched
          data={data.kpis.pacientes_unicos}
          label="Pacientes atendidos"
          icon={<Users size={14} className="text-cyan-700" />}
          iconBg="bg-cyan-50"
        />
      </div>

      {/* Saúde da agenda — fluxo completo: efetivas/faltas/cancel/indef */}
      <SaudeAgendaCard data={data.saude_agenda} />

      {/* Funil + Evolution */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <FunilCard data={data.funil} />
        <EvolutionChart data={data.evolution} />
      </div>

      {/* Top procedimentos + Top especialidades */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TopProcedimentosCard data={data.top_procedimentos} consultasEfetivas={data.kpis.consultas.value} />
        <TopEspecialidadesCard data={data.top_especialidades} consultasEfetivas={data.kpis.consultas.value} />
      </div>

      {/* Top profissionais (linha cheia) */}
      <TopProfsConsultasCard
        data={data.top_profissionais}
        absMediaClinica={data.kpis.absenteismo_pct.value}
      />

      {/* Mix categorias + Operacional */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <MixCategoriasCard data={data.mix_categorias} />
        <OperacionalCard data={data.operacional} />
      </div>
    </>
  )
}

// ── Conversão — tooltip explicativo ───────────────────────────
//
// Decompõe os 100% do denominador da Conversão em 5 status. Pacientes que
// estão em tratamento (já aprovaram em mês anterior) e avulsos puros (nunca
// tiveram orçamento) não deveriam ser lidos como "não converteu".

function ConversaoTooltip({ data }: { data: ConversaoBreakdown }) {
  const fmtN = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
  const linhas = [
    { label: 'Aprovou orçamento neste mês',  qtd: data.aprovou_no_mes,        pct: data.aprovou_no_mes_pct,        color: 'text-emerald-300' },
    { label: 'Gerou orçamento — em decisão', qtd: data.gerou_nao_aprovou,     pct: data.gerou_nao_aprovou_pct,     color: 'text-amber-300'   },
    { label: 'Em tratamento (aprovou antes)', qtd: data.em_tratamento,        pct: data.em_tratamento_pct,         color: 'text-sky-300'     },
    { label: 'Avulso — nunca teve orçamento', qtd: data.avulso_sem_orcamento, pct: data.avulso_sem_orcamento_pct,  color: 'text-rose-300'    },
    { label: 'Histórico antigo sem aprovar',  qtd: data.historico_sem_aprov,  pct: data.historico_sem_aprov_pct,   color: 'text-neutral-400' },
  ].filter((l) => l.qtd > 0)
  return (
    <div className="space-y-2">
      <div className="font-semibold text-[11.5px]">
        Decomposição dos {fmtN(data.total_atendidos)} pacientes atendidos
      </div>
      <ul className="space-y-1">
        {linhas.map((l) => (
          <li key={l.label} className="flex items-baseline gap-2">
            <span className={`${l.color} font-bold tabular-nums w-10 text-right shrink-0`}>
              {l.pct.toFixed(1)}%
            </span>
            <span className="text-neutral-300 tabular-nums w-8 text-right shrink-0">
              {fmtN(l.qtd)}
            </span>
            <span className="text-neutral-100">{l.label}</span>
          </li>
        ))}
      </ul>
      <div className="text-[10px] text-neutral-400 leading-snug pt-1 border-t border-neutral-700">
        A conversão (verde) só conta quem aprovou orçamento <em>no próprio mês</em>.
        Os demais não são necessariamente perdas: pacientes em tratamento já fecharam
        antes; avulsos costumam vir só pra retorno/manutenção.
      </div>
    </div>
  )
}

// ── Saúde da agenda ───────────────────────────────────────────
//
// Decompõe o universo de agendamentos do mês em 5 desfechos: efetivas
// (paciente atendido — base p/ KPIs e tops), faltas (absenteísmo real),
// canceladas (qualquer motivo), indefinidas (recepção não atualizou status)
// e outros (CONFIRMED/ARRIVED/IN_SESSION/LATE/CALL não-cancelados).

function SaudeAgendaCard({ data }: { data: SaudeAgendaSection }) {
  const fmtN = (n: number) => new Intl.NumberFormat('pt-BR').format(n)

  const segments = [
    { key: 'efetivas',    label: 'Efetivas',    qtd: data.efetivas,    pct: data.pct_efetivas,    bar: 'bg-emerald-500', text: 'text-emerald-700', bg: 'bg-emerald-50' },
    { key: 'faltas',      label: 'Faltas',      qtd: data.faltas,      pct: data.pct_faltas,      bar: 'bg-rose-500',    text: 'text-rose-700',    bg: 'bg-rose-50'    },
    { key: 'canceladas',  label: 'Canceladas',  qtd: data.canceladas,  pct: data.pct_canceladas,  bar: 'bg-orange-500',  text: 'text-orange-700',  bg: 'bg-orange-50'  },
    { key: 'indefinidas', label: 'Sem status',  qtd: data.indefinidas, pct: data.pct_indefinidas, bar: 'bg-neutral-400', text: 'text-neutral-700', bg: 'bg-neutral-100' },
    { key: 'outros',      label: 'Outros',      qtd: data.outros,      pct: data.pct_outros,      bar: 'bg-sky-400',     text: 'text-sky-700',     bg: 'bg-sky-50'     },
  ].filter((s) => s.qtd > 0)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-4 flex items-start justify-between gap-4 flex-wrap border-b border-neutral-100">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Saúde da agenda
          </div>
          <div className="text-sm text-neutral-700 mt-0.5">
            <strong className="text-neutral-900">{fmtN(data.total)}</strong> agendamentos no mês ·
            absenteísmo clínico <strong className="text-rose-700 tabular-nums">{data.absenteismo_clinico_pct.toFixed(1)}%</strong>
          </div>
        </div>
        <div className="text-[10px] text-neutral-500 max-w-sm">
          Absenteísmo = faltas / (efetivas + faltas). Cancelamentos não entram —
          cancel pela clínica/com aviso ≠ paciente faltar.
        </div>
      </header>

      <div className="px-5 py-3">
        <div className="flex h-7 rounded-md overflow-hidden ring-1 ring-neutral-200">
          {segments.map((s) => (
            <div
              key={s.key}
              className={`${s.bar} flex items-center justify-center text-[10.5px] font-bold text-white transition`}
              style={{ width: `${Math.max(s.pct, 2)}%` }}
              title={`${s.label}: ${fmtN(s.qtd)} (${s.pct.toFixed(1)}%)`}
            >
              {s.pct >= 8 ? `${s.pct.toFixed(0)}%` : ''}
            </div>
          ))}
        </div>
      </div>

      <div className="px-5 pb-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        {segments.map((s) => (
          <div key={s.key} className={`${s.bg} rounded-md px-3 py-2`}>
            <div className="flex items-center gap-2">
              <span className={`w-2 h-6 rounded-sm ${s.bar} shrink-0`} />
              <div className="min-w-0">
                <div className={`text-[11px] font-semibold ${s.text}`}>{s.label}</div>
                <div className="flex items-baseline gap-1.5">
                  <span className="text-base font-bold text-neutral-900 tabular-nums">{fmtN(s.qtd)}</span>
                  <span className="text-[10px] text-neutral-500 tabular-nums">{s.pct.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// ── Insight pra SonIA ─────────────────────────────────────────

function buildAnaliseComercialInsight(data: AnaliseComercialResponse): SonIAInsight {
  const cons = data.kpis.consultas
  const abs = data.kpis.absenteismo_pct
  const conv = data.kpis.conversao_consulta_orcamento_pct
  const pac = data.kpis.pacientes_unicos

  // Mês em andamento: suprimir MoM e mostrar projeção quando disponível.
  if (cons.is_partial) {
    const days = cons.partial_days ?? 0
    const total = cons.partial_days_in_month ?? 30
    const pctMes = total > 0 ? Math.round((days / total) * 100) : 0
    const proj = cons.projected_label

    // Absenteísmo continua válido (é taxa, não acumulado) — alerta se alto.
    const absHigh = abs.value !== null && abs.value >= 15
    return {
      mood: absHigh ? 'alert' : 'curious',
      headline: absHigh
        ? `Olhei o que temos até agora — tenho uma observação.`
        : `Olhei o que temos de ${data.period.label} até agora.`,
      detail: absHigh
        ? `Estamos no dia ${days} de ${total} (${pctMes}% do mês). O absenteísmo está em ${abs.value_label} — um pouco acima do confortável. Vale conversar com a equipe sobre confirmações.`
        : `Estamos no dia ${days} de ${total} (${pctMes}% do mês). Por enquanto ${cons.value_label} consultas${proj ? `, com projeção de ${proj}` : ''}. Espero o mês fechar pra comparar com confiança.`,
      bullets: [
        { text: `${cons.value_label} consultas${proj ? ` · projeção ${proj}` : ''}.`, tone: 'neutral' },
        { text: `Absenteísmo ${abs.value_label}.`, tone: absHigh ? 'negative' : 'neutral' },
        { text: `Conversão em orçamento ${conv.value_label}.`, tone: 'neutral' },
        { text: `Pacientes únicos ${pac.value_label}.`, tone: 'neutral' },
      ],
    }
  }

  const absHigh = abs.value !== null && abs.value >= 15
  const convDown = conv.mom_pct !== null && conv.mom_pct <= -5

  const mood = absHigh || convDown ? 'alert' : 'curious'
  const headline = absHigh
    ? 'Dei uma olhadinha aqui — tem algo pra olharmos juntos.'
    : convDown
    ? 'Vi algumas coisas que vale a pena olhar.'
    : 'Olhei a página com calma.'

  const detail = absHigh
    ? `O absenteísmo de ${data.period.label} está em ${abs.value_label} — um pouco acima do confortável. Vale conversar com a equipe sobre confirmações.`
    : convDown
    ? `A conversão de consulta em orçamento caiu ${Math.abs(conv.mom_pct!).toFixed(1)}% em relação ao mês passado. Quem sabe a gente investiga as últimas oportunidades?`
    : `${data.period.label} foram ${cons.value_label} consultas atendidas. Trouxe um resumo do que observei.`

  const bullets = [
    { text: `${cons.value_label} consultas${pctSuffix(cons.mom_pct)}.`, tone: tonePctC(cons.mom_pct, false) },
    { text: `Absenteísmo ${abs.value_label}${pctSuffix(abs.mom_pct)}.`, tone: tonePctC(abs.mom_pct, true) },
    { text: `Conversão em orçamento ${conv.value_label}${pctSuffix(conv.mom_pct)}.`, tone: tonePctC(conv.mom_pct, false) },
    { text: `Pacientes únicos ${pac.value_label}${pctSuffix(pac.mom_pct)}.`, tone: tonePctC(pac.mom_pct, false) },
  ] as SonIAInsight['bullets']

  return { mood, headline, detail, bullets }
}

function pctSuffix(p: number | null): string {
  if (p === null) return ''
  const sign = p > 0 ? '+' : ''
  return ` (${sign}${p.toFixed(1)}% vs mês passado)`
}

function tonePctC(p: number | null, inverse: boolean): 'positive' | 'negative' | 'neutral' | 'warning' {
  if (p === null) return 'neutral'
  if (Math.abs(p) < 2) return 'neutral'
  const positivo = inverse ? p < 0 : p > 0
  if (positivo) return 'positive'
  return Math.abs(p) >= 10 ? 'negative' : 'warning'
}

// ── Banner mês parcial ────────────────────────────────────────

function PartialMonthBanner({
  days, daysInMonth, progress,
}: { days: number; daysInMonth: number; progress: number }) {
  const pct = Math.round(progress * 100)
  return (
    <div className="flex items-center gap-3 bg-sky-50/70 border border-sky-200 rounded-lg px-4 py-2.5 text-[12px] text-sky-900">
      <CalendarClock size={15} className="text-sky-600 shrink-0" />
      <span className="font-semibold">Mês em andamento</span>
      <span className="text-sky-700">·</span>
      <span className="tabular-nums">{days} de {daysInMonth} dias ({pct}%)</span>
      <span className="text-sky-700/80 ml-auto hidden sm:block">
        Volumes mostram acumulado parcial; KPIs comparam projeção do ritmo atual.
      </span>
    </div>
  )
}

// ── Funil comercial ───────────────────────────────────────────

function FunilTooltip({ data }: { data: FunilComercial }) {
  const fmtN = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
  return (
    <div className="space-y-2.5">
      <div className="font-semibold text-[11.5px]">Como ler este funil</div>

      <div className="space-y-1.5">
        <div>
          <span className="text-blue-300 font-bold">Pacientes atendidos ({fmtN(data.pacientes_atendidos)})</span>
          <div className="text-neutral-300 leading-snug">
            Pacientes <em>distintos</em> com pelo menos 1 consulta status <strong>Atendido</strong> (CHECKOUT) no mês.
            Os {fmtN(data.total_consultas)} eventos de consulta cabem nesses {fmtN(data.pacientes_atendidos)} pacientes (média {(data.total_consultas / Math.max(data.pacientes_atendidos, 1)).toFixed(1)} consulta/paciente).
          </div>
        </div>

        <div>
          <span className="text-emerald-300 font-bold">Pacientes com orçamento ({fmtN(data.com_orcamento_qty)})</span>
          <div className="text-neutral-300 leading-snug">
            Subconjunto dos atendidos que tiveram pelo menos 1 orçamento <em>gerado no próprio mês</em> (qualquer status: aberto/aprovado/rejeitado).
            <strong className="text-emerald-300"> {data.taxa_oferta_pct.toFixed(1)}%</strong> dos atendidos.
          </div>
        </div>

        <div>
          <span className="text-cyan-300 font-bold">Pacientes aprovados ({fmtN(data.aprovados_qty)})</span>
          <div className="text-neutral-300 leading-snug">
            Desses, quantos aprovaram pelo menos 1 orçamento. <strong className="text-cyan-300">{data.taxa_aprovacao_pct.toFixed(1)}%</strong> dos com orçamento — mede a qualidade da abordagem comercial.
            R$ {fmtN(Math.round(data.aprovados_amount))} de faturamento aprovado.
          </div>
        </div>
      </div>

      <div className="pt-2 border-t border-neutral-700 space-y-1">
        <div>
          <span className="text-neutral-100 font-semibold">Conversão Total ({data.taxa_conversao_total_pct.toFixed(1)}%)</span>
          <div className="text-neutral-400 leading-snug">
            Aprovados ÷ atendidos = {fmtN(data.aprovados_qty)} ÷ {fmtN(data.pacientes_atendidos)}. Mesmo cálculo do KPI "Conversão em orçamento".
          </div>
        </div>
        <div>
          <span className="text-neutral-100 font-semibold">Tempo Médio</span>
          <div className="text-neutral-400 leading-snug">
            Dias entre a 1ª consulta do paciente no mês e a aprovação do orçamento. Tempo curto = decisão rápida.
          </div>
        </div>
      </div>

      <div className="text-[10px] text-neutral-500 leading-snug pt-1 border-t border-neutral-700">
        Pacientes em tratamento (já fecharam orçamento em mês anterior) não aparecem aqui — o funil só vê o que foi gerado/aprovado <em>no mês corrente</em>.
      </div>
    </div>
  )
}

function FunilCard({ data }: { data: FunilComercial }) {
  // Funil 100% por PACIENTE (igual KPI). total_consultas é só contexto de volume.
  const max = Math.max(data.pacientes_atendidos, data.com_orcamento_qty, data.aprovados_qty, 1)
  const stages = [
    {
      label: 'Pacientes atendidos',
      qty: data.pacientes_atendidos,
      color: 'bg-blue-500',
      hint: `${fmtNum(data.total_consultas)} consultas em ${fmtNum(data.pacientes_atendidos)} pacientes`,
    },
    {
      label: 'Pacientes com orçamento',
      qty: data.com_orcamento_qty,
      color: 'bg-emerald-500',
      hint: `${data.taxa_oferta_pct.toFixed(1)}% dos atendidos`,
    },
    {
      label: 'Pacientes aprovados',
      qty: data.aprovados_qty,
      color: 'bg-cyan-500',
      hint: `${data.taxa_aprovacao_pct.toFixed(1)}% dos com orçamento · ${fmtBRL(data.aprovados_amount, true)}`,
    },
  ]
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Funil Comercial — Paciente atendido → Orçamento → Aprovação
        </span>
        <span className="relative group/tip shrink-0 ml-auto">
          <HelpCircle
            size={13}
            className="text-neutral-400 hover:text-neutral-600 cursor-help"
            aria-label="Como ler o funil"
          />
          <div className="hidden group-hover/tip:block absolute z-20 right-0 top-full mt-1 w-80 bg-neutral-900 text-white text-[11px] leading-snug rounded-lg shadow-xl p-3 normal-case tracking-normal font-normal">
            <FunilTooltip data={data} />
          </div>
        </span>
      </div>
      <div className="space-y-2.5">
        {stages.map((s) => {
          const pct = (s.qty / max) * 100
          return (
            <div key={s.label}>
              <div className="flex items-center justify-between mb-1 text-[12px]">
                <span className="font-semibold text-neutral-700">{s.label}</span>
                <span className="font-bold tabular-nums text-neutral-900">
                  {fmtNum(s.qty)}
                </span>
              </div>
              <div className="h-3 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${s.color} rounded-full transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
              {s.hint && <div className="text-[10px] text-neutral-500 mt-0.5">{s.hint}</div>}
            </div>
          )
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-neutral-100 grid grid-cols-2 gap-3 text-[12px]">
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-400">Conversão Total</div>
          <div className="font-bold text-cyan-700 text-lg">{data.taxa_conversao_total_pct.toFixed(1)}%</div>
          <div className="text-[10px] text-neutral-400">atendido → aprovado</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-400">Tempo Médio</div>
          <div className="font-bold text-purple-700 text-lg">
            {data.tempo_medio_consulta_aprov_dias !== null
              ? `${data.tempo_medio_consulta_aprov_dias.toFixed(0)}d`
              : '—'}
          </div>
          <div className="text-[10px] text-neutral-400">consulta → aprovação</div>
        </div>
      </div>
    </div>
  )
}

// ── Evolution chart ───────────────────────────────────────────
//
// Barra empilhada por mês com os 4 desfechos da agenda (Atendidas / Faltas /
// Canceladas / Sem status). Cores espelham o card "Saúde da Agenda" pra
// criar coerência visual entre as duas visões. Total da barra ≈ volume
// agendado do mês — permite ver simultaneamente volume e composição.

const EVOLUTION_COLORS = {
  efetivas:    { fill: '#10b981', label: 'Atendidas',  stroke: 'text-emerald-300' },
  faltas:      { fill: '#f43f5e', label: 'Faltas',     stroke: 'text-rose-300'    },
  canceladas:  { fill: '#f97316', label: 'Canceladas', stroke: 'text-orange-300'  },
  indefinidas: { fill: '#a3a3a3', label: 'Sem status', stroke: 'text-neutral-400' },
} as const

function EvolutionTooltip() {
  return (
    <div className="space-y-2">
      <div className="font-semibold text-[11.5px]">Como ler o gráfico</div>
      <div className="text-neutral-300 leading-snug">
        Cada barra é o <strong>fluxo da agenda</strong> de 1 mês, empilhado por desfecho.
        A altura total ≈ volume agendado; a composição mostra qualidade.
      </div>
      <ul className="space-y-1 text-neutral-100">
        <li><span className="text-emerald-300 font-bold">Atendidas</span> — paciente compareceu (CHECKOUT)</li>
        <li><span className="text-rose-300 font-bold">Faltas</span> — paciente não compareceu (MISSED, absenteísmo)</li>
        <li><span className="text-orange-300 font-bold">Canceladas</span> — agendamento removido (qualquer motivo)</li>
        <li><span className="text-neutral-300 font-bold">Sem status</span> — recepção não atualizou o desfecho</li>
      </ul>
      <div className="text-[10px] text-neutral-400 leading-snug pt-1 border-t border-neutral-700">
        Use pra detectar tendências: faltas crescendo, melhora na disciplina de status, sazonalidade no volume.
      </div>
    </div>
  )
}

function EvolutionChart({ data }: { data: AnaliseComercialResponse['evolution'] }) {
  // Toggle de séries via clique na legenda — útil pra isolar uma categoria
  // (ex: ver só faltas ao longo dos 12m, sem o ruído visual das atendidas).
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const toggle = (key: string) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const formatted = data.map((p) => ({
    label: p.label,
    Atendidas:    p.efetivas,
    Faltas:       p.faltas,
    Canceladas:   p.canceladas,
    'Sem status': p.indefinidas,
  }))

  // Última barra visível na pilha precisa ter radius arredondado.
  const order = ['Atendidas', 'Faltas', 'Canceladas', 'Sem status']
  const visible = order.filter((k) => !hidden.has(k))
  const topKey = visible[visible.length - 1]

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Evolução da agenda — 12 meses
        </span>
        <span className="relative group/tip shrink-0 ml-auto">
          <HelpCircle
            size={13}
            className="text-neutral-400 hover:text-neutral-600 cursor-help"
            aria-label="Como ler o gráfico"
          />
          <div className="hidden group-hover/tip:block absolute z-20 right-0 top-full mt-1 w-72 bg-neutral-900 text-white text-[11px] leading-snug rounded-lg shadow-xl p-3 normal-case tracking-normal font-normal">
            <EvolutionTooltip />
          </div>
        </span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={formatted} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} />
          <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
          <Tooltip
            formatter={(v) => fmtNum(typeof v === 'number' ? v : Number(v))}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Legend
            wrapperStyle={{ fontSize: 11, cursor: 'pointer' }}
            onClick={(e) => toggle(String(e.dataKey ?? e.value))}
            formatter={(value) => (
              <span style={{ opacity: hidden.has(String(value)) ? 0.4 : 1 }}>{value}</span>
            )}
          />
          <Bar dataKey="Atendidas"   stackId="agenda" fill={EVOLUTION_COLORS.efetivas.fill}    hide={hidden.has('Atendidas')}    radius={topKey === 'Atendidas'   ? [3, 3, 0, 0] : undefined} />
          <Bar dataKey="Faltas"      stackId="agenda" fill={EVOLUTION_COLORS.faltas.fill}      hide={hidden.has('Faltas')}       radius={topKey === 'Faltas'      ? [3, 3, 0, 0] : undefined} />
          <Bar dataKey="Canceladas"  stackId="agenda" fill={EVOLUTION_COLORS.canceladas.fill}  hide={hidden.has('Canceladas')}   radius={topKey === 'Canceladas'  ? [3, 3, 0, 0] : undefined} />
          <Bar dataKey="Sem status"  stackId="agenda" fill={EVOLUTION_COLORS.indefinidas.fill} hide={hidden.has('Sem status')}   radius={topKey === 'Sem status'  ? [3, 3, 0, 0] : undefined} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Top procedimentos ─────────────────────────────────────────

function TopProcedimentosCard({
  data, consultasEfetivas,
}: { data: TopProcedimentoExecutado[]; consultasEfetivas: number }) {
  const max = Math.max(...data.map((p) => p.qtd_executados), 1)
  const totalProcs = data.reduce((s, p) => s + p.qtd_executados, 0)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <TrendingUp size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Procedimentos Executados
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">por volume</span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(totalProcs)} procedimentos em {fmtNum(consultasEfetivas)} consultas atendidas
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem procedimentos no período.</div>
      ) : (
        <ul className="space-y-2.5">
          {data.map((p, i) => (
            <li key={p.procedure_name + i}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                  i === 0 ? 'bg-amber-100 text-amber-700' :
                  i === 1 ? 'bg-neutral-100 text-neutral-600' :
                  i === 2 ? 'bg-orange-100 text-orange-700' :
                  'bg-neutral-50 text-neutral-500'
                }`}>{i + 1}</span>
                <span className="text-[12px] font-medium text-neutral-800 truncate flex-1" title={p.procedure_name}>
                  {p.procedure_name}
                </span>
                <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                  {fmtNum(p.qtd_executados)}
                </span>
              </div>
              <div className="ml-7 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${i === 0 ? 'bg-amber-500' : 'bg-primary-500'}`}
                    style={{ width: `${(p.qtd_executados / max) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 w-10 text-right">{p.pct_volume.toFixed(0)}%</span>
              </div>
              <div className="ml-7 mt-1 text-[10px] text-neutral-500 flex items-center gap-2 flex-wrap">
                <span>{fmtBRL(p.faturamento, true)}</span>
                <span className="text-neutral-400">·</span>
                <span>ticket {fmtBRL(p.ticket_medio, true)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Top especialidades ────────────────────────────────────────

function TopEspecialidadesCard({
  data, consultasEfetivas,
}: { data: TopEspecialidadeDemanda[]; consultasEfetivas: number }) {
  const max = Math.max(...data.map((e) => e.qtd_procedimentos), 1)
  const totalProcs = data.reduce((s, e) => s + e.qtd_procedimentos, 0)
  const palette = ['bg-emerald-500', 'bg-blue-500', 'bg-purple-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-indigo-500', 'bg-pink-500']
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Especialidades em Demanda
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(totalProcs)} procedimentos em {fmtNum(consultasEfetivas)} consultas atendidas
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem dados.</div>
      ) : (
        <ul className="space-y-2">
          {data.map((e, i) => (
            <li key={e.especialidade} className="flex items-center gap-3">
              <span className={`w-2 h-2 rounded-full ${palette[i % palette.length]}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <span className="text-[12px] font-medium text-neutral-700 truncate">{e.especialidade}</span>
                  <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                    {fmtNum(e.qtd_procedimentos)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div className={`h-full ${palette[i % palette.length]} opacity-80`} style={{ width: `${(e.qtd_procedimentos / max) * 100}%` }} />
                  </div>
                  <span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">{e.pct_volume.toFixed(0)}%</span>
                  <span className="text-[10px] text-neutral-500 tabular-nums w-14 text-right">{fmtBRL(e.faturamento, true)}</span>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Top profissionais por consultas ───────────────────────────

function TopProfsConsultasCard({
  data, absMediaClinica,
}: { data: TopProfissionalConsultas[]; absMediaClinica: number }) {
  const max = Math.max(...data.map((p) => p.qtd_consultas), 1)
  // Volume mínimo (efetivas + faltas) pra exibir absenteísmo — abaixo disso
  // o número fica ruidoso (1 falta em 2 atendimentos = 33%).
  const MIN_VOL_ABS = 10
  // Destacar quando profissional está acima da média da clínica + 2pp.
  const ALERT_ABOVE = absMediaClinica + 2
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <UserCheck size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Profissionais por Volume de Consultas
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">
          consultas atendidas · média da clínica {absMediaClinica.toFixed(1)}% abs.
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem consultas no período.</div>
      ) : (
        <ul className="space-y-2.5">
          {data.map((p, i) => {
            const volumeDesfecho = p.qtd_consultas + p.qtd_faltas
            const showAbs = volumeDesfecho >= MIN_VOL_ABS
            const absAlerta = showAbs && p.absenteismo_pct > ALERT_ABOVE
            return (
              <li key={p.professional_external_id}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                    i === 0 ? 'bg-amber-100 text-amber-700' :
                    i === 1 ? 'bg-neutral-100 text-neutral-600' :
                    i === 2 ? 'bg-orange-100 text-orange-700' :
                    'bg-neutral-50 text-neutral-500'
                  }`}>{i + 1}</span>
                  <span className="text-[12px] font-medium text-neutral-800 truncate flex-1" title={p.nome}>
                    {p.nome}
                  </span>
                  <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                    {fmtNum(p.qtd_consultas)}
                  </span>
                </div>
                <div className="ml-7 flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${i === 0 ? 'bg-amber-500' : 'bg-blue-500'}`}
                      style={{ width: `${(p.qtd_consultas / max) * 100}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-neutral-500 w-10 text-right">{p.pct_volume.toFixed(0)}%</span>
                </div>
                <div className="ml-7 mt-1 text-[10px] text-neutral-500 flex items-center gap-2 flex-wrap">
                  <span>{p.pacientes_distintos} pacientes</span>
                  <span className="text-neutral-400">·</span>
                  <span>{p.qtd_faltas} faltas</span>
                  <span className="text-neutral-400">·</span>
                  <span>{p.qtd_canceladas} cancel</span>
                  {showAbs && (
                    <>
                      <span className="text-neutral-400">·</span>
                      <span
                        className={absAlerta ? 'text-rose-600 font-semibold' : ''}
                        title={absAlerta ? `Acima da média (${absMediaClinica.toFixed(1)}% + 2pp)` : undefined}
                      >
                        {p.absenteismo_pct.toFixed(1)}% abs.
                        {absAlerta && ' ⚠'}
                      </span>
                    </>
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ── Mix categorias ────────────────────────────────────────────

// ── Mix Categorias — taxonomia semântica ──────────────────────
//
// Backend retorna a chave canônica do `category_group` (heurística no builder
// de fato_agenda). Aqui mapeamos pra label/cor/descrição estável: se ortodontia
// trocar de cor amanhã, o gráfico inteiro vira inconsistente histórica.

const CATEGORIA_GROUP_META: Record<string, {
  label: string; color: string; bar: string; descricao: string
}> = {
  manutencao:   { label: 'Manutenção',    color: 'text-emerald-700', bar: 'bg-emerald-500', descricao: 'Manutenção, ajuste, limpeza, revisão — pacientes em acompanhamento periódico' },
  procedimento: { label: 'Procedimentos', color: 'text-blue-700',    bar: 'bg-blue-500',    descricao: 'Cirurgia, restauração, endodontia, implante, exodontia — execução de tratamentos vendidos' },
  retorno:      { label: 'Retorno',       color: 'text-cyan-700',    bar: 'bg-cyan-500',    descricao: 'Retornos e periódicos — controle pós-tratamento' },
  reabilitacao: { label: 'Reabilitação',  color: 'text-purple-700',  bar: 'bg-purple-500',  descricao: 'Lentes, coroa, mockup, scanner, prótese, protocolo — etapas de reabilitação estética/funcional' },
  consulta:     { label: 'Consulta inicial', color: 'text-amber-700', bar: 'bg-amber-500', descricao: 'Consulta, exame, orçamento — porta de entrada do funil comercial' },
  ortodontia:   { label: 'Ortodontia',    color: 'text-pink-700',    bar: 'bg-pink-500',    descricao: 'Aparelho, contenção, invisalign — tratamentos ortodônticos em curso' },
  bloqueio:     { label: 'Bloqueio',      color: 'text-neutral-600', bar: 'bg-neutral-400', descricao: 'Não agendar, pendências — tempo bloqueado na agenda' },
  outro:        { label: 'Outros',        color: 'text-neutral-600', bar: 'bg-neutral-400', descricao: 'Categorias não classificadas pela heurística' },
}

function MixCategoriasTooltip() {
  return (
    <div className="space-y-2">
      <div className="font-semibold text-[11.5px]">Como ler o mix</div>
      <div className="text-neutral-300 leading-snug">
        Agrupamos as ~80 categorias do Clinicorp em <strong>buckets semânticos</strong> pra dar leitura estratégica
        (catálogo cru tem nomes inconsistentes — CONSULTA vs Consulta, várias variações).
      </div>
      <ul className="space-y-1.5 text-neutral-100">
        {Object.entries(CATEGORIA_GROUP_META).filter(([k]) => k !== 'bloqueio').map(([k, m]) => (
          <li key={k} className="flex gap-2">
            <span className={`w-2 h-2 rounded-full ${m.bar} mt-1.5 shrink-0`} />
            <div>
              <span className="font-bold">{m.label}</span>
              <div className="text-neutral-400 text-[10px] leading-snug">{m.descricao}</div>
            </div>
          </li>
        ))}
      </ul>
      <div className="text-[10px] text-neutral-400 leading-snug pt-1 border-t border-neutral-700">
        Insight estratégico: <strong>Manutenção + Retorno + Reabilitação</strong> = continuação de tratamento
        (pacientes que já fecharam). <strong>Consulta inicial</strong> é a porta de entrada do funil.
      </div>
    </div>
  )
}

function MixCategoriasCard({ data }: { data: MixCategoriaConsulta[] }) {
  const fallback = { label: 'Outros', color: 'text-neutral-600', bar: 'bg-neutral-400', descricao: '' }
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Mix da agenda — por tipo de atendimento
        </span>
        <span className="relative group/tip shrink-0 ml-auto">
          <HelpCircle
            size={13}
            className="text-neutral-400 hover:text-neutral-600 cursor-help"
            aria-label="O que cada grupo significa"
          />
          <div className="hidden group-hover/tip:block absolute z-20 right-0 top-full mt-1 w-80 bg-neutral-900 text-white text-[11px] leading-snug rounded-lg shadow-xl p-3 normal-case tracking-normal font-normal">
            <MixCategoriasTooltip />
          </div>
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem consultas no período.</div>
      ) : (
        <ul className="space-y-2.5">
          {data.map((m) => {
            const meta = CATEGORIA_GROUP_META[m.categoria] ?? fallback
            return (
              <li key={m.categoria} className="flex items-center gap-3">
                <span className={`w-2 h-6 rounded-sm ${meta.bar} shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2 mb-1">
                    <span className={`text-[12px] font-semibold ${meta.color} truncate`}>{meta.label}</span>
                    <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtNum(m.qtd)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                      <div className={`h-full ${meta.bar} opacity-80`} style={{ width: `${m.pct}%` }} />
                    </div>
                    <span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">{m.pct.toFixed(1)}%</span>
                    {m.mom_pct !== null && Math.abs(m.mom_pct) >= 5 && (
                      <span className={`text-[10px] font-semibold tabular-nums w-12 text-right ${m.mom_pct > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {fmtPct(m.mom_pct)}
                      </span>
                    )}
                  </div>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ── Operacional — 3 blocos: problema / oportunidade / ações ───
//
// Reformulado em 2026-05-09. Card antigo mostrava 4 números soltos com
// "R$ potencial perdido" calculado por ticket médio (artificial). Agora:
//
//  Bloco 1 — Tempo perdido: horas das faltas+canceladas (palpável, não inflado).
//  Bloco 2 — Aproveitamento de slots ociosos: % de encaixes sobre slots perdidos.
//  Bloco 3 — Ações pendentes: contadores das tags do Clinicorp.

function OperacionalCard({ data }: { data: OperacionalComercial }) {
  const taxaAprov = data.taxa_aproveitamento_pct
  const taxaCor =
    taxaAprov >= 30 ? 'text-emerald-700'
      : taxaAprov >= 10 ? 'text-amber-700'
        : 'text-rose-700'

  const acoes = [
    { label: 'Para remarcar',    qtd: data.remarcar_qty,         hint: 'cancelados sem nova data' },
    { label: 'Retorno pendente', qtd: data.retorno_pendente_qty, hint: 'follow-up esperado'        },
    { label: 'Em waitlist',      qtd: data.waitlist_qty,         hint: 'esperando vaga'           },
  ]

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Operacional — problema, oportunidade, ações
        </span>
      </div>

      <div className="space-y-3">
        {/* Bloco 1 — Tempo perdido */}
        <div className="rounded-lg border border-rose-200 bg-rose-50/50 p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase tracking-wider font-bold text-rose-700">
              Tempo perdido na agenda
            </span>
            <span className="text-[10px] text-rose-600/70">problema</span>
          </div>
          <div className="flex items-baseline gap-2 mb-0.5">
            <span className="text-xl font-bold text-rose-900 tabular-nums">
              {data.horas_perdidas.toFixed(1)}h
            </span>
            <span className="text-[11px] text-rose-700">
              ≈ {data.dias_equivalentes_8h.toFixed(1)} dias de 8h de 1 profissional
            </span>
          </div>
          <div className="text-[10px] text-rose-700/80">
            {data.faltas_qty} faltas · {data.cancelados_qty} canceladas
          </div>
        </div>

        {/* Bloco 2 — Aproveitamento de slots ociosos */}
        <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase tracking-wider font-bold text-amber-700">
              Aproveitamento de slots ociosos
            </span>
            <span className="text-[10px] text-amber-600/70">oportunidade</span>
          </div>
          <div className="flex items-baseline gap-2 mb-0.5">
            <span className={`text-xl font-bold tabular-nums ${taxaCor}`}>
              {taxaAprov.toFixed(1)}%
            </span>
            <span className="text-[11px] text-amber-700">
              {fmtNum(data.slots_recuperados_encaixe)} de {fmtNum(data.slots_perdidos)} slots vagos viraram encaixe
            </span>
          </div>
          <div className="text-[10px] text-amber-700/80">
            {data.slots_perdidos - data.slots_recuperados_encaixe} slots ainda ociosos — campanhas de waitlist/encaixe podem recuperar parte
          </div>
        </div>

        {/* Bloco 3 — Ações pendentes */}
        <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase tracking-wider font-bold text-blue-700">
              Ações pendentes
            </span>
            <span className="text-[10px] text-blue-600/70">tarefas operacionais</span>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {acoes.map((a) => (
              <div key={a.label}>
                <div className="text-lg font-bold tabular-nums text-blue-900">
                  {fmtNum(a.qtd)}
                </div>
                <div className="text-[10.5px] font-semibold text-blue-800 leading-tight">
                  {a.label}
                </div>
                <div className="text-[10px] text-blue-700/70 leading-tight">
                  {a.hint}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
