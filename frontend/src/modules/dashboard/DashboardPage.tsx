import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import KpiDrillDown from './KpiDrillDown'
import {
  Bar,
  BarChart,
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
  ArrowUpRight,
  Award,
  BarChart3,
  CalendarCheck,
  CalendarX,
  Gem,
  LayoutGrid,
  Medal,
  Receipt,
  RotateCcw,
  Target,
  TrendingUp,
  Trophy,
  UserMinus,
  UserPlus,
  Users,
  Wallet,
} from 'lucide-react'

import { dashboardService } from '@/services/dashboard.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import type {
  ChurnBucket,
  CurvaAbcItem,
  DashboardExecutivoResponse,
  KpiId,
  KpiValue,
  MixPagamentoItem,
} from '@/types/dashboard'

// ── helpers ───────────────────────────────────────────────────

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000) {
    if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
    return `R$ ${(n / 1_000).toFixed(0)}k`
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(n)
}

const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtPct = (n: number | null) =>
  n == null ? '—' : `${n >= 0 ? '+' : ''}${n.toFixed(1)}%`

const MONTHS_PT = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

const ABC_COLORS: Record<string, string> = { A: '#1D4ED8', B: '#60A5FA', C: '#BFDBFE' }
const CHURN_COLORS: Record<string, string> = {
  ativo: '#1A8917',
  em_risco: '#D97706',
  inativo: '#9CA3AF',
  perdido: '#DC2626',
  sem_visita: '#E5E5E5',
}
const PIE_COLORS = ['#1D4ED8', '#3B82F6', '#60A5FA', '#93C5FD', '#BFDBFE', '#DBEAFE', '#94A3B8']

// ── página ────────────────────────────────────────────────────

export default function DashboardPage() {
  const today = new Date()
  const [year, setYear] = useState<number>(today.getFullYear())
  const [month, setMonth] = useState<number>(today.getMonth() + 1)

  const yearOptions = useMemo(() => {
    const start = 2019
    const end = today.getFullYear()
    return Array.from({ length: end - start + 1 }, (_, i) => end - i)
  }, [today])

  const [drillKpi, setDrillKpi] = useState<KpiId | null>(null)

  const dashQ = useQuery({
    queryKey: ['dashboard', 'executivo', year, month],
    queryFn: () => dashboardService.executivo(year, month),
    staleTime: 60_000,
  })

  const periodLabel = `${MONTHS_PT[month - 1]} de ${year}`
  usePageTitle('Painel Executivo', `Indicadores estratégicos de ${periodLabel}`, 'ANÁLISE')

  return (
    <main className="relative">
      {/* Pattern decorativo sutil de fundo */}
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
        {dashQ.isLoading && (
          <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
            Carregando…
          </div>
        )}

        {dashQ.isError && (
          <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
            Erro ao carregar o dashboard. Verifique se o pipeline analytics foi reconstruído.
          </div>
        )}

        {dashQ.data && <DashboardContent data={dashQ.data} onDrillDown={setDrillKpi} />}
      </div>
      {drillKpi && (
        <KpiDrillDown
          kpiId={drillKpi}
          year={year}
          month={month}
          onClose={() => setDrillKpi(null)}
        />
      )}
    </main>
  )
}

// ── conteúdo ──────────────────────────────────────────────────

function DashboardContent({ data, onDrillDown }: { data: DashboardExecutivoResponse; onDrillDown: (kpi: KpiId) => void }) {
  const { kpis, funil, inadimplencia, mix_pagamento, top_profissionais, top_categorias_agenda,
          comparacao_yoy, pacientes, evolution, period } = data

  return (
    <>
      {/* ─── HERO: Faturamento gigante + Pipeline ───────────────── */}
      <section className="grid lg:grid-cols-3 gap-4">
        <FaturamentoHero
          value={kpis.faturamento.value}
          mom={kpis.faturamento.delta_pct}
          momPrev={kpis.faturamento.previous}
          yoy={comparacao_yoy.faturamento_yoy_pct}
          yoyPrev={comparacao_yoy.faturamento_yoy}
          period={period.label_pt}
          onDrillDown={() => onDrillDown('faturamento')}
        />
        <PipelineHero
          valor_pipeline={funil.valor_pipeline}
          abertos={funil.abertos}
          em_followup={funil.em_followup}
          taxa_conversao={funil.taxa_conversao_pct}
          ticket_aprovado={funil.aprovados ? funil.valor_aprovado / funil.aprovados : 0}
        />
        <InadimplenciaHero data={inadimplencia} />
      </section>

      {/* ─── KPI Grid ────────────────────────────────────────────── */}
      <section>
        <SectionTitle icon={<BarChart3 size={16} />} title="Indicadores principais" subtitle="Comparação vs mês anterior (MoM) — variações coloridas por direção" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          <KpiCard
            icon={<CalendarCheck size={18} />}
            iconColor="bg-info-bg text-info-text"
            label="Consultas"
            value={fmtNum(kpis.consultas.value)}
            kpi={kpis.consultas}
            type="num"
            yoy={comparacao_yoy.consultas_yoy_pct}
            yoyPrev={comparacao_yoy.consultas_yoy}
            yoyType="num"
            onDrillDown={() => onDrillDown('consultas')}
          />
          <KpiCard
            icon={<Target size={18} />}
            iconColor="bg-success-bg text-success-text"
            label="Conversão"
            value={`${kpis.conversao_pct.value.toFixed(1)}%`}
            kpi={kpis.conversao_pct}
            type="pct"
            onDrillDown={() => onDrillDown('conversao')}
          />
          <KpiCard
            icon={<CalendarX size={18} />}
            iconColor="bg-warning-bg text-warning-text"
            label="Absenteísmo"
            value={`${kpis.absenteismo_pct.value.toFixed(1)}%`}
            kpi={kpis.absenteismo_pct}
            type="pct"
            inverse
            onDrillDown={() => onDrillDown('absenteismo')}
          />
          <KpiCard
            icon={<Receipt size={18} />}
            iconColor="bg-primary-50 text-primary-700"
            label="Ticket médio"
            value={fmtBRL(kpis.ticket_medio.value)}
            kpi={kpis.ticket_medio}
            type="brl"
            onDrillDown={() => onDrillDown('ticket_medio')}
          />
          <KpiCard
            icon={<Users size={18} />}
            iconColor="bg-neutral-100 text-neutral-700"
            label="Pacientes ativos"
            value={fmtNum(kpis.pacientes_ativos.value)}
            kpi={kpis.pacientes_ativos}
            type="num"
            subtitle={`de ${fmtNum(pacientes.total_base)} na base`}
            onDrillDown={() => onDrillDown('pacientes_ativos')}
          />
        </div>
      </section>

      {/* ─── Receita & Pagamento ───────────────────────────────── */}
      <section className="space-y-3">
        <SectionTitle
          icon={<TrendingUp size={16} />}
          title="Receita & Pagamento"
          subtitle="Evolução de 12 meses, mix de formas de pagamento"
        />
        <div className="grid lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2">
            <CardHeader title="Evolução 12 meses" subtitle="Faturamento (R$) e consultas" icon={<TrendingUp size={16} />} />
            <div className="h-72 px-2">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={evolution} margin={{ top: 10, right: 24, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
                  <XAxis dataKey="label_pt" tick={{ fontSize: 11, fill: '#737373' }} />
                  <YAxis yAxisId="left" tickFormatter={(v) => fmtBRL(v, true)} tick={{ fontSize: 11, fill: '#737373' }} width={70} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11, fill: '#737373' }} width={50} />
                  <Tooltip
                    formatter={(v, name) => name === 'faturamento' ? [fmtBRL(Number(v)), 'Faturamento'] : [fmtNum(Number(v)), 'Consultas']}
                    contentStyle={{ fontSize: 12, borderRadius: 6 }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar yAxisId="left" dataKey="faturamento" fill="#1D4ED8" name="Faturamento" radius={[4, 4, 0, 0]} />
                  <Line yAxisId="right" type="monotone" dataKey="consultas" stroke="#D97706" strokeWidth={2.5} name="Consultas" dot={{ r: 3 }} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card>
            <CardHeader title="Mix de pagamento" subtitle={`Recebido em ${period.label_pt}`} icon={<Wallet size={16} />} />
            <MixPagamentoChart items={mix_pagamento} />
            <div className="border-t divide-y">
              {mix_pagamento.map((m, i) => (
                <div key={m.forma} className="px-4 py-2 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2 truncate">
                    <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                    <span className="text-neutral-700 truncate">{m.forma}</span>
                  </div>
                  <div className="text-right tabular-nums shrink-0 ml-2">
                    <span className="font-medium text-neutral-900">{fmtBRL(m.total, true)}</span>
                    <span className="text-xs text-neutral-500 ml-1.5">{m.pct.toFixed(0)}%</span>
                  </div>
                </div>
              ))}
              {mix_pagamento.length === 0 && (
                <div className="px-4 py-6 text-center text-neutral-400 text-xs">Sem pagamentos no período.</div>
              )}
            </div>
          </Card>
        </div>
      </section>

      {/* ─── Funil comercial ─────────────────────────────────────── */}
      <section className="space-y-3">
        <SectionTitle
          icon={<Target size={16} />}
          title="Funil Comercial"
          subtitle={`Orçamentos abertos em ${period.label_pt}`}
        />
        <Card>
          <div className="grid grid-cols-2 md:grid-cols-5 divide-x divide-neutral-200">
            <FunnelStep label="Orçados" qtd={funil.total_orcamentos} valor={funil.valor_total} variant="neutral" />
            <FunnelStep label="Aprovados" qtd={funil.aprovados} valor={funil.valor_aprovado} variant="success" pct={funil.total_orcamentos ? (funil.aprovados / funil.total_orcamentos) * 100 : 0} />
            <FunnelStep label="Em followup" qtd={funil.em_followup} valor={null} variant="warning" />
            <FunnelStep label="Abertos" qtd={funil.abertos} valor={null} variant="info" />
            <FunnelStep label="Recusados" qtd={funil.recusados} valor={funil.valor_perdido} variant="danger" />
          </div>
          <div className="px-5 py-4 border-t bg-gradient-to-r from-primary-50 to-white grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <FunnelMetric icon={<Wallet size={16} />} label="Pipeline em aberto" value={fmtBRL(funil.valor_pipeline)} sub={`${funil.abertos + funil.em_followup} orçamentos`} />
            <FunnelMetric icon={<Target size={16} />} label="Taxa de conversão" value={`${funil.taxa_conversao_pct.toFixed(1)}%`} sub="aprovados / orçados" />
            <FunnelMetric icon={<Receipt size={16} />} label="Ticket aprovado" value={fmtBRL(funil.aprovados ? funil.valor_aprovado / funil.aprovados : 0)} sub={`${fmtNum(funil.aprovados)} aprovações`} />
          </div>
        </Card>
      </section>

      {/* ─── Performance ────────────────────────────────────────── */}
      <section className="space-y-3">
        <SectionTitle
          icon={<Award size={16} />}
          title="Performance"
          subtitle="Top profissionais e categorias com mais consultas"
        />
        <div className="grid lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader title="Top 5 profissionais" subtitle="Por valor aprovado em orçamentos" icon={<Trophy size={16} />} />
            <ProfissionaisRanking items={top_profissionais} />
          </Card>
          <Card>
            <CardHeader title="Top 5 categorias de consulta" subtitle="Por volume e absenteísmo" icon={<LayoutGrid size={16} />} />
            <CategoriasRanking items={top_categorias_agenda} />
          </Card>
        </div>
      </section>

      {/* ─── Pacientes ───────────────────────────────────────────── */}
      <section className="space-y-3">
        <SectionTitle
          icon={<Users size={16} />}
          title="Pacientes"
          subtitle={`Análise estratégica · ${fmtNum(pacientes.total_base)} cadastrados na base`}
        />

        <div className="grid lg:grid-cols-2 gap-4">
          <Card>
            <CardHeader title="Curva ABC" subtitle="Pareto: ~20% dos pacientes geram ~80% da receita" icon={<BarChart3 size={16} />} />
            <CurvaAbcChart items={pacientes.curva_abc} />
            <div className="grid grid-cols-3 divide-x border-t">
              {pacientes.curva_abc.map((c) => (
                <div key={c.classe} className="px-4 py-3 text-center">
                  <div className="text-xs uppercase tracking-wide font-bold" style={{ color: ABC_COLORS[c.classe] }}>Classe {c.classe}</div>
                  <div className="text-xl font-bold text-neutral-900 mt-1 tabular-nums">{fmtNum(c.qtd_pacientes)}</div>
                  <div className="text-[11px] text-neutral-500">{c.pct_pacientes.toFixed(1)}% pacientes</div>
                  <div className="text-sm text-neutral-700 mt-1 tabular-nums font-medium">{fmtBRL(c.faturamento, true)}</div>
                  <div className="text-[11px] text-neutral-500">{c.pct_faturamento.toFixed(1)}% receita</div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Risco de evasão (churn)" subtitle="Distribuição por dias desde última visita" icon={<UserMinus size={16} />} />
            <ChurnChart items={pacientes.churn_buckets} />
            <div className="border-t divide-y">
              {pacientes.churn_buckets.map((b) => (
                <div key={b.bucket} className="px-4 py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <span className="w-3 h-3 rounded-full shrink-0" style={{ background: CHURN_COLORS[b.bucket] || '#999' }} />
                    <span className="text-sm text-neutral-800">{b.label_pt}</span>
                  </div>
                  <div className="text-sm tabular-nums">
                    <span className="font-semibold text-neutral-900">{fmtNum(b.qtd)}</span>
                    <span className="text-xs text-neutral-500 ml-2">{b.pct.toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="grid lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2">
            <CardHeader title="Top 10 pacientes por LTV" subtitle="Lifetime value · soma de pagamentos recebidos" icon={<Gem size={16} />} />
            <LtvList items={pacientes.top_ltv} />
          </Card>
          <Card>
            <CardHeader title="Novos × Recorrentes" subtitle={`Atendidos em ${period.label_pt}`} icon={<UserPlus size={16} />} />
            <div className="px-5 py-4 relative overflow-hidden">
              {/* Ilustração: avatares estilizados sobrepostos */}
              <svg className="absolute right-2 top-2 opacity-15" width="120" height="80" viewBox="0 0 120 80" fill="none">
                <circle cx="35" cy="40" r="18" fill="#1D4ED8" />
                <circle cx="35" cy="32" r="6" fill="white" />
                <path d="M22 50 Q35 42 48 50 L48 56 L22 56 Z" fill="white" />
                <circle cx="65" cy="40" r="14" fill="#1A8917" />
                <circle cx="65" cy="34" r="5" fill="white" />
                <path d="M55 48 Q65 42 75 48 L75 53 L55 53 Z" fill="white" />
                <circle cx="90" cy="40" r="11" fill="#94A3B8" />
                <circle cx="90" cy="35" r="4" fill="white" />
                <path d="M82 47 Q90 42 98 47 L98 51 L82 51 Z" fill="white" />
              </svg>
              <div className="relative">
                <div className="text-2xl md:text-3xl font-bold text-neutral-900 tabular-nums">{fmtNum(pacientes.novos_recorrentes.total)}</div>
                <div className="text-xs text-neutral-500 mt-0.5">total de pacientes únicos</div>
                <div className="mt-5 space-y-3.5">
                  <SplitRow icon={<UserPlus size={14} />} label="Novos" value={pacientes.novos_recorrentes.novos} total={pacientes.novos_recorrentes.total} color="bg-primary-600" />
                  <SplitRow icon={<RotateCcw size={14} />} label="Recorrentes" value={pacientes.novos_recorrentes.recorrentes} total={pacientes.novos_recorrentes.total} color="bg-success-DEFAULT" />
                </div>
              </div>
            </div>
          </Card>
        </div>
      </section>
    </>
  )
}

// ── componentes auxiliares ────────────────────────────────────

function SectionTitle({ icon, title, subtitle }: { icon?: React.ReactNode; title: string; subtitle?: string }) {
  return (
    <div className="flex items-center gap-2.5">
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

function FaturamentoHero({ value, mom, momPrev, yoy, yoyPrev, period, onDrillDown }: {
  value: number; mom: number | null; momPrev: number | null; yoy: number | null; yoyPrev: number | null; period: string
  onDrillDown?: () => void
}) {
  const clickable = !!onDrillDown
  const Tag: React.ElementType = clickable ? 'button' : 'div'
  return (
    <Tag
      type={clickable ? 'button' : undefined}
      onClick={onDrillDown}
      className={`bg-gradient-to-br from-primary-700 to-primary-900 text-white rounded-xl p-4 shadow-lg relative overflow-hidden text-left w-full ${clickable ? 'cursor-pointer hover:shadow-2xl hover:from-primary-600 hover:to-primary-800 focus:outline-none focus:ring-2 focus:ring-primary-300 group transition-all' : ''}`}
    >
      {clickable && (
        <ArrowUpRight
          size={16}
          className="absolute top-3 right-3 text-white/40 group-hover:text-white transition-colors"
          aria-hidden
        />
      )}
      <div className="absolute -right-6 -top-6 w-20 h-20 bg-white/10 rounded-full" />
      <div className="absolute -right-10 top-10 w-24 h-24 bg-white/5 rounded-full" />
      {/* Ilustração: gráfico crescente estilizado */}
      <svg className="absolute right-3 bottom-3 opacity-20" width="80" height="50" viewBox="0 0 80 50" fill="none">
        <path d="M2 45 L18 32 L34 38 L50 18 L66 22 L78 5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <circle cx="18" cy="32" r="2.5" fill="white" />
        <circle cx="34" cy="38" r="2.5" fill="white" />
        <circle cx="50" cy="18" r="2.5" fill="white" />
        <circle cx="66" cy="22" r="2.5" fill="white" />
        <circle cx="78" cy="5" r="3" fill="white" />
      </svg>
      <div className="relative">
        <div className="flex items-center gap-2 text-primary-100 text-[11px] font-semibold uppercase tracking-wide">
          <span className="w-7 h-7 rounded-lg bg-white/15 flex items-center justify-center"><TrendingUp size={14} /></span>
          Faturamento
        </div>
        <div className="text-[11px] text-primary-200 mt-1">{period}</div>
        <div className="text-2xl md:text-3xl font-bold tabular-nums mt-1.5">{fmtBRL(value)}</div>
        <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
          <DeltaPill label="MoM" value={mom} prev={momPrev != null ? fmtBRL(momPrev, true) : null} dark />
          <DeltaPill label="YoY" value={yoy} prev={yoyPrev != null ? fmtBRL(yoyPrev, true) : null} dark />
        </div>
      </div>
    </Tag>
  )
}

function PipelineHero({ valor_pipeline, abertos, em_followup, taxa_conversao, ticket_aprovado }: {
  valor_pipeline: number; abertos: number; em_followup: number; taxa_conversao: number; ticket_aprovado: number
}) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-md relative overflow-hidden">
      {/* Decoração: bolhas suaves no canto */}
      <div className="absolute -right-4 -top-4 w-16 h-16 bg-warning-bg rounded-full opacity-50" />
      <div className="absolute right-6 top-6 w-10 h-10 bg-warning-bg rounded-full opacity-30" />
      <div className="relative">
        <div className="flex items-center gap-2 text-neutral-600 text-[11px] font-semibold uppercase tracking-wide">
          <span className="w-7 h-7 rounded-lg bg-warning-bg text-warning-text flex items-center justify-center"><Wallet size={14} /></span>
          Pipeline em aberto
        </div>
        <div className="text-[11px] text-neutral-400 mt-1">orçamentos a receber</div>
        <div className="text-2xl md:text-3xl font-bold tabular-nums mt-1.5 text-neutral-900">{fmtBRL(valor_pipeline)}</div>
        <div className="mt-2.5 grid grid-cols-2 gap-2">
          <div className="bg-neutral-50 rounded-lg px-2.5 py-1.5">
            <div className="text-[10px] uppercase text-neutral-500 font-medium">Abertos</div>
            <div className="text-sm font-bold tabular-nums text-neutral-900">{abertos}</div>
          </div>
          <div className="bg-neutral-50 rounded-lg px-2.5 py-1.5">
            <div className="text-[10px] uppercase text-neutral-500 font-medium">Followup</div>
            <div className="text-sm font-bold tabular-nums text-neutral-900">{em_followup}</div>
          </div>
        </div>
        <div className="mt-2.5 flex justify-between text-[11px] text-neutral-500 pt-2 border-t border-neutral-100">
          <span>Conversão <strong className="text-neutral-900">{taxa_conversao.toFixed(1)}%</strong></span>
          <span>Ticket <strong className="text-neutral-900">{fmtBRL(ticket_aprovado, true)}</strong></span>
        </div>
      </div>
    </div>
  )
}

function InadimplenciaHero({ data }: { data: { recebido: number; a_receber: number; total_emitido: number; inadimplencia_pct: number } }) {
  const isHigh = data.inadimplencia_pct > 10
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-md relative overflow-hidden">
      <div className={`absolute -right-4 -top-4 w-16 h-16 rounded-full opacity-40 ${isHigh ? 'bg-error-bg' : 'bg-success-bg'}`} />
      <div className={`absolute right-6 top-6 w-10 h-10 rounded-full opacity-25 ${isHigh ? 'bg-error-bg' : 'bg-success-bg'}`} />
      <div className="relative">
        <div className="flex items-center gap-2 text-neutral-600 text-[11px] font-semibold uppercase tracking-wide">
          <span className={`w-7 h-7 rounded-lg flex items-center justify-center ${isHigh ? 'bg-error-bg text-error-text' : 'bg-success-bg text-success-text'}`}>
            <AlertTriangle size={14} />
          </span>
          Inadimplência
        </div>
        <div className="text-[11px] text-neutral-400 mt-1">a receber sobre total emitido</div>
        <div className={`text-2xl md:text-3xl font-bold tabular-nums mt-1.5 ${isHigh ? 'text-error-text' : 'text-neutral-900'}`}>
          {data.inadimplencia_pct.toFixed(1)}%
        </div>
        <div className="mt-2.5 space-y-1.5">
          <BarRow label="Recebido" value={data.recebido} total={data.total_emitido} color="bg-success-DEFAULT" />
          <BarRow label="A receber" value={data.a_receber} total={data.total_emitido} color="bg-warning-DEFAULT" />
        </div>
        <div className="mt-2.5 pt-2 border-t border-neutral-100 text-[11px] text-neutral-500 flex justify-between">
          <span>Total emitido</span>
          <span className="tabular-nums font-semibold text-neutral-900">{fmtBRL(data.total_emitido)}</span>
        </div>
      </div>
    </div>
  )
}

// ── KPI Card ──────────────────────────────────────────────────

function KpiCard({ icon, iconColor, label, value, kpi, type, inverse, subtitle, yoy, yoyPrev, yoyType, onDrillDown }: {
  icon: React.ReactNode; iconColor: string; label: string; value: string; kpi: KpiValue; type: 'brl' | 'num' | 'pct';
  inverse?: boolean; subtitle?: string;
  yoy?: number | null; yoyPrev?: number | null; yoyType?: 'brl' | 'num';
  onDrillDown?: () => void
}) {
  const prevLabel = kpi.previous == null ? null
    : type === 'brl' ? fmtBRL(kpi.previous, true)
    : type === 'pct' ? `${kpi.previous.toFixed(1)}%`
    : fmtNum(kpi.previous)

  const yoyPrevLabel = yoyPrev == null ? null
    : yoyType === 'brl' ? fmtBRL(yoyPrev, true)
    : fmtNum(yoyPrev)

  const clickable = !!onDrillDown
  const baseCls = 'relative bg-white border border-neutral-200 rounded-xl p-4 shadow-md transition-shadow text-left w-full'
  const interactCls = clickable
    ? 'hover:shadow-lg hover:border-primary-300 cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary-300 group'
    : 'hover:shadow-lg'
  const Tag: React.ElementType = clickable ? 'button' : 'div'

  return (
    <Tag
      type={clickable ? 'button' : undefined}
      onClick={onDrillDown}
      className={`${baseCls} ${interactCls}`}
    >
      {clickable && (
        <ArrowUpRight
          size={14}
          className="absolute top-2.5 right-2.5 text-neutral-300 group-hover:text-primary-600 transition-colors"
          aria-hidden
        />
      )}
      <div className="flex items-start justify-between gap-2">
        <span className={`w-9 h-9 rounded-lg ${iconColor} flex items-center justify-center shrink-0`}>{icon}</span>
      </div>
      <div className="text-[11px] uppercase tracking-wide text-neutral-500 font-semibold mt-3">{label}</div>
      <div className="text-2xl font-bold text-neutral-900 tabular-nums mt-1">{value}</div>
      <div className="mt-2 space-y-1">
        <DeltaLine label="MoM" pct={kpi.delta_pct} prevLabel={prevLabel} inverse={inverse} />
        {yoy !== undefined && <DeltaLine label="YoY" pct={yoy} prevLabel={yoyPrevLabel} inverse={inverse} />}
      </div>
      {subtitle && <div className="text-[11px] text-neutral-400 mt-1.5">{subtitle}</div>}
    </Tag>
  )
}

function DeltaLine({ label, pct, prevLabel, inverse }: {
  label: string; pct: number | null | undefined; prevLabel: string | null; inverse?: boolean
}) {
  if (pct == null) {
    return (
      <div className="text-[11px] text-neutral-400 flex items-center gap-1">
        <span className="font-bold text-[10px] text-neutral-500 uppercase">{label}</span>
        <span>—</span>
      </div>
    )
  }
  const goodDirection = inverse ? pct < 0 : pct >= 0
  const colorClass = goodDirection ? 'text-success-text' : 'text-error-text'
  return (
    <div className={`text-[11px] flex items-center gap-1 ${colorClass} font-medium`}>
      <span className="font-bold text-[10px] text-neutral-500 uppercase">{label}</span>
      <span>{pct >= 0 ? '▲' : '▼'}</span>
      <span>{fmtPct(pct)}</span>
      {prevLabel && <span className="text-neutral-400 font-normal">vs {prevLabel}</span>}
    </div>
  )
}

function DeltaPill({ label, value, prev, dark }: { label: string; value: number | null; prev: string | null; dark?: boolean }) {
  if (value == null) {
    return (
      <span className={`text-[11px] px-2 py-0.5 rounded-full ${dark ? 'bg-white/10 text-white/70' : 'bg-neutral-100 text-neutral-500'}`}>
        {label} —
      </span>
    )
  }
  const isPositive = value >= 0
  const bg = dark
    ? (isPositive ? 'bg-white/20 text-white' : 'bg-error-DEFAULT/30 text-white')
    : (isPositive ? 'bg-success-bg text-success-text' : 'bg-error-bg text-error-text')
  return (
    <span className={`text-[11px] px-2 py-0.5 rounded-full font-semibold ${bg} flex items-center gap-1`}>
      <span className="text-[10px]">{isPositive ? '▲' : '▼'}</span>
      <span>{label}</span>
      <span>{fmtPct(value)}</span>
      {prev && <span className="font-normal opacity-80">vs {prev}</span>}
    </span>
  )
}

// ── Funnel ────────────────────────────────────────────────────

function FunnelStep({ label, qtd, valor, variant, pct }: {
  label: string; qtd: number; valor: number | null;
  variant: 'neutral' | 'success' | 'warning' | 'info' | 'danger'
  pct?: number
}) {
  const variantColors: Record<string, { text: string; bg: string }> = {
    neutral: { text: 'text-neutral-900', bg: 'bg-neutral-100 text-neutral-700' },
    success: { text: 'text-success-text', bg: 'bg-success-bg text-success-text' },
    warning: { text: 'text-warning-text', bg: 'bg-warning-bg text-warning-text' },
    info: { text: 'text-info-text', bg: 'bg-info-bg text-info-text' },
    danger: { text: 'text-error-text', bg: 'bg-error-bg text-error-text' },
  }
  const c = variantColors[variant]
  return (
    <div className="px-4 py-4">
      <div className={`inline-block px-2 py-0.5 text-[10px] uppercase rounded font-bold ${c.bg}`}>{label}</div>
      <div className={`text-2xl font-bold tabular-nums mt-2 ${c.text}`}>{fmtNum(qtd)}</div>
      {pct != null && <div className="text-[11px] text-neutral-400">{pct.toFixed(1)}% do total</div>}
      {valor != null && <div className="text-xs text-neutral-500 tabular-nums mt-0.5">{fmtBRL(valor, true)}</div>}
    </div>
  )
}

function FunnelMetric({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string; sub: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="w-9 h-9 rounded-lg bg-white text-primary-700 flex items-center justify-center border border-primary-100 shrink-0">{icon}</span>
      <div className="min-w-0">
        <div className="text-[11px] uppercase text-neutral-500 font-medium">{label}</div>
        <div className="text-base font-bold text-neutral-900 tabular-nums">{value}</div>
        <div className="text-[11px] text-neutral-400">{sub}</div>
      </div>
    </div>
  )
}

// ── Rankings ──────────────────────────────────────────────────

function MedalBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="w-7 h-7 rounded-full bg-yellow-100 text-yellow-700 flex items-center justify-center shrink-0"><Trophy size={14} /></span>
  if (rank === 2) return <span className="w-7 h-7 rounded-full bg-neutral-200 text-neutral-700 flex items-center justify-center shrink-0"><Medal size={14} /></span>
  if (rank === 3) return <span className="w-7 h-7 rounded-full bg-orange-100 text-orange-700 flex items-center justify-center shrink-0"><Award size={14} /></span>
  return <span className="w-7 h-7 rounded-full bg-neutral-50 border border-neutral-200 text-neutral-500 flex items-center justify-center text-xs font-semibold shrink-0">{rank}</span>
}

function ProfissionaisRanking({ items }: { items: { external_id: number; name: string | null; aprovados: number; orcamentos: number; valor_aprovado: number; taxa_conversao_pct: number }[] }) {
  const max = Math.max(...items.map(i => i.valor_aprovado), 1)
  if (items.length === 0) {
    return <div className="px-5 py-8 text-center text-xs text-neutral-400">Sem orçamentos no período.</div>
  }
  return (
    <div className="divide-y">
      {items.map((p, i) => {
        const widthPct = (p.valor_aprovado / max) * 100
        return (
          <div key={p.external_id} className="px-5 py-3 flex items-center gap-3">
            <MedalBadge rank={i + 1} />
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-sm font-medium text-neutral-900 truncate" title={p.name || ''}>
                  {p.name || `#${p.external_id}`}
                </span>
                <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">{fmtBRL(p.valor_aprovado, true)}</span>
              </div>
              <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                <div className="h-full bg-primary-600 rounded-full transition-all" style={{ width: `${widthPct}%` }} />
              </div>
              <div className="flex justify-between text-[11px] text-neutral-500 mt-1">
                <span>{p.aprovados}/{p.orcamentos} aprovados</span>
                <span>{p.taxa_conversao_pct.toFixed(0)}% conversão</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function CategoriasRanking({ items }: { items: { categoria: string; consultas: number; canceladas: number; absenteismo_pct: number }[] }) {
  const max = Math.max(...items.map(i => i.consultas), 1)
  if (items.length === 0) {
    return <div className="px-5 py-8 text-center text-xs text-neutral-400">Sem agendamentos no período.</div>
  }
  return (
    <div className="divide-y">
      {items.map((c, i) => {
        const widthPct = (c.consultas / max) * 100
        const absColor = c.absenteismo_pct > 15 ? 'text-error-text font-semibold'
          : c.absenteismo_pct > 8 ? 'text-warning-text'
          : 'text-success-text'
        return (
          <div key={c.categoria} className="px-5 py-3 flex items-center gap-3">
            <span className="w-7 h-7 rounded-full bg-neutral-50 border border-neutral-200 text-neutral-500 flex items-center justify-center text-xs font-semibold shrink-0">{i + 1}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-2 mb-1">
                <span className="text-sm font-medium text-neutral-900 truncate" title={c.categoria}>{c.categoria}</span>
                <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">{fmtNum(c.consultas)}</span>
              </div>
              <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                <div className="h-full bg-info-DEFAULT rounded-full transition-all" style={{ width: `${widthPct}%` }} />
              </div>
              <div className="flex justify-between text-[11px] text-neutral-500 mt-1">
                <span>{c.canceladas} canceladas</span>
                <span className={absColor}>{c.absenteismo_pct.toFixed(1)}% absenteísmo</span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function LtvList({ items }: { items: { external_id: number; name: string | null; ltv: number; total_payments: number }[] }) {
  if (items.length === 0) {
    return <div className="px-5 py-8 text-center text-xs text-neutral-400">Sem pagamentos registrados.</div>
  }
  const max = Math.max(...items.map(i => i.ltv), 1)
  return (
    <div className="divide-y">
      {items.map((p, i) => {
        const widthPct = (p.ltv / max) * 100
        return (
          <div key={p.external_id} className="px-5 py-2.5 flex items-center gap-3">
            <span className="w-6 text-right text-xs text-neutral-400 tabular-nums shrink-0">{i + 1}</span>
            <span className="w-7 h-7 rounded-full bg-primary-50 text-primary-700 flex items-center justify-center text-xs font-bold shrink-0">
              {(p.name || '?').charAt(0).toUpperCase()}
            </span>
            <div className="flex-1 min-w-0">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm text-neutral-800 truncate" title={p.name || ''}>{p.name || `#${p.external_id}`}</span>
                <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">{fmtBRL(p.ltv, true)}</span>
              </div>
              <div className="h-1 bg-neutral-100 rounded-full overflow-hidden mt-0.5">
                <div className="h-full bg-primary-600 rounded-full" style={{ width: `${widthPct}%` }} />
              </div>
              <div className="text-[11px] text-neutral-400 mt-0.5">{p.total_payments} pagamentos</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Bars ──────────────────────────────────────────────────────

function BarRow({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? (value / total) * 100 : 0
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-neutral-600">{label}</span>
        <span className="tabular-nums font-medium text-neutral-900">{fmtBRL(value, true)}</span>
      </div>
      <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function SplitRow({ icon, label, value, total, color }: {
  icon?: React.ReactNode; label: string; value: number; total: number; color: string
}) {
  const pct = total > 0 ? (value / total) * 100 : 0
  return (
    <div>
      <div className="flex justify-between items-center text-sm mb-1.5">
        <span className="text-neutral-700 flex items-center gap-1.5">
          {icon}
          {label}
        </span>
        <span className="tabular-nums">
          <span className="font-bold text-neutral-900">{fmtNum(value)}</span>
          <span className="text-xs text-neutral-500 ml-2">{pct.toFixed(0)}%</span>
        </span>
      </div>
      <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// ── Charts ────────────────────────────────────────────────────

function MixPagamentoChart({ items }: { items: MixPagamentoItem[] }) {
  if (items.length === 0) {
    return <div className="h-52 flex items-center justify-center text-xs text-neutral-400">Sem pagamentos no período.</div>
  }
  return (
    <div className="h-52">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={items} dataKey="total" nameKey="forma" cx="50%" cy="50%" innerRadius={45} outerRadius={80} paddingAngle={2}>
            {items.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
          </Pie>
          <Tooltip formatter={(v) => fmtBRL(Number(v))} contentStyle={{ fontSize: 12, borderRadius: 6 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function CurvaAbcChart({ items }: { items: CurvaAbcItem[] }) {
  if (items.length === 0) {
    return <div className="h-56 flex items-center justify-center text-xs text-neutral-400">Sem dados de receita ainda.</div>
  }
  const data = items.map(c => ({
    classe: `Classe ${c.classe}`,
    pacientes: c.pct_pacientes,
    receita: c.pct_faturamento,
  }))
  return (
    <div className="h-56 px-4">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 18, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E5E5" />
          <XAxis dataKey="classe" tick={{ fontSize: 11, fill: '#737373' }} />
          <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: '#737373' }} width={40} />
          <Tooltip formatter={(v) => `${Number(v).toFixed(1)}%`} contentStyle={{ fontSize: 12, borderRadius: 6 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="pacientes" name="% pacientes" fill="#93C5FD" radius={[4, 4, 0, 0]} />
          <Bar dataKey="receita" name="% receita" fill="#1D4ED8" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function ChurnChart({ items }: { items: ChurnBucket[] }) {
  const filtered = items.filter(b => b.qtd > 0)
  if (filtered.length === 0) {
    return <div className="h-56 flex items-center justify-center text-xs text-neutral-400">Sem pacientes na base.</div>
  }
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={filtered} dataKey="qtd" nameKey="label_pt" cx="50%" cy="50%" innerRadius={45} outerRadius={85} paddingAngle={2}>
            {filtered.map((b, i) => <Cell key={i} fill={CHURN_COLORS[b.bucket] || '#999'} />)}
          </Pie>
          <Tooltip formatter={(v) => fmtNum(Number(v))} contentStyle={{ fontSize: 12, borderRadius: 6 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
