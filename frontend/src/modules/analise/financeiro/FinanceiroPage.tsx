/**
 * Dashboard financeiro segmentado (Sub-PR 20b).
 * Foco: relatório estratégico-tático para o DONO da clínica.
 *
 * Estrutura:
 * 1. Header com seletor de mês
 * 2. Insights estratégicos (3-6 frases narrativas)
 * 3. KPIs principais (5 cards com MoM/YoY/sparkline/insight)
 * 4. Evolution chart (12 meses faturamento + recebido)
 * 5. Funil orçamentos + Mix de pagamento
 * 6. Top profissionais + Top categorias
 * 7. Saúde de recebíveis
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3, CalendarClock, ChevronDown, ChevronRight, Clock, DollarSign,
  FileText, HandCoins, Loader2, Scissors, Search, Target, TrendingUp, Zap,
} from 'lucide-react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid,
} from 'recharts'

import { usePageTitle } from '@/contexts/PageTitleContext'
import { analiseService } from '@/services/analise.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageFooter } from '@/components/layout/PageFooter'
import type {
  AnaliseFinanceiroResponse, DescontosSection, FunilOrcamentos,
  PrazoRecebimentoSection, TopCategoriaFaturamento, TopMedicoFaturamento, TopProfFaturamento,
} from '@/types/analise'

import { KpiCardEnriched } from '../components/KpiCardEnriched'
import { PeriodSelector } from '../components/PeriodSelector'
import { useSonIA, type SonIAInsight } from '@/components/sonia/SonIAContext'
import { CustoAdquirenciaCard } from './CustoAdquirenciaCard'
import PrazoAuditModal from './PrazoAuditModal'

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

// ── Página ────────────────────────────────────────────────────

export default function FinanceiroPage() {
  usePageTitle(
    'Análise Financeira',
    'Faturamento, conversão, recebimentos e saúde de recebíveis',
    'ANÁLISE',
  )

  // Default: mês atual
  const today = new Date()
  const [period, setPeriod] = useState<{ year: number; month: number }>({
    year: today.getFullYear(),
    month: today.getMonth() + 1,
  })

  const q = useQuery({
    queryKey: ['analise', 'financeiro', period.year, period.month],
    queryFn: () => analiseService.financeiro(period.year, period.month),
    staleTime: 5 * 60_000,  // 5min
  })

  const { publish, clear } = useSonIA()
  useEffect(() => {
    if (!q.data) return
    publish({
      pageKey: '/analise/financeiro',
      pageTitle: 'Análise Financeira',
      data: { insight: buildAnaliseFinanceiroInsight(q.data) },
    })
    return () => clear('/analise/financeiro')
  }, [q.data, publish, clear])

  return (
    <PageContainer>
      <PageHeader
        eyebrow="ANÁLISE"
        title="Dashboard Financeiro"
        subtitle="Visão estratégica do faturamento"
        icon={<DollarSign size={20} />}
        filters={
          <PeriodSelector
            year={period.year}
            month={period.month}
            onChange={(y, m) => setPeriod({ year: y, month: m })}
          />
        }
      />

      {q.isLoading && (
        <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm flex items-center justify-center gap-2">
          <Loader2 size={16} className="animate-spin" />
          Carregando análise…
        </div>
      )}

      {q.isError && (
        <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
          Erro ao carregar dashboard. Tente atualizar a página.
        </div>
      )}

      {q.data && <Body data={q.data} />}

      <PageFooter dataSource="Clinicorp + Conta Azul" />
    </PageContainer>
  )
}

// ── Body ──────────────────────────────────────────────────────

function Body({ data }: { data: AnaliseFinanceiroResponse }) {
  const fat = data.kpis.faturamento
  return (
    <>
      {/* Aviso único de mês em andamento (parcial) */}
      {fat.is_partial && fat.partial_days && fat.partial_days_in_month && (
        <PartialMonthBanner
          days={fat.partial_days}
          daysInMonth={fat.partial_days_in_month}
          progress={fat.partial_progress ?? 0}
        />
      )}

      {/* KPIs principais — 4 cards (Inadimplência foi pra Fluxo de Caixa) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCardEnriched
          data={data.kpis.faturamento}
          label="Faturamento"
          icon={<DollarSign size={14} className="text-emerald-700" />}
          iconBg="bg-emerald-50"
          emphasized
        />
        <KpiCardEnriched
          data={data.kpis.conversao}
          label="Conversão"
          icon={<Target size={14} className="text-blue-700" />}
          iconBg="bg-blue-50"
        />
        <KpiCardEnriched
          data={data.kpis.ticket_medio}
          label="Ticket Médio"
          icon={<TrendingUp size={14} className="text-purple-700" />}
          iconBg="bg-purple-50"
        />
        <KpiCardEnriched
          data={data.kpis.recebido}
          label="Recebido (Caixa)"
          icon={<DollarSign size={14} className="text-cyan-700" />}
          iconBg="bg-cyan-50"
          footer={
            <div className="flex items-center justify-between gap-2 tabular-nums">
              <div>
                <div className="text-neutral-500">Bruto</div>
                <div className="font-semibold text-neutral-700">
                  {fmtBRL(data.kpis.recebido_breakdown.bruto, true)}
                </div>
              </div>
              <div className="text-right">
                <div className="text-neutral-500">Taxas</div>
                <div className="font-semibold text-rose-600">
                  −{fmtBRL(data.kpis.recebido_breakdown.taxas, true)}
                  <span className="text-[10px] text-neutral-400 ml-1">
                    ({data.kpis.recebido_breakdown.taxas_pct.toFixed(1)}%)
                  </span>
                </div>
              </div>
            </div>
          }
        />
      </div>

      {/* Evolution chart */}
      <EvolutionChart data={data.evolution} />

      {/* Descontos */}
      <DescontosCard data={data.descontos} />

      {/* Prazo de recebimento (orçamentos aprovados) */}
      <PrazoRecebimentoCard
        data={data.prazos}
        year={data.period.year}
        month={data.period.month}
      />

      {/* Custo de adquirência (taxas de maquininha por forma de pagamento) */}
      <CustoAdquirenciaCard data={data.taxas} />

      {/* Funil de orçamentos */}
      <FunilCard data={data.funil} />

      {/* Top médicos + Top atendentes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TopMedicosCard data={data.top_medicos} />
        <TopAtendentesCard data={data.top_profissionais} />
      </div>

      {/* Top categorias */}
      <TopCategoriasCard data={data.top_categorias} />
    </>
  )
}

// ── Insight pra SonIA ─────────────────────────────────────────

function buildAnaliseFinanceiroInsight(data: AnaliseFinanceiroResponse): SonIAInsight {
  const fat = data.kpis.faturamento
  const conv = data.kpis.conversao
  const tk = data.kpis.ticket_medio
  const rec = data.kpis.recebido

  // Mês em andamento: comparar parcial com mês fechado distorce TUDO.
  // Backend já marca is_partial e fornece projeção — usamos isso.
  if (fat.is_partial) {
    const days = fat.partial_days ?? 0
    const total = fat.partial_days_in_month ?? 30
    const pctMes = total > 0 ? Math.round((days / total) * 100) : 0
    const proj = fat.projected_label

    return {
      mood: 'curious',
      headline: `Olhei o que temos de ${data.period.label} até agora.`,
      detail: `Estamos no dia ${days} de ${total} (${pctMes}% do mês). Por enquanto o faturamento parcial é ${fat.value_label}${proj ? `, com projeção de ${proj} no ritmo atual` : ''}. Vou esperar o mês fechar pra trazer comparações com confiança.`,
      bullets: [
        { text: `Faturamento parcial ${fat.value_label}${proj ? ` · projeção ${proj}` : ''}.`, tone: 'neutral' },
        { text: `Conversão ${conv.value_label} (sobre o que já foi atendido).`, tone: 'neutral' },
        { text: `Ticket médio ${tk.value_label}.`, tone: 'neutral' },
        { text: `Recebido (caixa) ${rec.value_label}.`, tone: 'neutral' },
      ],
    }
  }

  const momPct = fat.mom_pct
  const positivaSubida = momPct !== null && momPct >= 5
  const queda = momPct !== null && momPct <= -5

  const mood = queda ? 'alert' : positivaSubida ? 'happy' : 'curious'
  const headline = queda
    ? 'Dei uma olhadinha e queria te contar.'
    : positivaSubida
    ? 'Olha que notícia boa.'
    : 'Olhei a página com calma.'

  const detail = queda
    ? `O faturamento de ${data.period.label} ficou em ${fat.value_label}, ${momPct!.toFixed(1)}% abaixo do mês anterior. Vale a pena olhar com mais carinho.`
    : positivaSubida
    ? `O faturamento de ${data.period.label} foi ${fat.value_label}, com alta de ${momPct!.toFixed(1)}% sobre o mês anterior. A equipe está em ritmo bonito.`
    : `O faturamento de ${data.period.label} está em ${fat.value_label}. Trouxe aqui um resumo do que observei.`

  const bullets = [
    { text: `Faturamento ${fat.value_label}${momLabel(fat.mom_pct)}.`, tone: tonePct(fat.mom_pct, fat.is_inverse) },
    { text: `Conversão ${conv.value_label}${momLabel(conv.mom_pct)}.`, tone: tonePct(conv.mom_pct, conv.is_inverse) },
    { text: `Ticket médio ${tk.value_label}${momLabel(tk.mom_pct)}.`, tone: tonePct(tk.mom_pct, tk.is_inverse) },
    { text: `Recebido (caixa) ${rec.value_label}${momLabel(rec.mom_pct)}.`, tone: tonePct(rec.mom_pct, rec.is_inverse) },
  ] as SonIAInsight['bullets']

  return { mood, headline, detail, bullets }
}

function momLabel(p: number | null): string {
  if (p === null) return ''
  const sign = p > 0 ? '+' : ''
  return ` (${sign}${p.toFixed(1)}% vs mês passado)`
}

function tonePct(p: number | null, inverse: boolean): 'positive' | 'negative' | 'neutral' | 'warning' {
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
        Comparativos e médias usam projeção do ritmo atual.
      </span>
    </div>
  )
}

// ── Evolution chart ───────────────────────────────────────────

function EvolutionChart({ data }: { data: AnaliseFinanceiroResponse['evolution'] }) {
  const formatted = data.map((p) => ({
    label: p.label,
    Faturamento: p.faturamento,
    Recebido: p.recebido,
  }))
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Evolução 12 meses
        </span>
        <span className="text-[11px] text-neutral-400 ml-2">
          Faturamento (orçamentos aprovados) vs Recebido (caixa)
        </span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={formatted} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#a3a3a3" />
          <YAxis
            tick={{ fontSize: 11 }}
            stroke="#a3a3a3"
            tickFormatter={(v) => `R$ ${(v / 1000).toFixed(0)}k`}
          />
          <Tooltip
            formatter={(v) => fmtBRL(typeof v === 'number' ? v : Number(v))}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone" dataKey="Faturamento"
            stroke="#10b981" strokeWidth={2.5}
            dot={{ r: 3 }} activeDot={{ r: 5 }}
          />
          <Line
            type="monotone" dataKey="Recebido"
            stroke="#06b6d4" strokeWidth={2.5}
            dot={{ r: 3 }} activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Descontos ─────────────────────────────────────────────────

function DescontosCard({ data }: { data: DescontosSection }) {
  const [open, setOpen] = useState(false)

  // Variação MoM/YoY em pontos percentuais (rosa = aumentou desconto = perda maior)
  const fmtPP = (pp: number | null | undefined): { txt: string; cls: string } | null => {
    if (pp === null || pp === undefined) return null
    const sign = pp > 0 ? '+' : ''
    const cls = pp > 0.1 ? 'text-rose-600' : pp < -0.1 ? 'text-emerald-600' : 'text-neutral-500'
    return { txt: `${sign}${pp.toFixed(1)}pp`, cls }
  }
  const mom = fmtPP(data.mom_total_pct)
  const yoy = fmtPP(data.yoy_total_pct)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-4 flex items-start justify-between gap-4 flex-wrap border-b border-neutral-100">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-rose-50 flex items-center justify-center text-rose-600 ring-1 ring-rose-100 shrink-0">
            <HandCoins size={18} />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
              Desconto efetivo concedido
            </div>
            <div className="text-sm text-neutral-700 mt-0.5">
              {data.qtd_orcamentos_aprovados} orçamentos · {data.qtd_procs_aprovados} procedimentos efetivamente aprovados
            </div>
          </div>
        </div>
        <div className="flex items-baseline gap-3 shrink-0">
          <div className="text-right">
            <div className="text-2xl font-bold text-rose-600 tabular-nums">
              {fmtBRL(data.desconto_total, true)}
            </div>
            <div className="text-xs text-neutral-500 tabular-nums">
              {data.desconto_total_pct.toFixed(1)}% do preço de tabela
            </div>
          </div>
          {(mom || yoy) && (
            <div className="text-[11px] tabular-nums">
              {mom && <div className={mom.cls}>MoM {mom.txt}</div>}
              {yoy && <div className={yoy.cls}>YoY {yoy.txt}</div>}
            </div>
          )}
        </div>
      </header>

      {/* Barra empilhada: faturamento + desconto = preço de tabela */}
      <div className="px-5 py-3">
        <div className="text-[10px] uppercase tracking-wider text-neutral-500 font-semibold mb-1.5 flex items-center justify-between">
          <span>Composição do preço de tabela (procedimentos aprovados)</span>
          <span className="tabular-nums text-neutral-400">{fmtBRL(data.original_amount_tabela, true)}</span>
        </div>
        <div className="flex h-7 rounded-md overflow-hidden ring-1 ring-neutral-200">
          <div
            className="bg-emerald-500 flex items-center justify-center text-[11px] font-bold text-white"
            style={{ width: `${Math.max(100 - data.desconto_total_pct, 5)}%`, minWidth: 60 }}
            title={`Faturamento: ${fmtBRL(data.faturamento)}`}
          >
            Faturamento {(100 - data.desconto_total_pct).toFixed(1)}%
          </div>
          <div
            className="bg-rose-400 flex items-center justify-center text-[11px] font-bold text-white"
            style={{ width: `${Math.max(data.desconto_total_pct, 5)}%`, minWidth: 40 }}
            title={`Desconto: ${fmtBRL(data.desconto_total)}`}
          >
            {data.desconto_total_pct.toFixed(1)}%
          </div>
        </div>
        <div className="flex justify-between text-[11px] text-neutral-600 mt-1.5 tabular-nums">
          <span>Faturado: <strong className="text-emerald-700">{fmtBRL(data.faturamento)}</strong></span>
          <span>Desconto: <strong className="text-rose-700">{fmtBRL(data.desconto_total)}</strong></span>
        </div>
      </div>

      {/* Info paralela: escopo recusado pelo paciente (NÃO É DESCONTO) */}
      {data.escopo_nao_aprovado > 0 && (
        <div className="px-5 py-3 bg-amber-50/60 border-t border-amber-100">
          <div className="flex items-start gap-2.5">
            <Scissors size={14} className="text-amber-700 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-[12px] font-semibold text-amber-900">
                Escopo recusado pelo paciente <span className="font-normal text-amber-700">— não conta como desconto</span>
              </div>
              <div className="text-[10.5px] text-amber-700/90 leading-snug mt-0.5">
                Procedimentos sugeridos no plano de tratamento mas que o paciente optou por não fazer agora.
                Oportunidade de resgate.
              </div>
            </div>
            <div className="text-right shrink-0 tabular-nums">
              <div className="text-[14px] font-bold text-amber-800">{fmtBRL(data.escopo_nao_aprovado, true)}</div>
              <div className="text-[10px] text-amber-700/70">não aprovado</div>
            </div>
          </div>
        </div>
      )}

      {/* Drill-down dos descontos */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-5 py-2 border-t border-neutral-100 text-left text-[12px] text-neutral-600 hover:bg-neutral-50 flex items-center gap-1.5 transition"
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="font-medium">Detalhar componentes do desconto</span>
      </button>

      {open && (
        <div className="px-5 py-3 bg-neutral-50/60 border-t border-neutral-100 space-y-2.5">
          <DescBreakdownRow
            label="Por procedimento"
            hint="Profissional/recepção ajustou preço (R$ X → R$ Y) diretamente na linha do procedimento aprovado."
            value={data.desconto_procedimento}
            pct={data.desconto_procedimento_pct}
          />
          <DescBreakdownRow
            label="Negociação no fechamento"
            hint="Desconto extra negociado no momento de fechar o orçamento (residual entre soma dos procedimentos aprovados e valor combinado)."
            value={data.desconto_negociacao}
            pct={data.desconto_negociacao_pct}
          />
        </div>
      )}
    </section>
  )
}

function DescBreakdownRow({
  label, hint, value, pct,
}: { label: string; hint: string; value: number; pct: number }) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-semibold text-neutral-800">{label}</div>
        <div className="text-[10.5px] text-neutral-500 leading-snug mt-0.5">{hint}</div>
      </div>
      <div className="text-right shrink-0 tabular-nums">
        <div className="text-[13px] font-bold text-rose-700">{fmtBRL(value, true)}</div>
        <div className="text-[10px] text-neutral-500">{pct.toFixed(1)}% do bruto</div>
      </div>
    </div>
  )
}

// ── Prazo de Recebimento ─────────────────────────────────────

function PrazoRecebimentoCard({
  data, year, month,
}: { data: PrazoRecebimentoSection; year: number; month: number }) {
  const [auditOpen, setAuditOpen] = useState<
    { min: number; max: number; label: string } | 'all' | null
  >(null)

  // Cores por bucket — degradê de verde (saudável) → âmbar → rose (risco)
  const BUCKET_COLOR: Record<string, { bar: string; bg: string; text: string; min: number; max: number }> = {
    '1x à vista':       { bar: 'bg-emerald-500', bg: 'bg-emerald-50',  text: 'text-emerald-700', min: 1,  max: 1   },
    '2-3x curto':       { bar: 'bg-lime-500',    bg: 'bg-lime-50',     text: 'text-lime-700',    min: 2,  max: 3   },
    '4-6x médio':       { bar: 'bg-amber-500',   bg: 'bg-amber-50',    text: 'text-amber-700',   min: 4,  max: 6   },
    '7-12x longo':      { bar: 'bg-orange-500',  bg: 'bg-orange-50',   text: 'text-orange-700',  min: 7,  max: 12  },
    '13+ muito longo':  { bar: 'bg-rose-500',    bg: 'bg-rose-50',     text: 'text-rose-700',    min: 13, max: 999 },
  }

  const fmtPP = (pp: number | null | undefined): { txt: string; cls: string } | null => {
    if (pp === null || pp === undefined) return null
    const sign = pp > 0 ? '+' : ''
    // Para "% à vista", subir = bom (verde), cair = ruim (rosa)
    const cls = pp > 0.5 ? 'text-emerald-600' : pp < -0.5 ? 'text-rose-600' : 'text-neutral-500'
    return { txt: `${sign}${pp.toFixed(1)}pp`, cls }
  }
  const mom = fmtPP(data.mom_a_vista_pct)
  const yoy = fmtPP(data.yoy_a_vista_pct)

  if (data.qtd_pagamentos_total === 0) {
    return (
      <section className="bg-white border border-neutral-200 rounded-xl shadow-sm p-5">
        <div className="text-sm text-neutral-500">Sem pagamentos vinculados a orçamentos aprovados neste mês.</div>
      </section>
    )
  }

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-4 flex items-start justify-between gap-4 flex-wrap border-b border-neutral-100">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600 ring-1 ring-emerald-100 shrink-0">
            <Clock size={18} />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
              Prazo de recebimento
            </div>
            <div className="text-sm text-neutral-700 mt-0.5">
              {data.qtd_pagamentos_total} pagamentos fechados · prazo médio {Math.round(data.prazo_medio_dias)} dias
            </div>
          </div>
        </div>
        <div className="flex items-baseline gap-3 shrink-0">
          <div className="text-right">
            <div className="text-2xl font-bold text-emerald-600 tabular-nums">
              {data.pct_a_vista_valor.toFixed(0)}%
            </div>
            <div className="text-xs text-neutral-500 tabular-nums">à vista (em valor)</div>
          </div>
          {(mom || yoy) && (
            <div className="text-[11px] tabular-nums">
              {mom && <div className={mom.cls}>MoM {mom.txt}</div>}
              {yoy && <div className={yoy.cls}>YoY {yoy.txt}</div>}
            </div>
          )}
          <button
            onClick={() => setAuditOpen('all')}
            className="ml-1 inline-flex items-center gap-1.5 text-[11px] font-semibold px-2.5 py-1.5 rounded-md bg-blue-50 text-blue-700 border border-blue-100 hover:bg-blue-100 transition"
            title="Auditar — listar todas as parcelas"
          >
            <Search size={13} />
            Auditar
          </button>
        </div>
      </header>

      {/* Cobertura do plano de pagamento — Clinicorp gera parcelas em partes,
          então valor_total < faturamento aprovado quando há orçamentos com
          plano parcial (só entrada lançada) ou ainda sem nenhuma parcela. */}
      <CoberturaPanel data={data} />

      {/* Barra empilhada — distribuição de valor por bucket */}
      <div className="px-5 py-3">
        <div className="text-[10px] uppercase tracking-wider text-neutral-500 font-semibold mb-1.5 flex items-center justify-between">
          <span>Distribuição das parcelas já lançadas, por nº de parcelas</span>
          <span className="tabular-nums text-neutral-400">{fmtBRL(data.valor_total, true)}</span>
        </div>
        <div className="flex h-7 rounded-md overflow-hidden ring-1 ring-neutral-200">
          {data.buckets.map((b) => {
            const c = BUCKET_COLOR[b.label] || { bar: 'bg-neutral-400', bg: '', text: '' }
            return (
              <div
                key={b.label}
                className={`${c.bar} flex items-center justify-center text-[10.5px] font-bold text-white transition`}
                style={{ width: `${Math.max(b.pct_valor, 3)}%` }}
                title={`${b.label}: ${fmtBRL(b.valor)} (${b.pct_valor.toFixed(1)}%)`}
              >
                {b.pct_valor >= 8 ? `${b.pct_valor.toFixed(0)}%` : ''}
              </div>
            )
          })}
        </div>
      </div>

      {/* Tabela detalhada por bucket */}
      <div className="px-5 pb-3 pt-1">
        <div className="grid grid-cols-1 gap-1.5">
          {data.buckets.map((b) => {
            const c = BUCKET_COLOR[b.label] || {
              bar: 'bg-neutral-400', bg: 'bg-neutral-50', text: 'text-neutral-600', min: 1, max: 999,
            }
            return (
              <div
                key={b.label}
                className={`${c.bg} rounded-md px-3 py-2 flex items-center gap-3 w-full`}
              >
                <div className={`w-2 h-8 rounded-sm ${c.bar} shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className={`text-[12px] font-semibold ${c.text}`}>{b.label}</div>
                  <div className="text-[10px] text-neutral-500">
                    {b.qtd_pagamentos} pagamentos · ticket médio {fmtBRL(b.ticket_medio, true)}
                  </div>
                </div>
                <div className="text-right shrink-0 tabular-nums">
                  <div className={`text-[13px] font-bold ${c.text}`}>{fmtBRL(b.valor, true)}</div>
                  <div className="text-[10px] text-neutral-500">{b.pct_valor.toFixed(1)}% do total</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Comparativo ticket: à vista vs parcelado */}
      {data.ticket_medio_a_vista > 0 && data.ticket_medio_parcelado > 0 && (
        <div className="px-5 py-3 border-t border-neutral-100 bg-neutral-50/40 flex items-center gap-4 text-[11px]">
          <Zap size={13} className="text-amber-500 shrink-0" />
          <span className="text-neutral-600">
            Ticket médio à vista <strong className="text-emerald-700 tabular-nums">{fmtBRL(data.ticket_medio_a_vista, true)}</strong>
            {' · '}
            parcelado <strong className="text-amber-700 tabular-nums">{fmtBRL(data.ticket_medio_parcelado, true)}</strong>
            {data.ticket_medio_a_vista > data.ticket_medio_parcelado
              ? <> — pacientes pagam tickets menores quando parcelam.</>
              : <> — pacientes parcelam quando o ticket é maior.</>}
          </span>
        </div>
      )}

      {auditOpen && (
        <PrazoAuditModal
          year={year}
          month={month}
          initialBucket={auditOpen === 'all' ? undefined : auditOpen}
          onClose={() => setAuditOpen(null)}
        />
      )}
    </section>
  )
}

// ── Cobertura do plano de pagamento ───────────────────────────
//
// A Clinicorp gera as parcelas em partes: no fechamento normalmente lança só
// a entrada/sinal e as demais ficam abertas, sendo lançadas conforme o paciente
// paga ou conforme renegociação. Logo, soma das parcelas < faturamento aprovado.
// Este painel torna o gap explícito: % com plano lançado + valor pendente.

function CoberturaPanel({ data }: { data: PrazoRecebimentoSection }) {
  const aprovado = data.faturamento_aprovado
  const lancado = data.valor_total
  const pendente = Math.max(aprovado - lancado, 0)
  if (aprovado <= 0) return null

  const pctLancado = (lancado / aprovado) * 100
  const pctPendente = 100 - pctLancado
  const corCobertura =
    pctLancado >= 90 ? 'text-emerald-700'
      : pctLancado >= 70 ? 'text-amber-700'
        : 'text-rose-700'

  return (
    <div className="px-5 py-3 bg-amber-50/30 border-b border-amber-100/50">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-600">
          Cobertura do plano de pagamento
        </div>
        <div className={`text-sm font-bold tabular-nums ${corCobertura}`}>
          {pctLancado.toFixed(0)}% lançado
        </div>
      </div>

      <div className="flex h-5 rounded-md overflow-hidden ring-1 ring-neutral-200 mb-2">
        <div
          className="bg-emerald-500 flex items-center justify-center text-[10px] font-bold text-white"
          style={{ width: `${Math.max(pctLancado, 5)}%` }}
          title={`Parcelas já lançadas: ${fmtBRL(lancado)}`}
        >
          {pctLancado >= 12 ? `${pctLancado.toFixed(0)}%` : ''}
        </div>
        {pctPendente > 0 && (
          <div
            className="bg-neutral-300 flex items-center justify-center text-[10px] font-bold text-neutral-700"
            style={{ width: `${pctPendente}%` }}
            title={`Pendente de lançamento: ${fmtBRL(pendente)}`}
          >
            {pctPendente >= 12 ? `${pctPendente.toFixed(0)}%` : ''}
          </div>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 text-[11px]">
        <div>
          <div className="text-neutral-500">Aprovado (header)</div>
          <div className="font-bold text-neutral-800 tabular-nums">{fmtBRL(aprovado)}</div>
        </div>
        <div>
          <div className="text-emerald-700">Parcelas lançadas</div>
          <div className="font-bold text-emerald-800 tabular-nums">{fmtBRL(lancado)}</div>
        </div>
        <div>
          <div className="text-neutral-500">Pendente de lançamento</div>
          <div className="font-bold text-neutral-700 tabular-nums">{fmtBRL(pendente)}</div>
          {data.qtd_sem_parcelas > 0 && (
            <div className="text-[10px] text-neutral-500 mt-0.5">
              {data.qtd_sem_parcelas} orçamento{data.qtd_sem_parcelas > 1 ? 's' : ''} sem nenhuma parcela ({fmtBRL(data.valor_sem_parcelas, true)})
            </div>
          )}
        </div>
      </div>

      <div className="mt-2 text-[10.5px] text-neutral-600 leading-snug">
        <strong>Por que tem gap?</strong> A Clinicorp lança o plano em partes — no fechamento normalmente só a entrada vai pra <em>core_payments</em>; as demais parcelas entram conforme paciente paga ou renegocia. A distribuição abaixo é a fotografia do que <em>já foi lançado</em>.
      </div>
    </div>
  )
}

// ── Funil ─────────────────────────────────────────────────────

function FunilCard({ data }: { data: FunilOrcamentos }) {
  const max = Math.max(data.gerados_amount, data.aprovados_amount, data.pagos_amount, 1)
  const stages = [
    { label: 'Gerados', qty: data.gerados_qty, amount: data.gerados_amount, color: 'bg-blue-500' },
    { label: 'Aprovados', qty: data.aprovados_qty, amount: data.aprovados_amount, color: 'bg-emerald-500' },
    { label: 'Pagos', qty: data.pagos_qty, amount: data.pagos_amount, color: 'bg-cyan-500' },
  ]
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Funil de Orçamentos
        </span>
      </div>
      <div className="space-y-2">
        {stages.map((s) => {
          const pct = (s.amount / max) * 100
          return (
            <div key={s.label}>
              <div className="flex items-center justify-between mb-1 text-[12px]">
                <span className="font-semibold text-neutral-700">{s.label}</span>
                <span className="text-neutral-500">
                  <span className="font-bold text-neutral-900">{fmtNum(s.qty)}</span> orçamentos · <span className="font-bold text-neutral-900">{fmtBRL(s.amount, true)}</span>
                </span>
              </div>
              <div className="h-3 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${s.color} rounded-full transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-neutral-100 grid grid-cols-2 gap-3 text-[12px]">
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-400">Conversão (R$)</div>
          <div className="font-bold text-emerald-700 text-lg">{data.conversao_aprovacao_valor_pct.toFixed(1)}%</div>
          {data.aprovacao_valor_mom_pct !== null && (
            <div className={`text-[10px] ${data.aprovacao_valor_mom_pct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {fmtPct(data.aprovacao_valor_mom_pct)} MoM
            </div>
          )}
          <div className="text-[10px] text-neutral-400 mt-0.5">
            {data.conversao_aprovacao_pct.toFixed(0)}% por qtd
          </div>
        </div>
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-400">Pagamento (R$)</div>
          <div className="font-bold text-cyan-700 text-lg">{data.conversao_pagamento_valor_pct.toFixed(1)}%</div>
          <div className="text-[10px] text-neutral-400">dos aprovados</div>
          <div className="text-[10px] text-neutral-400 mt-0.5">
            {data.conversao_pagamento_pct.toFixed(0)}% por qtd
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Top médicos (dentistas executantes) ──────────────────────

function TopMedicosCard({ data }: { data: TopMedicoFaturamento[] }) {
  const max = Math.max(...data.map((m) => m.faturamento), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={14} className="text-emerald-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Médicos por Faturamento
        </span>
        <span className="ml-auto text-[10px] text-neutral-400" title="Dentista executante dos procedimentos">
          quem executa
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem procedimentos aprovados no período.</div>
      ) : (
        <ul className="space-y-2.5">
          {data.map((m, i) => (
            <li key={m.dentist_external_id}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                  i === 0 ? 'bg-emerald-100 text-emerald-700' :
                  i === 1 ? 'bg-neutral-100 text-neutral-600' :
                  i === 2 ? 'bg-teal-100 text-teal-700' :
                  'bg-neutral-50 text-neutral-500'
                }`}>{i + 1}</span>
                <span className="text-[12px] font-medium text-neutral-800 truncate flex-1" title={m.nome}>
                  {m.nome}
                </span>
                <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                  {fmtBRL(m.faturamento, true)}
                </span>
              </div>
              <div className="ml-7 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${i === 0 ? 'bg-emerald-500' : 'bg-emerald-400'}`}
                    style={{ width: `${(m.faturamento / max) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 w-12 text-right">{m.pct_total.toFixed(0)}%</span>
              </div>
              <div className="ml-7 mt-1 text-[10px] text-neutral-500 flex items-center gap-2 flex-wrap">
                <span>{m.qtd_procedimentos} procedimentos</span>
                <span className="text-neutral-400">·</span>
                <span>ticket {fmtBRL(m.ticket_medio_procedimento, true)}/proc</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ── Top atendentes (quem registrou o orçamento) ──────────────

function TopAtendentesCard({ data }: { data: TopProfFaturamento[] }) {
  const max = Math.max(...data.map((p) => p.faturamento), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Atendentes por Faturamento
        </span>
        <span className="ml-auto text-[10px] text-neutral-400" title="Quem registrou o orçamento (recepção/secretaria)">
          quem registrou
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem aprovações no período.</div>
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
                  {fmtBRL(p.faturamento, true)}
                </span>
              </div>
              <div className="ml-7 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${i === 0 ? 'bg-amber-500' : 'bg-primary-500'}`}
                    style={{ width: `${(p.faturamento / max) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 w-12 text-right">{p.pct_total.toFixed(0)}%</span>
              </div>
              <div className="ml-7 mt-1 text-[10px] text-neutral-500 flex items-center gap-2 flex-wrap">
                <span>{p.qtd_aprovados}/{p.qtd_gerados} aprov</span>
                <span className="text-neutral-400">·</span>
                <span title="Conversão por valor (Clinicorp)">
                  <span className="font-semibold text-neutral-700">{p.taxa_conversao_valor_pct.toFixed(0)}%</span> R$
                </span>
                <span className="text-neutral-400">/</span>
                <span title="Conversão por contagem">
                  {p.taxa_conversao_pct.toFixed(0)}% qtd
                </span>
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

// ── Top categorias ────────────────────────────────────────────

function TopCategoriasCard({ data }: { data: TopCategoriaFaturamento[] }) {
  const max = Math.max(...data.map((c) => c.faturamento), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top Categorias por Faturamento
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem dados de categorias.</div>
      ) : (
        <ul className="space-y-2">
          {data.map((c) => (
            <li key={c.categoria}>
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-[12px] font-medium text-neutral-800 truncate">{c.categoria}</span>
                <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                  {fmtBRL(c.faturamento, true)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-purple-500 rounded-full"
                    style={{ width: `${(c.faturamento / max) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 tabular-nums w-12 text-right">
                  {c.pct_total.toFixed(0)}%
                </span>
                {c.mom_pct !== null && Math.abs(c.mom_pct) >= 5 && (
                  <span className={`text-[10px] font-semibold tabular-nums ${c.mom_pct > 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                    {fmtPct(c.mom_pct)}
                  </span>
                )}
              </div>
              <div className="text-[10px] text-neutral-500 mt-0.5">
                {c.qtd_procs} procedimentos · ticket {fmtBRL(c.ticket_medio, true)}/proc
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

