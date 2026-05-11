/**
 * DRE Estruturada (Conta Azul) — página dedicada com 3 níveis de drill:
 * Grupo (03 Custos Variáveis) → Subgrupo (03.1 Custos tributários) →
 * Categoria plana (ISS / COFINS / Simples Nacional / ...).
 *
 * Backend: GET /financeiro/dre?year&month (com_categorias=True).
 * Visual alinhado com /financeiro: cards brancos shadow-sm, padrão Comercial.
 */
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronDown,
  ChevronRight,
  Layers,
  Loader2,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'

import { financeiroService } from '@/services/financeiro.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { PageFooter } from '@/components/layout/PageFooter'
import { PeriodSelector } from '@/modules/analise/components/PeriodSelector'
import { useSonIA, type SonIAInsight } from '@/components/sonia/SonIAContext'
import { isCurrentMonthPartial } from '@/components/sonia/partialMonth'
import type {
  DreBlock,
  DreCategoriaItem,
  DreGrupoItem,
  DreSubgrupoItem,
} from '@/types/financeiro'

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

// Heurística: grupos cujo `codigo` começa com 01/02/07 são tipicamente
// receitas/totalizadores positivos; 03/04/05/06 são saídas. Usado pra
// colorir os mini-cards (verde para receita, rosa para custo).
function isReceitaCodigo(codigo: string): boolean {
  return codigo.startsWith('01') || codigo.startsWith('02') || codigo.startsWith('07')
}

// ── Page ──────────────────────────────────────────────────────

export default function DREPage() {
  usePageTitle('DRE Estruturada', 'Demonstrativo do Resultado do Exercício — Conta Azul', 'FINANCEIRO')

  const today = new Date()
  const [period, setPeriod] = useState({
    year: today.getFullYear(), month: today.getMonth() + 1,
  })

  const query = useQuery({
    queryKey: ['financeiro', 'dre', period.year, period.month],
    queryFn: () => financeiroService.dre(period.year, period.month),
    staleTime: 60_000,
  })

  const { publish, clear } = useSonIA()
  useEffect(() => {
    if (!query.data) return
    publish({
      pageKey: '/financeiro/dre',
      pageTitle: 'DRE Estruturada',
      data: { insight: buildDREInsight(query.data) },
    })
    return () => clear('/financeiro/dre')
  }, [query.data, publish, clear])

  return (
    <PageContainer>
      <PageHeader
        eyebrow="FINANCEIRO"
        title="DRE Estruturada"
        subtitle="3 níveis de drill: grupo → subgrupo → categoria"
        icon={<Layers size={20} />}
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
          <Loader2 className="animate-spin" size={18} /> Carregando DRE...
        </div>
      )}
      {query.isError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-800 text-sm">
          Erro ao carregar DRE. Verifique se o pipeline analytics CA foi reconstruído.
        </div>
      )}
      {query.data && <Body dre={query.data.dre} periodLabel={query.data.period.label_pt} />}

      <PageFooter dataSource="Conta Azul" />
    </PageContainer>
  )
}

// ── Body ──────────────────────────────────────────────────────

function Body({ dre, periodLabel }: { dre: DreBlock; periodLabel: string }) {
  const { receitas, custos, despesas, resultadoOp, margemOp } = useMemo(() => {
    let r = 0, c = 0, d = 0
    for (const g of dre.grupos) {
      if (g.codigo.startsWith('01')) r += g.total
      else if (g.codigo.startsWith('03')) c += g.total
      else if (g.codigo.startsWith('04')) d += g.total
    }
    const result = r - c - d
    const margem = r > 0 ? (result / r) * 100 : 0
    return { receitas: r, custos: c, despesas: d, resultadoOp: result, margemOp: margem }
  }, [dre.grupos])

  return (
    <>
      {/* Hero — 4 KPIs principais */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Receita Operacional"
          value={fmtBRL(receitas)}
          icon={<TrendingUp size={14} className="text-emerald-700" />}
          iconBg="bg-emerald-50"
          subtitle={`${periodLabel} · grupo 01`}
        />
        <KpiCard
          label="Custos Variáveis"
          value={fmtBRL(custos)}
          icon={<TrendingDown size={14} className="text-rose-700" />}
          iconBg="bg-rose-50"
          subtitle="grupo 03"
        />
        <KpiCard
          label="Despesas Fixas"
          value={fmtBRL(despesas)}
          icon={<TrendingDown size={14} className="text-amber-700" />}
          iconBg="bg-amber-50"
          subtitle="grupo 04"
        />
        <KpiCard
          label="Resultado Operacional"
          value={fmtBRL(resultadoOp)}
          icon={<Wallet size={14} className={resultadoOp >= 0 ? 'text-emerald-700' : 'text-rose-700'} />}
          iconBg={resultadoOp >= 0 ? 'bg-emerald-50' : 'bg-rose-50'}
          subtitle={`margem ${margemOp.toFixed(1)}% · receita - custos - despesas`}
          emphasized
        />
      </div>

      {/* Árvore DRE com 3 níveis de drill */}
      <DreTree dre={dre} periodLabel={periodLabel} />
    </>
  )
}

// ── KPI Card ──────────────────────────────────────────────────

function KpiCard({
  label, value, icon, iconBg, subtitle, emphasized,
}: {
  label: string
  value: string
  icon: React.ReactNode
  iconBg: string
  subtitle?: string
  emphasized?: boolean
}) {
  return (
    <div className={`bg-white border rounded-xl p-4 shadow-sm ${
      emphasized ? 'border-primary-200' : 'border-neutral-200'
    }`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`w-7 h-7 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
          {icon}
        </span>
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500 truncate">
          {label}
        </span>
      </div>
      <div className="text-2xl font-bold text-neutral-900 tabular-nums mb-1">{value}</div>
      {subtitle && (
        <div className="text-[11px] text-neutral-500 leading-snug">{subtitle}</div>
      )}
    </div>
  )
}

// ── DRE Tree (3 níveis de drill) ──────────────────────────────

function DreTree({ dre, periodLabel }: { dre: DreBlock; periodLabel: string }) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [expandedSubs, setExpandedSubs] = useState<Set<string>>(new Set())

  const grupos = useMemo(
    () => dre.grupos.filter(g => g.total !== 0),
    [dre.grupos],
  )
  const grupoMaiorTotal = Math.max(...grupos.map(g => Math.abs(g.total)), 1)

  const toggleGroup = (id: string) => {
    setExpandedGroups(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }
  const toggleSub = (id: string) => {
    setExpandedSubs(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Layers size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          DRE — {periodLabel}
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">
          {dre.total_nao_classificado > 0
            ? <>R$ {fmtNum(Math.round(dre.total_nao_classificado))} sem categoria DRE</>
            : <>100% classificado</>}
        </span>
      </div>

      {dre.grupos.length === 0 && (
        <div className="text-sm text-neutral-400 py-6 text-center">
          Plano DRE não sincronizado. Rode sync de cadastros CA + reconstruir pipeline.
        </div>
      )}
      {dre.grupos.length > 0 && grupos.length === 0 && (
        <div className="text-sm text-neutral-400 py-6 text-center">
          Sem movimentações classificadas no DRE neste período.
        </div>
      )}

      {grupos.length > 0 && (
        <ul className="space-y-2">
          {grupos.map(grupo => {
            const isOpen = expandedGroups.has(grupo.external_id)
            const widthPct = (Math.abs(grupo.total) / grupoMaiorTotal) * 100
            const subAtivos = grupo.subgrupos.filter(s => s.total !== 0)
            const cor = isReceitaCodigo(grupo.codigo) ? 'bg-emerald-500' : 'bg-rose-500'
            return (
              <li key={grupo.external_id}>
                <button
                  onClick={() => toggleGroup(grupo.external_id)}
                  className="w-full text-left flex items-center gap-2 hover:bg-neutral-50 rounded p-2 transition"
                  disabled={subAtivos.length === 0}
                >
                  <span className="w-4 h-4 flex items-center justify-center text-neutral-400 shrink-0">
                    {subAtivos.length > 0 && (isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />)}
                  </span>
                  <span className="text-[11px] font-mono font-bold text-neutral-500 w-7 shrink-0">{grupo.codigo}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2 mb-1">
                      <span className="text-sm font-semibold text-neutral-800 truncate">{grupo.descricao}</span>
                      <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">
                        {fmtBRL(grupo.total)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                        <div className={`h-full ${cor} rounded-full`} style={{ width: `${widthPct}%` }} />
                      </div>
                      {subAtivos.length > 0 && (
                        <span className="text-[10px] text-neutral-500 shrink-0 w-12 text-right">{subAtivos.length} sub.</span>
                      )}
                    </div>
                  </div>
                </button>
                {isOpen && subAtivos.length > 0 && (
                  <DreSubgrupoList
                    grupo={grupo}
                    expandedSubs={expandedSubs}
                    onToggleSub={toggleSub}
                  />
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

function DreSubgrupoList({
  grupo, expandedSubs, onToggleSub,
}: {
  grupo: DreGrupoItem
  expandedSubs: Set<string>
  onToggleSub: (id: string) => void
}) {
  const subAtivos = grupo.subgrupos.filter(s => s.total !== 0)
  const max = Math.max(...subAtivos.map(s => Math.abs(s.total)), 1)
  const cor = isReceitaCodigo(grupo.codigo) ? 'bg-emerald-400' : 'bg-rose-400'
  return (
    <div className="ml-9 mt-1 space-y-1.5 pl-3 border-l border-primary-200">
      {subAtivos.map(s => {
        const w = (Math.abs(s.total) / max) * 100
        const isOpen = expandedSubs.has(s.external_id)
        const hasCats = (s.categorias?.length ?? 0) > 0
        return (
          <div key={s.external_id}>
            <button
              onClick={() => hasCats && onToggleSub(s.external_id)}
              className={`w-full text-left flex items-center gap-2 rounded p-1.5 transition ${
                hasCats ? 'hover:bg-neutral-50 cursor-pointer' : 'cursor-default'
              }`}
              disabled={!hasCats}
            >
              <span className="w-4 h-4 flex items-center justify-center text-neutral-400 shrink-0">
                {hasCats && (isOpen ? <ChevronDown size={11} /> : <ChevronRight size={11} />)}
              </span>
              <span className="text-[10px] font-mono text-neutral-400 w-10 shrink-0">{s.codigo || '—'}</span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2 mb-0.5">
                  <span className="text-[12px] text-neutral-700 truncate">{s.descricao}</span>
                  <span className="text-[12px] font-semibold tabular-nums text-neutral-900 shrink-0">
                    {fmtBRL(s.total)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 bg-neutral-100 rounded-full overflow-hidden">
                    <div className={`h-full ${cor} rounded-full`} style={{ width: `${w}%` }} />
                  </div>
                  <span className="text-[10px] text-neutral-400 w-12 text-right shrink-0">
                    {hasCats ? `${s.categorias.length} cat.` : `${s.qtd_categorias} cat.`}
                  </span>
                </div>
              </div>
            </button>
            {isOpen && hasCats && (
              <DreCategoriaList categorias={s.categorias} />
            )}
          </div>
        )
      })}
    </div>
  )
}

function DreCategoriaList({ categorias }: { categorias: DreCategoriaItem[] }) {
  return (
    <ul className="ml-9 mt-1 space-y-1 pl-3 border-l border-neutral-200 mb-2">
      {categorias.map((c, i) => (
        <li key={`${c.external_id}-${i}`} className="flex items-baseline justify-between gap-3 text-[11px] py-0.5">
          <span className="text-neutral-600 truncate flex-1" title={c.nome}>· {c.nome}</span>
          <span className="text-neutral-400 tabular-nums w-12 text-right shrink-0">
            {c.pct_subgrupo.toFixed(1)}%
          </span>
          <span className="font-semibold tabular-nums text-neutral-800 w-24 text-right shrink-0">
            {fmtBRL(c.total, true)}
          </span>
        </li>
      ))}
    </ul>
  )
}

// ── Insight pra SonIA ─────────────────────────────────────────

function buildDREInsight(data: { period: { label: string; year: number; month: number }; dre: DreBlock }): SonIAInsight {
  const receita = data.dre.grupos
    .filter((g) => g.codigo === '01' || g.codigo === '02')
    .reduce((s, g) => s + g.total, 0)
  const custosVar = data.dre.grupos.find((g) => g.codigo === '03')?.total ?? 0
  const despFix = data.dre.grupos.find((g) => g.codigo === '04')?.total ?? 0
  const resultado = receita - Math.abs(custosVar) - Math.abs(despFix)
  const margem = receita > 0 ? (resultado / receita) * 100 : 0

  // Mês em andamento: projetar no ritmo atual, suprimir veredito sobre
  // resultado/margem (o mês mal começou).
  const progress = isCurrentMonthPartial(data.period.year, data.period.month)
  if (progress.partial) {
    const factor = progress.totalDays / progress.days
    const projReceita = receita * factor
    const projCustos = Math.abs(custosVar) * factor
    const projDesp = Math.abs(despFix) * factor
    const projResultado = projReceita - projCustos - projDesp
    const projMargem = projReceita > 0 ? (projResultado / projReceita) * 100 : 0

    return {
      mood: 'curious',
      headline: `Olhei a DRE de ${data.period.label} até agora.`,
      detail: `Estamos no dia ${progress.days} de ${progress.totalDays} (${progress.progressPct.toFixed(0)}% do mês). Por enquanto a receita parcial é ${fmtBRL(receita, true)} e o resultado ${fmtBRL(resultado, true)}. No ritmo atual, o mês deve fechar com resultado de ${fmtBRL(projResultado, true)} (margem ${projMargem.toFixed(1)}%).`,
      bullets: [
        { text: `Receita ${fmtBRL(receita, true)} · projeção ${fmtBRL(projReceita, true)}.`, tone: 'neutral' },
        { text: `Custos variáveis ${fmtBRL(Math.abs(custosVar), true)} · projeção ${fmtBRL(projCustos, true)}.`, tone: 'neutral' },
        { text: `Despesas fixas ${fmtBRL(Math.abs(despFix), true)} · projeção ${fmtBRL(projDesp, true)}.`, tone: 'neutral' },
        { text: `Resultado parcial ${fmtBRL(resultado, true)} · projeção ${fmtBRL(projResultado, true)} (margem ${projMargem.toFixed(1)}%).`, tone: projResultado < 0 ? 'warning' : 'neutral' },
      ],
    }
  }

  const negativa = resultado < 0
  const margemBaixa = !negativa && margem < 10
  const margemBoa = margem >= 20

  const mood: SonIAInsight['mood'] = negativa ? 'alert' : margemBoa ? 'happy' : 'curious'

  const headline = negativa
    ? 'Olhei aqui — queria sentar com você pra conversar.'
    : margemBaixa
    ? 'Olhei a DRE com calma.'
    : margemBoa
    ? 'Olha que notícia boa.'
    : 'Vim te trazer um resumo da DRE.'

  const detail = negativa
    ? `Em ${data.period.label} as despesas superaram a receita — resultado ficou em ${fmtBRL(resultado, true)}. Vale a gente abrir junto pra entender onde dá pra equilibrar.`
    : margemBaixa
    ? `Receita de ${fmtBRL(receita, true)} e margem de ${margem.toFixed(1)}%. Está apertado — quem sabe encontremos um espacinho nas despesas.`
    : margemBoa
    ? `Receita de ${fmtBRL(receita, true)} com margem operacional de ${margem.toFixed(1)}%. Resultado positivo de ${fmtBRL(resultado, true)} — saudável.`
    : `Receita de ${fmtBRL(receita, true)}, resultado de ${fmtBRL(resultado, true)} (margem ${margem.toFixed(1)}%).`

  const bullets: SonIAInsight['bullets'] = [
    { text: `Receita operacional ${fmtBRL(receita, true)}.`, tone: 'neutral' },
    { text: `Custos variáveis ${fmtBRL(Math.abs(custosVar), true)}.`, tone: 'neutral' },
    { text: `Despesas fixas ${fmtBRL(Math.abs(despFix), true)}.`, tone: 'neutral' },
    {
      text: `Resultado ${fmtBRL(resultado, true)} (margem ${margem.toFixed(1)}%).`,
      tone: negativa ? 'negative' : margemBoa ? 'positive' : 'warning',
    },
  ]

  const top = [...data.dre.grupos]
    .filter((g) => Math.abs(g.total) > 0)
    .sort((a, b) => Math.abs(b.total) - Math.abs(a.total))[0]
  if (top) {
    bullets.push({
      text: `Grupo mais relevante: ${top.descricao} (${fmtBRL(Math.abs(top.total), true)}).`,
      tone: 'neutral',
    })
  }

  return { mood, headline, detail, bullets }
}
