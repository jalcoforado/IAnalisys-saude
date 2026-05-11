/**
 * Cockpit Financeiro (Conta Azul) — fluxo de caixa, DRE, saldos.
 * Visual alinhado com /analise/comercial: cards brancos minimalistas,
 * headers inline (icon + uppercase tracking-wider), shadow-sm sem hover.
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRightLeft,
  ArrowUpRight,
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CreditCard,
  HandCoins,
  Info,
  Landmark,
  Layers,
  Loader2,
  PiggyBank,
  TrendingDown,
  TrendingUp,
  Vault,
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
  CategoriaItem,
  CentroCustoItem,
  ConciliacaoBlock as ConciliacaoBlockT,
  ContaBancariaItem,
  FinanceiroOverviewResponse,
  MetodosPagamentoBlock,
  SaldosBancariosBlock,
  StatusMixItem,
  TransferenciasBlock,
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
const fmtPct = (n: number | null | undefined) => {
  if (n === null || n === undefined) return null
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}
const fmtTime = (iso: string | null) => {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return '—' }
}
const _delta = (curr: number, prev: number): number | null => {
  if (prev === 0) return null
  return ((curr - prev) / Math.abs(prev)) * 100
}

const STATUS_COLORS: Record<string, string> = {
  pago: '#10b981',
  em_aberto: '#f59e0b',
  vencido: '#dc2626',
}

const PIE_COLORS = ['#1d4ed8', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#94a3b8']

// ── Page ──────────────────────────────────────────────────────

export default function FinanceiroPage() {
  usePageTitle('Financeiro', 'Fluxo de caixa, DRE e saldos bancários (Conta Azul)', 'CONTA AZUL')

  const today = new Date()
  const [period, setPeriod] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 })

  const query = useQuery({
    queryKey: ['financeiro', 'overview', period.year, period.month],
    queryFn: () => financeiroService.overview(period.year, period.month),
    staleTime: 60_000,
  })

  const { publish, clear } = useSonIA()
  useEffect(() => {
    if (!query.data) return
    publish({
      pageKey: '/financeiro',
      pageTitle: 'Fluxo de Caixa',
      data: { insight: buildFluxoCaixaInsight(query.data) },
    })
    return () => clear('/financeiro')
  }, [query.data, publish, clear])

  return (
    <PageContainer>
      <PageHeader
        eyebrow="CONTA AZUL"
        title="Financeiro"
        subtitle="Fluxo de caixa · DRE estruturada · saldos bancários"
        icon={<Wallet size={20} />}
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
          <Loader2 className="animate-spin" size={18} /> Carregando financeiro...
        </div>
      )}
      {query.isError && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-800 text-sm">
          Erro ao carregar dashboard. Verifique se o pipeline analytics CA foi reconstruído.
        </div>
      )}
      {query.data && <Body data={query.data} />}

      <PageFooter dataSource="Conta Azul" />
    </PageContainer>
  )
}

// ── Body ──────────────────────────────────────────────────────

function Body({ data }: { data: FinanceiroOverviewResponse }) {
  const { kpis, kpis_previous, saldos_bancarios, dre, metodos_pagamento, conciliacao, transferencias, top_receitas, top_despesas, centros_custo, status_mix, evolution, period } = data

  const entradasMoM = _delta(kpis.entradas, kpis_previous.entradas)
  const saidasMoM = _delta(kpis.saidas, kpis_previous.saidas)
  const aReceberMoM = _delta(kpis.a_receber, kpis_previous.a_receber)
  const aPagarMoM = _delta(kpis.a_pagar, kpis_previous.a_pagar)
  const saldoPrevisto = kpis.saldo_liquido + kpis.a_receber - kpis.a_pagar

  return (
    <>
      {/* Banner explicativo do escopo CA */}
      <ScopeBanner />

      {/* KPIs principais — 4 cards (padrão Comercial) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Saldo bancário"
          value={fmtBRL(saldos_bancarios.saldo_bancos)}
          icon={<Landmark size={14} className="text-blue-700" />}
          iconBg="bg-blue-50"
          subtitle={`${saldos_bancarios.qtd_bancos_ativos} ${saldos_bancarios.qtd_bancos_ativos === 1 ? 'conta bancária' : 'contas bancárias'}`}
          footer={
            saldos_bancarios.qtd_caixinhas_ativas > 0 && (
              <span className="text-[11px] text-amber-700 inline-flex items-center gap-1">
                <Vault size={11} />
                + {fmtBRL(saldos_bancarios.saldo_caixinhas, true)} em caixinhas ({saldos_bancarios.qtd_caixinhas_ativas})
              </span>
            )
          }
          emphasized
        />
        <KpiCard
          label="Entradas"
          value={fmtBRL(kpis.entradas)}
          icon={<ArrowUpRight size={14} className="text-emerald-700" />}
          iconBg="bg-emerald-50"
          subtitle={`${period.label_pt} · realizado`}
          delta={entradasMoM}
          footer={<EncargosFooter encargos={kpis.encargos_entradas} base={kpis.entradas} />}
        />
        <KpiCard
          label="Saídas"
          value={fmtBRL(kpis.saidas)}
          icon={<ArrowDownRight size={14} className="text-rose-700" />}
          iconBg="bg-rose-50"
          subtitle={`${period.label_pt} · realizado`}
          delta={saidasMoM}
          deltaInverse
          footer={<EncargosFooter encargos={kpis.encargos_saidas} base={kpis.saidas} />}
        />
        <KpiCard
          label="Saldo previsto"
          value={fmtBRL(saldoPrevisto)}
          icon={<PiggyBank size={14} className="text-purple-700" />}
          iconBg="bg-purple-50"
          subtitle="realizado + a receber − a pagar"
        />
      </div>

      {/* KPIs secundários — 4 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="A receber"
          value={fmtBRL(kpis.a_receber)}
          icon={<HandCoins size={14} className="text-emerald-700" />}
          iconBg="bg-emerald-50"
          subtitle={`vs ${fmtBRL(kpis_previous.a_receber, true)} mês anterior`}
          delta={aReceberMoM}
        />
        <KpiCard
          label="A pagar"
          value={fmtBRL(kpis.a_pagar)}
          icon={<TrendingDown size={14} className="text-amber-700" />}
          iconBg="bg-amber-50"
          subtitle={`vs ${fmtBRL(kpis_previous.a_pagar, true)} mês anterior`}
          delta={aPagarMoM}
          deltaInverse
        />
        <KpiCard
          label="Inadimplência"
          value={`${kpis.inadimplencia_pct.toFixed(1)}%`}
          icon={<AlertTriangle size={14} className="text-rose-700" />}
          iconBg="bg-rose-50"
          subtitle={`${fmtNum(kpis.qtd_parcelas_vencidas)} parcelas vencidas`}
        />
        <KpiCard
          label="Saldo líquido do mês"
          value={fmtBRL(kpis.saldo_liquido)}
          icon={<TrendingUp size={14} className="text-cyan-700" />}
          iconBg="bg-cyan-50"
          subtitle={`entradas − saídas em ${period.label_pt}`}
        />
      </div>

      {/* Distribuição por banco */}
      <SaldoPorBancoCard data={saldos_bancarios} />

      {/* DRE foi movida para a página dedicada /financeiro/dre — link
           rápido aqui pra quem quer drill 3 níveis (grupo → subgrupo → categoria). */}
      <DreShortcutCard total={dre.grupos.length} periodLabel={period.label_pt} />

      {/* Onde caiu o dinheiro + Conciliação */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <MetodosPagamentoCard data={metodos_pagamento} periodLabel={period.label_pt} />
        <ConciliacaoCard data={conciliacao} periodLabel={period.label_pt} />
      </div>

      {/* Transferências internas (Fase 3) */}
      <TransferenciasCard data={transferencias} periodLabel={period.label_pt} />

      {/* Evolução 12 meses + Status mix */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2">
          <EvolutionChart data={evolution} />
        </div>
        <StatusMixCard items={status_mix} />
      </div>

      {/* Top categorias receitas + despesas */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <CategoriasRankingCard
          items={top_receitas}
          title="Top 5 receitas"
          subtitle="Maiores entradas por categoria"
          icon={<TrendingUp size={14} className="text-neutral-600" />}
          colorBar="bg-emerald-500"
        />
        <CategoriasRankingCard
          items={top_despesas}
          title="Top 5 despesas"
          subtitle="Maiores saídas por categoria"
          icon={<TrendingDown size={14} className="text-neutral-600" />}
          colorBar="bg-rose-500"
        />
      </div>

      {/* Centros de custo */}
      <CentrosCustoCard items={centros_custo} />
    </>
  )
}

// ── Banner escopo CA ──────────────────────────────────────────

function ScopeBanner() {
  return (
    <div className="bg-gradient-to-r from-amber-50 to-white border border-amber-200 rounded-lg px-4 py-2.5 flex items-start gap-3 text-[12px] text-amber-900">
      <Info size={15} className="text-amber-600 shrink-0 mt-0.5" />
      <div className="leading-snug">
        <strong>Escopo desta tela:</strong> só dados do <strong>Conta Azul</strong> — fluxo realizado de
        contas a pagar/receber, saldos bancários e DRE. Receitas via PIX/cartão de consultas
        (Clinicorp) que caem direto no banco <strong>não passam pelo CA</strong> e aparecem em{' '}
        <a href="/analise/financeiro" className="font-semibold underline decoration-dotted hover:decoration-solid">
          Análise Financeira
        </a>.
      </div>
    </div>
  )
}

// ── KPI Card (mesmo visual do KpiCardEnriched, sem sparkline) ─

function KpiCard({
  label, value, icon, iconBg, subtitle, footer, delta, deltaInverse, emphasized,
}: {
  label: string
  value: string
  icon: React.ReactNode
  iconBg: string
  subtitle?: string
  footer?: React.ReactNode
  delta?: number | null
  deltaInverse?: boolean
  emphasized?: boolean
}) {
  const deltaTxt = fmtPct(delta)
  const deltaCls = (() => {
    if (delta == null) return 'text-neutral-400'
    const isGood = deltaInverse ? delta < 0 : delta > 0
    return isGood ? 'text-emerald-600' : 'text-rose-600'
  })()

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
      {deltaTxt && (
        <div className="flex items-center gap-3 text-[11px] mb-1">
          <span className={`font-semibold tabular-nums ${deltaCls}`}>
            {deltaTxt} <span className="font-normal text-neutral-400">MoM</span>
          </span>
        </div>
      )}
      {subtitle && (
        <div className="text-[11px] text-neutral-500 leading-snug">{subtitle}</div>
      )}
      {footer && (
        <div className="mt-2 pt-2 border-t border-neutral-100">{footer}</div>
      )}
    </div>
  )
}

// Footer dos KPIs Entradas/Saídas: mostra juros + multa - desconto vindos do
// detalhamento /parcelas/{id}. Sem isso, o card mostra só "valor pago limpo"
// e fica ~R$ 1-2k abaixo do que o PDF do CA reporta. Só aparece quando há
// encargos e baixas detalhadas no mês.
function EncargosFooter({ encargos, base }: { encargos: number; base: number }) {
  if (Math.abs(encargos) < 0.01) return null
  const total = base + encargos
  const isPositivo = encargos > 0
  return (
    <span className="text-[11px] text-neutral-500 leading-snug" title="Diferença vs PDF do Conta Azul: juros + multa - desconto, vindos do detalhamento /parcelas/{id}.">
      {isPositivo ? '+' : '−'} {fmtBRL(Math.abs(encargos), true)} em juros/multa{' '}
      <span className="text-neutral-400">· {fmtBRL(total, true)} c/ encargos</span>
    </span>
  )
}

// ── Distribuição por banco ────────────────────────────────────

function SaldoPorBancoCard({ data }: { data: SaldosBancariosBlock }) {
  const [showCaixinhas, setShowCaixinhas] = useState(false)
  const [showInativas, setShowInativas] = useState(false)
  if (data.qtd_contas_total === 0) return null

  const bancos = data.contas.filter(c => c.ativo && c.is_banco_real)
  const caixinhas = data.contas.filter(c => c.ativo && !c.is_banco_real)
  const inativas = data.contas.filter(c => !c.ativo)

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Landmark size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Distribuição por banco
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">
          atualizado {fmtTime(data.atualizado_em)}
        </span>
      </div>

      {bancos.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {bancos.map(c => <ContaBancoItem key={c.external_id} c={c} />)}
        </div>
      )}

      {caixinhas.length > 0 && (
        <div className="mt-3 pt-3 border-t border-neutral-100">
          <button
            onClick={() => setShowCaixinhas(!showCaixinhas)}
            className="text-[11px] text-amber-800 hover:text-amber-900 flex items-center gap-1.5"
          >
            {showCaixinhas ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            <Vault size={12} />
            <strong>{caixinhas.length}</strong> caixinha{caixinhas.length === 1 ? '' : 's'}/cofre{caixinhas.length === 1 ? '' : 's'}{' '}
            <span className="text-amber-700">({fmtBRL(data.saldo_caixinhas, true)})</span>
            <span className="text-neutral-400">— registros contábeis internos, não somam ao saldo bancário</span>
          </button>
          {showCaixinhas && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-2">
              {caixinhas.map(c => <ContaBancoItem key={c.external_id} c={c} />)}
            </div>
          )}
        </div>
      )}

      {inativas.length > 0 && (
        <div className="mt-3 pt-3 border-t border-neutral-100">
          <button
            onClick={() => setShowInativas(!showInativas)}
            className="text-[11px] text-neutral-500 hover:text-neutral-700 flex items-center gap-1.5"
          >
            {showInativas ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
            {inativas.length} conta{inativas.length === 1 ? '' : 's'} inativa{inativas.length === 1 ? '' : 's'}
          </button>
          {showInativas && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-2">
              {inativas.map(c => <ContaBancoItem key={c.external_id} c={c} muted />)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ContaBancoItem({ c, muted = false }: { c: ContaBancariaItem; muted?: boolean }) {
  const positive = c.saldo_atual >= 0
  return (
    <div className={`rounded-md border border-neutral-100 bg-neutral-50/50 px-3 py-2 ${muted ? 'opacity-60' : ''}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`w-2 h-2 rounded-full shrink-0 ${c.is_banco_real ? 'bg-blue-500' : 'bg-amber-500'}`} />
        <span className="text-[11px] font-semibold text-neutral-800 truncate" title={c.nome}>{c.nome}</span>
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span className={`text-[13px] font-bold tabular-nums ${positive ? 'text-neutral-900' : 'text-rose-700'}`}>
          {positive ? '' : '-'}{fmtBRL(Math.abs(c.saldo_atual))}
        </span>
        {c.tipo && (
          <span className="text-[9px] uppercase tracking-wide text-neutral-500 font-semibold shrink-0">
            {c.tipo.replace(/_/g, ' ')}
          </span>
        )}
      </div>
      {c.banco && (
        <div className="text-[10px] text-neutral-500 mt-0.5 truncate">{c.banco}</div>
      )}
    </div>
  )
}

// ── DRE shortcut ──────────────────────────────────────────────

// Card compacto que substituiu a árvore completa de DRE — a árvore com
// drill 3 níveis vive agora em /financeiro/dre. Aqui só linkamos pra lá.
function DreShortcutCard({ total, periodLabel }: { total: number; periodLabel: string }) {
  return (
    <a
      href="/financeiro/dre"
      className="block bg-white border border-neutral-200 rounded-xl p-4 shadow-sm hover:border-primary-200 hover:shadow transition group"
    >
      <div className="flex items-center gap-3">
        <span className="w-9 h-9 rounded-lg bg-primary-50 flex items-center justify-center shrink-0">
          <Layers size={16} className="text-primary-700" />
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 mb-0.5">
            <span className="text-sm font-semibold text-neutral-900">DRE Estruturada</span>
            <span className="text-[10px] uppercase tracking-wider text-neutral-400">{periodLabel}</span>
          </div>
          <div className="text-[12px] text-neutral-500 leading-snug">
            {total > 0
              ? <>{total} grupos classificados · drill em 3 níveis (grupo → subgrupo → categoria)</>
              : <>Plano DRE não sincronizado.</>}
          </div>
        </div>
        <ChevronRight size={16} className="text-neutral-400 group-hover:text-primary-700 shrink-0" />
      </div>
    </a>
  )
}

// ── Métodos de pagamento (Onde caiu o dinheiro) ───────────────

const METODO_BAR_PALETTE: Record<string, string> = {
  PIX_PAGAMENTO_INSTANTANEO: 'bg-emerald-500',
  PIX: 'bg-emerald-500',
  BOLETO_BANCARIO: 'bg-blue-500',
  BOLETO: 'bg-blue-500',
  CARTAO_CREDITO: 'bg-purple-500',
  CARTAO_DEBITO: 'bg-cyan-500',
  DINHEIRO: 'bg-amber-500',
  TRANSFERENCIA_BANCARIA: 'bg-indigo-500',
  DEBITO_AUTOMATICO: 'bg-pink-500',
  CHEQUE: 'bg-orange-500',
}

function metodoBar(metodo: string): string {
  return METODO_BAR_PALETTE[metodo.toUpperCase()] ?? 'bg-neutral-400'
}

function MetodosPagamentoCard({
  data, periodLabel,
}: { data: MetodosPagamentoBlock; periodLabel: string }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <CreditCard size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Onde caiu o dinheiro
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">
          receitas pagas em {periodLabel}
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(data.qtd_total)} baixas · {fmtBRL(data.valor_total, true)} total
      </div>

      {data.qtd_total === 0 ? (
        <div className="space-y-2">
          <div className="text-sm text-neutral-400 py-3 text-center">
            Nenhuma baixa detalhada neste período.
          </div>
          {data.pendentes_detalhamento > 0 && (
            <div className="text-[11px] text-blue-700 bg-blue-50 border border-blue-200 rounded-md px-3 py-2 leading-snug">
              <strong>{fmtNum(data.pendentes_detalhamento)}</strong> parcelas pagas neste mês
              ainda não têm detalhamento. Rode <strong>Detalhar baixas</strong> em{' '}
              <a href="/admin/sync" className="underline decoration-dotted hover:decoration-solid">/admin/sync</a> pra
              capturar método de pagamento, conta destino e conciliação.
            </div>
          )}
        </div>
      ) : (
        <>
          <ul className="space-y-2.5">
            {data.metodos.map((m) => (
              <li key={m.metodo} className="flex items-center gap-3">
                <span className={`w-2 h-6 rounded-sm ${metodoBar(m.metodo)} shrink-0`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2 mb-1">
                    <span className="text-[12px] font-semibold text-neutral-800 truncate">{m.label}</span>
                    <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtBRL(m.valor_total, true)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                      <div className={`h-full ${metodoBar(m.metodo)} opacity-80`} style={{ width: `${m.pct_valor}%` }} />
                    </div>
                    <span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">
                      {m.pct_valor.toFixed(0)}%
                    </span>
                    <span className="text-[10px] text-neutral-400 tabular-nums w-10 text-right">
                      {fmtNum(m.qtd_baixas)}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
          {data.cobertura_pct < 95 && (
            <div className="mt-3 pt-3 border-t border-neutral-100 text-[11px] text-amber-700 leading-snug">
              <strong>Cobertura: {data.cobertura_pct.toFixed(1)}%</strong> das parcelas pagas no mês
              {data.pendentes_detalhamento > 0 && (
                <> · {fmtNum(data.pendentes_detalhamento)} ainda sem detalhamento (rode em /admin/sync)</>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Conciliação ───────────────────────────────────────────────

function ConciliacaoCard({
  data, periodLabel,
}: { data: ConciliacaoBlockT; periodLabel: string }) {
  const corPct =
    data.pct_conciliado >= 90 ? 'text-emerald-700'
      : data.pct_conciliado >= 70 ? 'text-amber-700'
        : 'text-rose-700'
  const max = Math.max(...data.contas_destino.map(c => c.valor_total), 1)

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <CheckCircle2 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Conciliação bancária
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">{periodLabel}</span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(data.qtd_total)} baixas · reconciliadas com extrato CA
      </div>

      {data.qtd_total === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem baixas no período.</div>
      ) : (
        <>
          {/* Mini hero da taxa */}
          <div className="rounded-lg border border-neutral-100 bg-neutral-50/50 p-3 mb-3">
            <div className="flex items-baseline justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-500">
                  Taxa de conciliação
                </div>
                <div className={`text-2xl font-bold tabular-nums ${corPct}`}>
                  {data.pct_conciliado.toFixed(1)}%
                </div>
              </div>
              <div className="text-right text-[11px] text-neutral-600">
                <div className="tabular-nums">
                  <strong>{fmtNum(data.qtd_conciliadas)}</strong> de {fmtNum(data.qtd_total)}
                </div>
                <div className="text-neutral-400">
                  {fmtBRL(data.valor_conciliado, true)} · faltam {fmtBRL(data.valor_nao_conciliado, true)}
                </div>
              </div>
            </div>
          </div>

          {/* Top contas destino */}
          {data.contas_destino.length > 0 && (
            <>
              <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-500 mb-2">
                Onde mais caiu dinheiro
              </div>
              <ul className="space-y-2">
                {data.contas_destino.slice(0, 5).map((c) => (
                  <li key={c.external_id ?? c.nome} className="flex items-center gap-3">
                    <span className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline justify-between gap-2 mb-1">
                        <span className="text-[12px] font-medium text-neutral-700 truncate" title={c.nome}>
                          {c.nome}
                        </span>
                        <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                          {fmtBRL(c.valor_total, true)}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1 bg-neutral-100 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-400 rounded-full" style={{ width: `${(c.valor_total / max) * 100}%` }} />
                        </div>
                        <span className="text-[10px] text-neutral-500 tabular-nums w-10 text-right">
                          {c.pct_valor.toFixed(0)}%
                        </span>
                        <span className="text-[10px] text-neutral-400 tabular-nums w-10 text-right">
                          {fmtNum(c.qtd_baixas)}
                        </span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  )
}

// ── Transferências internas (Fase 3) ──────────────────────────

function TransferenciasCard({
  data, periodLabel,
}: { data: TransferenciasBlock; periodLabel: string }) {
  const max = Math.max(...data.fluxos.map(f => f.valor_total), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <ArrowRightLeft size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Transferências internas
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">{periodLabel}</span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        movimentação entre contas — não conta como receita/despesa
      </div>

      {data.qtd === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem transferências no período.</div>
      ) : (
        <>
          {/* Mini hero do volume total */}
          <div className="rounded-lg border border-neutral-100 bg-neutral-50/50 p-3 mb-3">
            <div className="flex items-baseline justify-between gap-3">
              <div>
                <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-500">
                  Volume movido internamente
                </div>
                <div className="text-2xl font-bold tabular-nums text-neutral-900">
                  {fmtBRL(data.valor_total)}
                </div>
              </div>
              <div className="text-right text-[11px] text-neutral-600">
                <div className="tabular-nums">
                  <strong>{fmtNum(data.qtd)}</strong> transferências
                </div>
                <div className="text-neutral-400">
                  {data.qtd_contas_origem} origens · {data.qtd_contas_destino} destinos
                </div>
              </div>
            </div>
          </div>

          {/* Top fluxos */}
          <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-500 mb-2">
            Principais fluxos (origem → destino)
          </div>
          <ul className="space-y-2">
            {data.fluxos.slice(0, 6).map((f, i) => (
              <li key={`${f.origem_external_id}-${f.destino_external_id}-${i}`} className="flex items-center gap-3">
                <span className="w-2 h-6 rounded-sm bg-indigo-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2 mb-1">
                    <span className="text-[12px] text-neutral-700 truncate" title={`${f.origem_nome} → ${f.destino_nome}`}>
                      <span className="font-medium">{f.origem_nome}</span>
                      <ArrowRightLeft size={10} className="inline mx-1.5 text-neutral-400" />
                      <span className="font-medium">{f.destino_nome}</span>
                    </span>
                    <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtBRL(f.valor_total, true)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 bg-neutral-100 rounded-full overflow-hidden">
                      <div className="h-full bg-indigo-400 rounded-full" style={{ width: `${(f.valor_total / max) * 100}%` }} />
                    </div>
                    <span className="text-[10px] text-neutral-400 tabular-nums w-10 text-right">
                      {fmtNum(f.qtd)}×
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

// ── Evolution chart ───────────────────────────────────────────

function EvolutionChart({ data }: { data: FinanceiroOverviewResponse['evolution'] }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Evolução 12 meses — entradas, saídas e saldo
        </span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="label_pt" tick={{ fontSize: 10, fill: '#64748b' }} />
          <YAxis tick={{ fontSize: 10, fill: '#64748b' }} tickFormatter={(v) => fmtBRL(v, true)} width={60} />
          <Tooltip
            formatter={(v) => fmtBRL(Number(v))}
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="entradas" fill="#10b981" name="Entradas" radius={[3, 3, 0, 0]} />
          <Bar dataKey="saidas" fill="#dc2626" name="Saídas" radius={[3, 3, 0, 0]} />
          <Line type="monotone" dataKey="saldo" stroke="#1d4ed8" strokeWidth={2} name="Saldo" dot={{ r: 3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Status mix card ───────────────────────────────────────────

function StatusMixCard({ items }: { items: StatusMixItem[] }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <AlertTriangle size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Status das parcelas
        </span>
      </div>
      {items.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem parcelas no período.</div>
      ) : (
        <>
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={items} dataKey="total" nameKey="label_pt" cx="50%" cy="50%" innerRadius={32} outerRadius={60} paddingAngle={2}>
                {items.map((s, i) => (
                  <Cell key={i} fill={STATUS_COLORS[s.status] || PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => fmtBRL(Number(v))} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="space-y-1.5 mt-2">
            {items.map(s => (
              <li key={s.status} className="flex items-center justify-between text-[12px]">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: STATUS_COLORS[s.status] || '#999' }} />
                  <span className="text-neutral-700 truncate">{s.label_pt}</span>
                </div>
                <div className="text-right shrink-0">
                  <span className="font-semibold tabular-nums text-neutral-900">{fmtBRL(s.total, true)}</span>
                  <span className="text-[10px] text-neutral-500 ml-1.5">{fmtNum(s.qtd)}</span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

// ── Categorias ranking ────────────────────────────────────────

function CategoriasRankingCard({
  items, title, subtitle, icon, colorBar,
}: {
  items: CategoriaItem[]
  title: string
  subtitle: string
  icon: React.ReactNode
  colorBar: string
}) {
  const max = Math.max(...items.map(i => i.total), 1)
  const total = items.reduce((s, i) => s + i.total, 0)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        {icon}
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          {title}
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">{subtitle} · {fmtBRL(total, true)} total</div>
      {items.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem movimentações no período.</div>
      ) : (
        <ul className="space-y-2.5">
          {items.map((c, i) => {
            const widthPct = (c.total / max) * 100
            return (
              <li key={`${c.external_id ?? c.nome}-${i}`}>
                <div className="flex items-center gap-2 mb-1">
                  <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                    i === 0 ? 'bg-amber-100 text-amber-700' :
                    i === 1 ? 'bg-neutral-100 text-neutral-600' :
                    i === 2 ? 'bg-orange-100 text-orange-700' :
                    'bg-neutral-50 text-neutral-500'
                  }`}>{i + 1}</span>
                  <span className="text-[12px] font-medium text-neutral-800 truncate flex-1" title={c.nome}>
                    {c.nome}
                  </span>
                  <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                    {fmtBRL(c.total, true)}
                  </span>
                </div>
                <div className="ml-7 flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${i === 0 ? 'bg-amber-500' : colorBar}`} style={{ width: `${widthPct}%` }} />
                  </div>
                  <span className="text-[10px] text-neutral-500 w-10 text-right">{c.pct.toFixed(0)}%</span>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

// ── Centros de custo ──────────────────────────────────────────

function CentrosCustoCard({ items }: { items: CentroCustoItem[] }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Building2 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Centros de custo — entradas e saídas por unidade
        </span>
      </div>
      {items.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem movimentações no período.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead className="border-b border-neutral-100">
              <tr className="text-[10px] uppercase tracking-wider text-neutral-500">
                <th className="px-2 py-2 text-left font-bold">Centro de custo</th>
                <th className="px-2 py-2 text-right font-bold">Entradas</th>
                <th className="px-2 py-2 text-right font-bold">Saídas</th>
                <th className="px-2 py-2 text-right font-bold">Saldo</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {items.map((cc, i) => (
                <tr key={`${cc.external_id ?? cc.nome}-${i}`}>
                  <td className="px-2 py-2 font-medium text-neutral-800 truncate">{cc.nome}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-emerald-700">{fmtBRL(cc.entradas, true)}</td>
                  <td className="px-2 py-2 text-right tabular-nums text-rose-700">{fmtBRL(cc.saidas, true)}</td>
                  <td className={`px-2 py-2 text-right tabular-nums font-semibold ${cc.saldo >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {cc.saldo >= 0 ? '+' : ''}{fmtBRL(cc.saldo, true)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Insight pra SonIA ─────────────────────────────────────────

function buildFluxoCaixaInsight(data: FinanceiroOverviewResponse): SonIAInsight {
  const k = data.kpis
  const kPrev = data.kpis_previous

  // Mês em andamento: suprimir MoM (enganoso) e projetar no ritmo atual.
  // Alertas absolutos (saldo negativo, inadimplência alta) continuam válidos
  // porque não dependem de comparação.
  const progress = isCurrentMonthPartial(data.period.year, data.period.month)
  if (progress.partial) {
    const factor = progress.totalDays / progress.days
    const projEntradas = k.entradas * factor
    const projSaidas = k.saidas * factor
    const projSaldo = projEntradas - projSaidas

    const inadAlta = k.inadimplencia_pct >= 8
    const moodPartial: SonIAInsight['mood'] = inadAlta ? 'alert' : 'curious'

    return {
      mood: moodPartial,
      headline: inadAlta
        ? 'Olhei aqui e queria te mostrar uma coisa.'
        : `Olhei o caixa de ${data.period.label} até agora.`,
      detail: inadAlta
        ? `Estamos no dia ${progress.days} de ${progress.totalDays} (${progress.progressPct.toFixed(0)}% do mês). A inadimplência está em ${k.inadimplencia_pct.toFixed(1)}% — ${fmtNum(k.qtd_parcelas_vencidas)} parcelas vencidas. Que tal acionarmos a régua de cobrança com carinho?`
        : `Estamos no dia ${progress.days} de ${progress.totalDays} (${progress.progressPct.toFixed(0)}% do mês). Até agora entraram ${fmtBRL(k.entradas, true)} e saíram ${fmtBRL(k.saidas, true)}. No ritmo atual, o mês deve fechar em ${fmtBRL(projSaldo, true)}.`,
      bullets: [
        { text: `Entradas ${fmtBRL(k.entradas, true)} · projeção ${fmtBRL(projEntradas, true)}.`, tone: 'neutral' },
        { text: `Saídas ${fmtBRL(k.saidas, true)} · projeção ${fmtBRL(projSaidas, true)}.`, tone: 'neutral' },
        { text: `Saldo parcial ${fmtBRL(k.saldo_liquido, true)} · projeção ${fmtBRL(projSaldo, true)}.`, tone: projSaldo < 0 ? 'warning' : 'neutral' },
        { text: `Inadimplência ${k.inadimplencia_pct.toFixed(1)}% (${fmtNum(k.qtd_parcelas_vencidas)} parcelas).`, tone: inadAlta ? 'negative' : k.inadimplencia_pct >= 4 ? 'warning' : 'neutral' },
        { text: `A receber ${fmtBRL(k.a_receber, true)} · A pagar ${fmtBRL(k.a_pagar, true)}.`, tone: 'neutral' },
      ],
    }
  }

  const saldoMoMPct = kPrev.saldo_liquido !== 0
    ? ((k.saldo_liquido - kPrev.saldo_liquido) / Math.abs(kPrev.saldo_liquido)) * 100
    : null
  const entradasMoMPct = kPrev.entradas > 0
    ? ((k.entradas - kPrev.entradas) / kPrev.entradas) * 100
    : null

  const saldoNeg = k.saldo_liquido < 0
  const inadAlta = k.inadimplencia_pct >= 8
  const vencidasMuitas = k.qtd_parcelas_vencidas >= 30

  const moodAlert = saldoNeg || inadAlta || vencidasMuitas
  const moodHappy = !moodAlert && saldoMoMPct !== null && saldoMoMPct >= 10

  const mood: SonIAInsight['mood'] = moodAlert ? 'alert' : moodHappy ? 'happy' : 'curious'

  const headline = saldoNeg
    ? 'Olhei aqui e queria conversar com você.'
    : inadAlta
    ? 'Tem uma coisa que me chamou atenção.'
    : moodHappy
    ? 'Olha que notícia boa.'
    : 'Olhei o caixa com calma.'

  const detail = saldoNeg
    ? `O saldo de ${data.period.label} fechou em ${fmtBRL(k.saldo_liquido, true)}, abaixo do que entrou. Vale revisar o que pode ser ajustado.`
    : inadAlta
    ? `A inadimplência está em ${k.inadimplencia_pct.toFixed(1)}% — ${fmtNum(k.qtd_parcelas_vencidas)} parcelas vencidas. Que tal acionarmos a régua de cobrança com carinho?`
    : moodHappy
    ? `O caixa de ${data.period.label} fechou em ${fmtBRL(k.saldo_liquido, true)}, com alta de ${saldoMoMPct!.toFixed(1)}% sobre o mês anterior. Bonito de ver.`
    : `Entradas de ${fmtBRL(k.entradas, true)}, saídas de ${fmtBRL(k.saidas, true)}. Saldo do mês: ${fmtBRL(k.saldo_liquido, true)}.`

  const bullets: SonIAInsight['bullets'] = [
    { text: `Entradas ${fmtBRL(k.entradas, true)}${pctSuffix(entradasMoMPct)}.`, tone: tonePct(entradasMoMPct, false) },
    { text: `Saídas ${fmtBRL(k.saidas, true)}.`, tone: 'neutral' },
    { text: `Saldo ${fmtBRL(k.saldo_liquido, true)}${pctSuffix(saldoMoMPct)}.`, tone: saldoNeg ? 'negative' : tonePct(saldoMoMPct, false) },
    { text: `Inadimplência ${k.inadimplencia_pct.toFixed(1)}% (${fmtNum(k.qtd_parcelas_vencidas)} parcelas).`, tone: inadAlta ? 'negative' : k.inadimplencia_pct >= 4 ? 'warning' : 'neutral' },
    { text: `A receber ${fmtBRL(k.a_receber, true)} · A pagar ${fmtBRL(k.a_pagar, true)}.`, tone: 'neutral' },
  ]

  return { mood, headline, detail, bullets }
}

function pctSuffix(p: number | null): string {
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
