import { useMemo, useState } from 'react'
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
  ArrowUpRight,
  Building2,
  HandCoins,
  PiggyBank,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'

import { financeiroService } from '@/services/financeiro.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import type {
  CategoriaItem,
  CentroCustoItem,
  FinanceiroOverviewResponse,
  StatusMixItem,
} from '@/types/financeiro'

// ── helpers ───────────────────────────────────────────────────

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000) {
    if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
    return `R$ ${(n / 1_000).toFixed(0)}k`
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
  }).format(n)
}
const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtPct = (n: number | null | undefined) =>
  n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`

const MONTHS_PT = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

const STATUS_COLORS: Record<string, string> = {
  pago: '#1A8917',
  em_aberto: '#D97706',
  vencido: '#DC2626',
}

const PIE_COLORS = ['#1D4ED8', '#3B82F6', '#60A5FA', '#93C5FD', '#BFDBFE', '#94A3B8']

const _delta = (curr: number, prev: number): number | null => {
  if (prev === 0) return null
  return ((curr - prev) / Math.abs(prev)) * 100
}

// ── página ────────────────────────────────────────────────────

export default function FinanceiroPage() {
  const today = new Date()
  const [year, setYear] = useState<number>(today.getFullYear())
  const [month, setMonth] = useState<number>(today.getMonth() + 1)

  const yearOptions = useMemo(() => {
    const start = 2019
    const end = today.getFullYear()
    return Array.from({ length: end - start + 1 }, (_, i) => end - i)
  }, [today])

  const q = useQuery({
    queryKey: ['financeiro', 'overview', year, month],
    queryFn: () => financeiroService.overview(year, month),
    staleTime: 60_000,
  })

  const periodLabel = `${MONTHS_PT[month - 1]} de ${year}`
  usePageTitle('Financeiro', `Fluxo de caixa de ${periodLabel}`, 'CONTA AZUL')

  return (
    <main className="relative">
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none opacity-[0.4]"
        style={{
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(29, 78, 216, 0.08) 1px, transparent 0)',
          backgroundSize: '32px 32px',
        }}
      />
      <div className="px-6 py-6 max-w-7xl mx-auto space-y-6 relative">
        <div className="flex items-center justify-end flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <select
              value={month}
              onChange={(e) => setMonth(parseInt(e.target.value, 10))}
              className="text-sm border rounded-lg px-3 py-2 bg-white shadow-sm hover:border-primary-400 cursor-pointer"
            >
              {MONTHS_PT.map((m, i) => (
                <option key={m} value={i + 1}>{m}</option>
              ))}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(parseInt(e.target.value, 10))}
              className="text-sm border rounded-lg px-3 py-2 bg-white shadow-sm hover:border-primary-400 cursor-pointer"
            >
              {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>

        {q.isLoading && (
          <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
            Carregando…
          </div>
        )}
        {q.isError && (
          <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
            Erro ao carregar financeiro. Verifique se o pipeline analytics CA foi reconstruído.
          </div>
        )}
        {q.data && <FinanceiroContent data={q.data} />}
      </div>
    </main>
  )
}

// ── conteúdo ──────────────────────────────────────────────────

function FinanceiroContent({ data }: { data: FinanceiroOverviewResponse }) {
  const { kpis, kpis_previous, top_receitas, top_despesas, centros_custo, status_mix, evolution, period } = data

  const entradasMoM = _delta(kpis.entradas, kpis_previous.entradas)
  const saidasMoM = _delta(kpis.saidas, kpis_previous.saidas)
  const saldoMoM = _delta(kpis.saldo_liquido, kpis_previous.saldo_liquido)

  return (
    <>
      {/* ─── HERO: Entradas, Saídas, Saldo ──────────────────── */}
      <section className="grid lg:grid-cols-3 gap-4">
        <EntradasHero value={kpis.entradas} mom={entradasMoM} momPrev={kpis_previous.entradas} period={period.label_pt} />
        <SaidasHero value={kpis.saidas} mom={saidasMoM} momPrev={kpis_previous.saidas} period={period.label_pt} />
        <SaldoHero value={kpis.saldo_liquido} mom={saldoMoM} momPrev={kpis_previous.saldo_liquido} period={period.label_pt} />
      </section>

      {/* ─── KPIs secundários ────────────────────────────────── */}
      <section>
        <SectionTitle icon={<Wallet size={16} />} title="A receber & a pagar" subtitle="Saldos abertos do período (não realizados ainda)" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard
            icon={<HandCoins size={18} />}
            iconColor="bg-success-bg text-success-text"
            label="A receber"
            value={fmtBRL(kpis.a_receber)}
            subtitle={`vs ${fmtBRL(kpis_previous.a_receber, true)} mês anterior`}
          />
          <KpiCard
            icon={<TrendingDown size={18} />}
            iconColor="bg-warning-bg text-warning-text"
            label="A pagar"
            value={fmtBRL(kpis.a_pagar)}
            subtitle={`vs ${fmtBRL(kpis_previous.a_pagar, true)} mês anterior`}
          />
          <KpiCard
            icon={<AlertTriangle size={18} />}
            iconColor="bg-error-bg text-error-text"
            label="Inadimplência"
            value={`${kpis.inadimplencia_pct.toFixed(1)}%`}
            subtitle={`${fmtNum(kpis.qtd_parcelas_vencidas)} parcelas vencidas`}
          />
          <KpiCard
            icon={<PiggyBank size={18} />}
            iconColor="bg-primary-50 text-primary-700"
            label="Saldo previsto"
            value={fmtBRL(kpis.saldo_liquido + kpis.a_receber - kpis.a_pagar)}
            subtitle="saldo + a receber - a pagar"
          />
        </div>
      </section>

      {/* ─── Evolução 12 meses ────────────────────────────────── */}
      <section className="space-y-3">
        <SectionTitle icon={<TrendingUp size={16} />} title="Evolução 12 meses" subtitle="Entradas vs saídas vs saldo" />
        <Card>
          <div className="h-80 px-2 pt-3">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={evolution} margin={{ top: 10, right: 24, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
                <XAxis dataKey="label_pt" tick={{ fontSize: 11, fill: '#737373' }} />
                <YAxis tickFormatter={(v) => fmtBRL(v, true)} tick={{ fontSize: 11, fill: '#737373' }} width={70} />
                <Tooltip
                  formatter={(v) => fmtBRL(Number(v))}
                  contentStyle={{ fontSize: 12, borderRadius: 6 }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="entradas" fill="#1A8917" name="Entradas" radius={[4, 4, 0, 0]} />
                <Bar dataKey="saidas" fill="#DC2626" name="Saídas" radius={[4, 4, 0, 0]} />
                <Line type="monotone" dataKey="saldo" stroke="#1D4ED8" strokeWidth={2.5} name="Saldo líquido" dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </section>

      {/* ─── Top categorias e Mix de status ────────────────────── */}
      <section className="space-y-3">
        <SectionTitle icon={<Wallet size={16} />} title="Categorias & Status" subtitle={`Movimentações realizadas em ${period.label_pt}`} />
        <div className="grid lg:grid-cols-3 gap-4">
          <Card>
            <CardHeader title="Top 5 receitas" subtitle="Maiores entradas por categoria" icon={<TrendingUp size={16} />} />
            <CategoriasRanking items={top_receitas} colorBar="bg-success-DEFAULT" />
          </Card>
          <Card>
            <CardHeader title="Top 5 despesas" subtitle="Maiores saídas por categoria" icon={<TrendingDown size={16} />} />
            <CategoriasRanking items={top_despesas} colorBar="bg-error-DEFAULT" />
          </Card>
          <Card>
            <CardHeader title="Status das parcelas" subtitle="Distribuição por situação" icon={<AlertTriangle size={16} />} />
            <StatusMixChart items={status_mix} />
            <div className="border-t divide-y">
              {status_mix.map((s) => (
                <div key={s.status} className="px-4 py-2 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: STATUS_COLORS[s.status] || '#999' }} />
                    <span className="text-neutral-700">{s.label_pt}</span>
                  </div>
                  <div className="text-right tabular-nums">
                    <span className="font-medium text-neutral-900">{fmtBRL(s.total, true)}</span>
                    <span className="text-xs text-neutral-500 ml-1.5">{fmtNum(s.qtd)}</span>
                  </div>
                </div>
              ))}
              {status_mix.length === 0 && (
                <div className="px-4 py-6 text-center text-neutral-400 text-xs">Sem parcelas no período.</div>
              )}
            </div>
          </Card>
        </div>
      </section>

      {/* ─── Centros de custo ─────────────────────────────────── */}
      <section className="space-y-3">
        <SectionTitle icon={<Building2 size={16} />} title="Centros de custo" subtitle="Entradas e saídas por unidade" />
        <Card>
          <CentrosCustoTable items={centros_custo} />
        </Card>
      </section>
    </>
  )
}

// ── componentes auxiliares ────────────────────────────────────

function SectionTitle({ icon, title, subtitle }: { icon?: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-2.5 mb-3">
      {icon && <span className="w-7 h-7 rounded-lg bg-primary-50 text-primary-700 flex items-center justify-center">{icon}</span>}
      <div>
        <h2 className="text-base font-bold text-neutral-900 leading-tight">{title}</h2>
        {subtitle && <p className="text-xs text-neutral-500">{subtitle}</p>}
      </div>
    </div>
  )
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`bg-white border border-neutral-200 rounded-xl overflow-hidden shadow-md hover:shadow-lg transition-shadow ${className}`}>{children}</div>
}

function CardHeader({ title, subtitle, icon }: { title: string; subtitle?: string; icon?: React.ReactNode }) {
  return (
    <div className="px-5 py-3 border-b border-neutral-200 flex items-center gap-2.5">
      {icon && <span className="w-7 h-7 rounded-lg bg-neutral-100 text-neutral-600 flex items-center justify-center shrink-0">{icon}</span>}
      <div className="min-w-0">
        <div className="text-sm font-semibold text-neutral-900 truncate">{title}</div>
        {subtitle && <div className="text-xs text-neutral-500 truncate">{subtitle}</div>}
      </div>
    </div>
  )
}

// ── Hero cards ────────────────────────────────────────────────

function EntradasHero({ value, mom, momPrev, period }: { value: number; mom: number | null; momPrev: number; period: string }) {
  return (
    <div className="bg-gradient-to-br from-green-600 to-green-800 text-white rounded-xl p-4 shadow-lg relative overflow-hidden">
      <div className="absolute -right-6 -top-6 w-20 h-20 bg-white/10 rounded-full" />
      <div className="absolute -right-10 top-10 w-24 h-24 bg-white/5 rounded-full" />
      <div className="relative">
        <div className="flex items-center gap-2 text-white/90 text-[11px] font-semibold uppercase tracking-wide">
          <span className="w-7 h-7 rounded-lg bg-white/15 flex items-center justify-center"><ArrowUpRight size={14} /></span>
          Entradas
        </div>
        <div className="text-[11px] text-white/70 mt-1">{period} · realizado</div>
        <div className="text-2xl md:text-3xl font-bold tabular-nums mt-1.5">{fmtBRL(value)}</div>
        <div className="mt-2.5">
          <DeltaPill label="MoM" value={mom} prev={fmtBRL(momPrev, true)} dark />
        </div>
      </div>
    </div>
  )
}

function SaidasHero({ value, mom, momPrev, period }: { value: number; mom: number | null; momPrev: number; period: string }) {
  return (
    <div className="bg-gradient-to-br from-red-700 to-red-900 text-white rounded-xl p-4 shadow-lg relative overflow-hidden">
      <div className="absolute -right-6 -top-6 w-20 h-20 bg-white/10 rounded-full" />
      <div className="absolute -right-10 top-10 w-24 h-24 bg-white/5 rounded-full" />
      <div className="relative">
        <div className="flex items-center gap-2 text-white/90 text-[11px] font-semibold uppercase tracking-wide">
          <span className="w-7 h-7 rounded-lg bg-white/15 flex items-center justify-center"><ArrowDownRight size={14} /></span>
          Saídas
        </div>
        <div className="text-[11px] text-white/70 mt-1">{period} · realizado</div>
        <div className="text-2xl md:text-3xl font-bold tabular-nums mt-1.5">{fmtBRL(value)}</div>
        <div className="mt-2.5">
          <DeltaPill label="MoM" value={mom} prev={fmtBRL(momPrev, true)} dark inverse />
        </div>
      </div>
    </div>
  )
}

function SaldoHero({ value, mom, momPrev, period }: { value: number; mom: number | null; momPrev: number; period: string }) {
  const positive = value >= 0
  return (
    <div className={`text-white rounded-xl p-4 shadow-lg relative overflow-hidden ${positive ? 'bg-gradient-to-br from-primary-700 to-primary-900' : 'bg-gradient-to-br from-red-600 to-red-900'}`}>
      <div className="absolute -right-6 -top-6 w-20 h-20 bg-white/10 rounded-full" />
      <div className="absolute -right-10 top-10 w-24 h-24 bg-white/5 rounded-full" />
      <div className="relative">
        <div className="flex items-center gap-2 text-white/90 text-[11px] font-semibold uppercase tracking-wide">
          <span className="w-7 h-7 rounded-lg bg-white/15 flex items-center justify-center"><Wallet size={14} /></span>
          Saldo líquido
        </div>
        <div className="text-[11px] text-white/70 mt-1">{period} · entradas - saídas</div>
        <div className="text-2xl md:text-3xl font-bold tabular-nums mt-1.5">
          {value >= 0 ? '+' : ''}{fmtBRL(value)}
        </div>
        <div className="mt-2.5">
          <DeltaPill label="MoM" value={mom} prev={fmtBRL(momPrev, true)} dark />
        </div>
      </div>
    </div>
  )
}

// ── KPI Card simples ──────────────────────────────────────────

function KpiCard({ icon, iconColor, label, value, subtitle }: {
  icon: React.ReactNode; iconColor: string; label: string; value: string; subtitle?: string
}) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-md hover:shadow-lg transition-shadow">
      <span className={`w-9 h-9 rounded-lg ${iconColor} flex items-center justify-center shrink-0`}>{icon}</span>
      <div className="text-[11px] uppercase tracking-wide text-neutral-500 font-semibold mt-3">{label}</div>
      <div className="text-2xl font-bold text-neutral-900 tabular-nums mt-1">{value}</div>
      {subtitle && <div className="text-[11px] text-neutral-400 mt-1.5">{subtitle}</div>}
    </div>
  )
}

function DeltaPill({ label, value, prev, dark, inverse }: { label: string; value: number | null; prev: string | null; dark?: boolean; inverse?: boolean }) {
  if (value == null) {
    return (
      <span className={`text-[11px] px-2 py-0.5 rounded-full ${dark ? 'bg-white/10 text-white/70' : 'bg-neutral-100 text-neutral-500'}`}>
        {label} —
      </span>
    )
  }
  const goodDirection = inverse ? value < 0 : value >= 0
  const bg = dark
    ? (goodDirection ? 'bg-white/20 text-white' : 'bg-error-DEFAULT/30 text-white')
    : (goodDirection ? 'bg-success-bg text-success-text' : 'bg-error-bg text-error-text')
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${bg} inline-flex items-center gap-1`}>
      <span className="text-[10px]">{value >= 0 ? '▲' : '▼'}</span>
      <span>{label}</span>
      <span>{fmtPct(value)}</span>
      {prev && <span className="font-normal opacity-80">vs {prev}</span>}
    </span>
  )
}

// ── Categorias ranking ────────────────────────────────────────

function CategoriasRanking({ items, colorBar }: { items: CategoriaItem[]; colorBar: string }) {
  if (items.length === 0) {
    return <div className="px-5 py-8 text-center text-xs text-neutral-400">Sem movimentações no período.</div>
  }
  const max = Math.max(...items.map(i => i.total), 1)
  return (
    <div className="divide-y">
      {items.map((c, i) => {
        const widthPct = (c.total / max) * 100
        return (
          <div key={`${c.external_id ?? c.nome}-${i}`} className="px-5 py-3">
            <div className="flex items-baseline justify-between gap-2 mb-1">
              <span className="text-sm font-medium text-neutral-900 truncate" title={c.nome}>{c.nome}</span>
              <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">{fmtBRL(c.total, true)}</span>
            </div>
            <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
              <div className={`h-full ${colorBar} rounded-full transition-all`} style={{ width: `${widthPct}%` }} />
            </div>
            <div className="flex justify-end text-[11px] text-neutral-500 mt-1">
              <span>{c.pct.toFixed(1)}% do total</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Status mix chart ──────────────────────────────────────────

function StatusMixChart({ items }: { items: StatusMixItem[] }) {
  if (items.length === 0) {
    return <div className="h-52 flex items-center justify-center text-xs text-neutral-400">Sem parcelas no período.</div>
  }
  return (
    <div className="h-52">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={items} dataKey="total" nameKey="label_pt" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={2}>
            {items.map((s, i) => (
              <Cell key={i} fill={STATUS_COLORS[s.status] || PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(v) => fmtBRL(Number(v))} contentStyle={{ fontSize: 12, borderRadius: 6 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Centros de custo table ────────────────────────────────────

function CentrosCustoTable({ items }: { items: CentroCustoItem[] }) {
  if (items.length === 0) {
    return <div className="px-5 py-8 text-center text-xs text-neutral-400">Sem movimentações no período.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-neutral-50 border-b">
          <tr className="text-[11px] uppercase tracking-wide text-neutral-500">
            <th className="px-5 py-2.5 text-left font-semibold">Centro de custo</th>
            <th className="px-4 py-2.5 text-right font-semibold">Entradas</th>
            <th className="px-4 py-2.5 text-right font-semibold">Saídas</th>
            <th className="px-5 py-2.5 text-right font-semibold">Saldo</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {items.map((cc, i) => (
            <tr key={`${cc.external_id ?? cc.nome}-${i}`} className="hover:bg-primary-50/30">
              <td className="px-5 py-2.5 font-medium text-neutral-900 truncate">{cc.nome}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-success-text">{fmtBRL(cc.entradas, true)}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-error-text">{fmtBRL(cc.saidas, true)}</td>
              <td className={`px-5 py-2.5 text-right tabular-nums font-semibold ${cc.saldo >= 0 ? 'text-success-text' : 'text-error-text'}`}>
                {cc.saldo >= 0 ? '+' : ''}{fmtBRL(cc.saldo, true)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
