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
import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  Activity, BarChart3, BrainCircuit, Briefcase, CalendarClock,
  CheckCircle2, FileText, HelpCircle, Loader2, Sparkles, Target, TrendingUp, UserCheck, Users, XCircle,
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

      <AIInsightsSection year={data.period.year} month={data.period.month} />

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
        <TopProcedimentosCard data={data.top_procedimentos} />
        <TopEspecialidadesCard data={data.top_especialidades} />
      </div>

      {/* Top profissionais (linha cheia) */}
      <TopProfsConsultasCard data={data.top_profissionais} />

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

// ── Insights via IA ───────────────────────────────────────────

function AIInsightsSection({ year, month }: { year: number; month: number }) {
  const mutation = useMutation({
    mutationFn: () => analiseService.comercialAIInsights(year, month),
  })

  const key = `${year}-${month}`
  const [lastKey, setLastKey] = useState(key)
  if (lastKey !== key) {
    setLastKey(key)
    mutation.reset()
  }

  const lines = mutation.data?.narrative
    ? mutation.data.narrative
        .split('\n')
        .map((l) => l.trim())
        .filter((l) => l.length > 0)
    : []

  return (
    <div className="bg-gradient-to-br from-violet-50/70 to-fuchsia-50/40 border border-violet-200 rounded-xl p-4">
      <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
        <div className="flex items-center gap-2">
          <BrainCircuit size={14} className="text-violet-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-violet-800">
            Insights estratégicos com IA
          </span>
          {mutation.data && (
            <span className="text-[10px] text-violet-500 font-mono">
              · {mutation.data.model}
            </span>
          )}
        </div>
        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-700 disabled:bg-violet-300 text-white text-[12px] font-semibold transition-colors"
        >
          {mutation.isPending ? (
            <>
              <Loader2 size={12} className="animate-spin" /> Gerando...
            </>
          ) : (
            <>
              <Sparkles size={12} /> {mutation.data ? 'Regenerar' : 'Gerar com IA'}
            </>
          )}
        </button>
      </div>

      {!mutation.data && !mutation.isPending && !mutation.isError && (
        <div className="text-[12px] text-violet-700/80 leading-relaxed">
          Clique em <span className="font-semibold">Gerar com IA</span> para análise cruzada
          das dimensões comerciais (consultas, conversão, procedimentos, profissionais).
        </div>
      )}

      {mutation.isError && (
        <div className="text-[12px] text-rose-700 bg-rose-50 border border-rose-200 rounded-md px-3 py-2">
          Falha ao gerar insights:{' '}
          {(mutation.error as { response?: { data?: { detail?: string } }; message?: string })
            ?.response?.data?.detail ||
            (mutation.error as Error)?.message ||
            'erro desconhecido'}
        </div>
      )}

      {lines.length > 0 && (
        <ul className="space-y-1.5 text-[13px] text-neutral-800 leading-relaxed">
          {lines.map((line, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500 mt-2 shrink-0" />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      )}
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

function TopProcedimentosCard({ data }: { data: TopProcedimentoExecutado[] }) {
  const max = Math.max(...data.map((p) => p.qtd_executados), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Procedimentos Executados
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">por volume</span>
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

function TopEspecialidadesCard({ data }: { data: TopEspecialidadeDemanda[] }) {
  const max = Math.max(...data.map((e) => e.qtd_procedimentos), 1)
  const palette = ['bg-emerald-500', 'bg-blue-500', 'bg-purple-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-indigo-500', 'bg-pink-500']
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Especialidades em Demanda
        </span>
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

function TopProfsConsultasCard({ data }: { data: TopProfissionalConsultas[] }) {
  const max = Math.max(...data.map((p) => p.qtd_consultas), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <UserCheck size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Profissionais por Volume de Consultas
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">consultas executadas</span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem consultas no período.</div>
      ) : (
        <ul className="space-y-2.5">
          {data.map((p, i) => (
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
                <span>{p.qtd_canceladas} canc</span>
                <span className="text-neutral-400">·</span>
                <span className={p.absenteismo_pct >= 15 ? 'text-rose-600 font-semibold' : ''}>
                  {p.absenteismo_pct.toFixed(1)}% absent.
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Mix categorias ────────────────────────────────────────────

function MixCategoriasCard({ data }: { data: MixCategoriaConsulta[] }) {
  const palette = ['bg-blue-500', 'bg-emerald-500', 'bg-purple-500', 'bg-amber-500', 'bg-rose-500', 'bg-cyan-500', 'bg-indigo-500', 'bg-pink-500']
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Mix de Categorias de Consulta
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem consultas no período.</div>
      ) : (
        <ul className="space-y-2">
          {data.map((m, i) => (
            <li key={m.categoria} className="flex items-center gap-3">
              <span className={`w-2 h-2 rounded-full ${palette[i % palette.length]}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-baseline justify-between gap-2 mb-1">
                  <span className="text-[12px] font-medium text-neutral-700 truncate">{m.categoria}</span>
                  <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                    {fmtNum(m.qtd)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div className={`h-full ${palette[i % palette.length]} opacity-80`} style={{ width: `${m.pct}%` }} />
                  </div>
                  <span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">{m.pct.toFixed(0)}%</span>
                  {m.canceladas > 0 && (
                    <span className={`text-[10px] tabular-nums w-12 text-right ${m.absenteismo_pct >= 15 ? 'text-rose-600 font-semibold' : 'text-neutral-500'}`}>
                      {m.absenteismo_pct.toFixed(0)}% canc
                    </span>
                  )}
                  {m.mom_pct !== null && Math.abs(m.mom_pct) >= 5 && (
                    <span className={`text-[10px] font-semibold tabular-nums ${m.mom_pct > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {fmtPct(m.mom_pct)}
                    </span>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Operacional ───────────────────────────────────────────────

function OperacionalCard({ data }: { data: OperacionalComercial }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Activity size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Operacional
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Stat
          label="Encaixes"
          value={fmtNum(data.encaixe_qty)}
          hint={`${data.encaixe_pct.toFixed(1)}% das consultas`}
        />
        <Stat
          label="Retorno pendente"
          value={fmtNum(data.retorno_pendente_qty)}
          hint="follow-up esperado"
        />
        <Stat
          label="Para remarcar"
          value={fmtNum(data.remarcar_qty)}
          hint="ação direta"
        />
        <Stat
          label="Cancelados"
          value={fmtNum(data.cancelados_qty)}
          hint={`${fmtBRL(data.cancelados_amount_estimado, true)} potencial perdido`}
          danger
        />
      </div>
    </div>
  )
}

function Stat({
  label, value, hint, danger,
}: {
  label: string; value: string; hint?: string; danger?: boolean
}) {
  return (
    <div className={`rounded-lg border px-3 py-2.5 ${
      danger ? 'bg-rose-50 border-rose-200' : 'bg-neutral-50 border-neutral-200'
    }`}>
      <div className={`text-[10px] uppercase tracking-wider font-bold ${
        danger ? 'text-rose-700' : 'text-neutral-500'
      }`}>
        {label}
      </div>
      <div className={`text-lg font-bold tabular-nums mt-0.5 ${
        danger ? 'text-rose-900' : 'text-neutral-900'
      }`}>
        {value}
      </div>
      {hint && <div className="text-[10px] text-neutral-500">{hint}</div>}
    </div>
  )
}
