/**
 * Dashboard de Pacientes (Sub-PR 20d).
 * Foco: RETENÇÃO + LTV — quem chamar, quem reter, quem agradecer.
 *
 * Estrutura:
 * 1. Header + PeriodSelector
 * 2. Banner mês parcial (quando aplicável)
 * 3. KPIs (4): ativos / recorrência / LTV / em risco
 * 4. Saúde da base (5 buckets)
 * 5. Curva ABC + Novos vs Recorrentes
 * 6. Evolution 12m (novos × recorrentes)
 * 7. Para Resgatar ⚡ (em risco/inativo com LTV alto)
 * 8. Top LTV (pacientes valor total)
 * 9. Novos do mês (com status orçamento)
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, BarChart3, CalendarClock, Clock, Crown, Flame, HeartPulse, Loader2, Phone,
  TrendingUp, UserPlus, Users,
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
  AnalisePacientesResponse, CurvaAbcItem, NovoPacienteMes, NovosRecorrentesSection,
  OrcamentoPendentePaciente, PacientesEvolutionPoint, ParaResgatarPaciente,
  SaudeBaseSection, TopLtvPaciente,
} from '@/types/analise'

import { KpiCardEnriched } from '../analise/components/KpiCardEnriched'
import { PeriodSelector } from '../analise/components/PeriodSelector'
import PacienteDetalheDrawer from './PacienteDetalheDrawer'
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
const fmtDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

// Mapeamento bucket → cor + label legível
const BUCKET_META: Record<string, { label: string; bg: string; text: string; bar: string }> = {
  ativo:      { label: 'Ativo',      bg: 'bg-emerald-50', text: 'text-emerald-700', bar: 'bg-emerald-500' },
  em_risco:   { label: 'Em risco',   bg: 'bg-amber-50',   text: 'text-amber-700',   bar: 'bg-amber-500' },
  inativo:    { label: 'Inativo',    bg: 'bg-orange-50',  text: 'text-orange-700',  bar: 'bg-orange-500' },
  perdido:    { label: 'Perdido',    bg: 'bg-rose-50',    text: 'text-rose-700',    bar: 'bg-rose-500' },
  sem_visita: { label: 'Sem visita', bg: 'bg-neutral-100', text: 'text-neutral-600', bar: 'bg-neutral-400' },
}

// ── Page ──────────────────────────────────────────────────────

export default function PacientesPage() {
  usePageTitle('Análise de Pacientes')

  const today = new Date()
  const [period, setPeriod] = useState({ year: today.getFullYear(), month: today.getMonth() + 1 })

  const query = useQuery({
    queryKey: ['analise', 'pacientes', period.year, period.month],
    queryFn: () => analiseService.pacientes(period.year, period.month),
    staleTime: 60_000,
  })

  const { publish, clear } = useSonIA()
  useEffect(() => {
    if (!query.data) return
    publish({
      pageKey: '/pacientes',
      pageTitle: 'Análise de Pacientes',
      data: { insight: buildPacientesInsight(query.data) },
    })
    return () => clear('/pacientes')
  }, [query.data, publish, clear])

  return (
    <PageContainer>
      <PageHeader
        eyebrow="ANÁLISE"
        title="Dashboard de Pacientes"
        subtitle="Retenção, LTV e oportunidades de resgate"
        icon={<Users size={20} />}
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
          <Loader2 className="animate-spin" size={18} /> Carregando análise de pacientes...
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

function Body({ data }: { data: AnalisePacientesResponse }) {
  const ativos = data.kpis.pacientes_ativos
  const [detalhePid, setDetalhePid] = useState<number | null>(null)
  return (
    <>
      {ativos.is_partial && ativos.partial_days && ativos.partial_days_in_month && (
        <PartialMonthBanner
          days={ativos.partial_days}
          daysInMonth={ativos.partial_days_in_month}
          progress={ativos.partial_progress ?? 0}
        />
      )}

      {/* KPIs principais — 4 cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCardEnriched
          data={data.kpis.pacientes_ativos}
          label="Pacientes ativos"
          icon={<HeartPulse size={14} className="text-emerald-700" />}
          iconBg="bg-emerald-50"
          emphasized
          helpTooltip={
            <div className="space-y-1.5">
              <div className="font-semibold">Quem é "ativo"?</div>
              <div className="text-neutral-300 leading-snug">
                Paciente com pelo menos 1 visita nos <strong>últimos 90 dias</strong>.
                Bate com o bucket "Ativo" da Saúde da Base.
              </div>
            </div>
          }
        />
        <KpiCardEnriched
          data={data.kpis.taxa_recorrencia_pct}
          label="Recorrência"
          icon={<TrendingUp size={14} className="text-blue-700" />}
          iconBg="bg-blue-50"
          helpTooltip={
            <div className="text-neutral-300 leading-snug">
              % dos pacientes atendidos no mês que <strong>já estavam na base</strong> antes.
              Inverso de "novos": alta recorrência indica fidelização forte.
            </div>
          }
        />
        <KpiCardEnriched
          data={data.kpis.ltv_medio}
          label="LTV médio"
          icon={<Crown size={14} className="text-amber-700" />}
          iconBg="bg-amber-50"
          helpTooltip={
            <div className="text-neutral-300 leading-snug">
              Soma de pagamentos recebidos por paciente, em média. Calculado sobre
              quem já gerou caixa (não inclui pacientes sem pagamento ainda).
            </div>
          }
        />
        <KpiCardEnriched
          data={data.kpis.em_risco_qty}
          label="Em risco"
          icon={<AlertTriangle size={14} className="text-rose-700" />}
          iconBg="bg-rose-50"
          helpTooltip={
            <div className="text-neutral-300 leading-snug">
              Pacientes que estão entre <strong>90 e 180 dias sem visita</strong>.
              Alvo prioritário de campanha — ainda dá pra resgatar antes de virar inativo.
            </div>
          }
        />
      </div>

      {/* Saúde da base */}
      <SaudeBaseCard data={data.saude_base} />

      {/* Curva ABC + Novos vs Recorrentes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <CurvaAbcCard data={data.curva_abc} />
        <NovosRecorrentesCard data={data.novos_recorrentes} />
      </div>

      {/* Evolution 12m */}
      <EvolutionChart data={data.evolution} />

      {/* Para Resgatar — diferencial estratégico */}
      <ParaResgatarCard data={data.para_resgatar} onPickPaciente={setDetalhePid} />

      {/* Orçamentos pendentes — oportunidade quente */}
      <OrcamentosPendentesCard data={data.orcamentos_pendentes} onPickPaciente={setDetalhePid} />

      {/* Top LTV + Novos do mês */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <TopLtvCard data={data.top_ltv} onPickPaciente={setDetalhePid} />
        <NovosDoMesCard data={data.novos_do_mes} onPickPaciente={setDetalhePid} />
      </div>

      {detalhePid !== null && (
        <PacienteDetalheDrawer
          patientExternalId={detalhePid}
          onClose={() => setDetalhePid(null)}
        />
      )}
    </>
  )
}

// ── Partial month banner ──────────────────────────────────────

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

// ── Saúde da base ─────────────────────────────────────────────

function SaudeBaseCard({ data }: { data: SaudeBaseSection }) {
  const segments = [
    { key: 'ativo',      qtd: data.ativo_qty,      pct: data.ativo_pct      },
    { key: 'em_risco',   qtd: data.em_risco_qty,   pct: data.em_risco_pct   },
    { key: 'inativo',    qtd: data.inativo_qty,    pct: data.inativo_pct    },
    { key: 'perdido',    qtd: data.perdido_qty,    pct: data.perdido_pct    },
    { key: 'sem_visita', qtd: data.sem_visita_qty, pct: data.sem_visita_pct },
  ].filter((s) => s.qtd > 0)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-4 flex items-start justify-between gap-4 flex-wrap border-b border-neutral-100">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Saúde da base
          </div>
          <div className="text-sm text-neutral-700 mt-0.5">
            <strong className="text-neutral-900">{fmtNum(data.total)}</strong> pacientes na base ·
            ativos <strong className="text-emerald-700 tabular-nums">{data.ativo_pct.toFixed(1)}%</strong>
          </div>
        </div>
        <div className="text-[10px] text-neutral-500 max-w-sm leading-snug">
          Buckets pela última visita: <strong>ativo</strong> &lt;90d ·
          {' '}<strong>em risco</strong> 90-180d · <strong>inativo</strong> 180-365d ·
          {' '}<strong>perdido</strong> &gt;365d.
        </div>
      </header>

      <div className="px-5 py-3">
        <div className="flex h-7 rounded-md overflow-hidden ring-1 ring-neutral-200">
          {segments.map((s) => {
            const meta = BUCKET_META[s.key]
            return (
              <div
                key={s.key}
                className={`${meta.bar} flex items-center justify-center text-[10.5px] font-bold text-white transition`}
                style={{ width: `${Math.max(s.pct, 2)}%` }}
                title={`${meta.label}: ${fmtNum(s.qtd)} (${s.pct.toFixed(1)}%)`}
              >
                {s.pct >= 8 ? `${s.pct.toFixed(0)}%` : ''}
              </div>
            )
          })}
        </div>
      </div>

      <div className="px-5 pb-4 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
        {segments.map((s) => {
          const meta = BUCKET_META[s.key]
          return (
            <div key={s.key} className={`${meta.bg} rounded-md px-3 py-2`}>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-6 rounded-sm ${meta.bar} shrink-0`} />
                <div className="min-w-0">
                  <div className={`text-[11px] font-semibold ${meta.text}`}>{meta.label}</div>
                  <div className="flex items-baseline gap-1.5">
                    <span className={`text-[14px] font-bold tabular-nums ${meta.text}`}>{fmtNum(s.qtd)}</span>
                    <span className="text-[10px] text-neutral-500 tabular-nums">{s.pct.toFixed(1)}%</span>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}

// ── Curva ABC ─────────────────────────────────────────────────

function CurvaAbcCard({ data }: { data: CurvaAbcItem[] }) {
  const totalPac = data.reduce((s, c) => s + c.qtd_pacientes, 0)
  const totalFat = data.reduce((s, c) => s + c.faturamento, 0)
  const COR: Record<string, { bar: string; bg: string; text: string }> = {
    A: { bar: 'bg-emerald-500', bg: 'bg-emerald-50', text: 'text-emerald-700' },
    B: { bar: 'bg-amber-500',   bg: 'bg-amber-50',   text: 'text-amber-700' },
    C: { bar: 'bg-neutral-400', bg: 'bg-neutral-100', text: 'text-neutral-600' },
  }
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Curva ABC — Pareto sobre LTV
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(totalPac)} pacientes · {fmtBRL(totalFat, true)} de LTV total
      </div>
      <div className="space-y-2.5">
        {data.map((c) => {
          const cor = COR[c.classe] || COR.C
          return (
            <div key={c.classe} className={`${cor.bg} rounded-md px-3 py-2`}>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-2">
                  <span className={`w-6 h-6 rounded-full ${cor.bar} text-white text-[11px] font-bold flex items-center justify-center`}>
                    {c.classe}
                  </span>
                  <span className={`text-[12px] font-semibold ${cor.text}`}>
                    {fmtNum(c.qtd_pacientes)} pacientes ({c.pct_pacientes.toFixed(1)}%)
                  </span>
                </div>
                <span className={`text-[13px] font-bold tabular-nums ${cor.text}`}>
                  {fmtBRL(c.faturamento, true)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-white rounded-full overflow-hidden">
                  <div className={`h-full ${cor.bar}`} style={{ width: `${c.pct_faturamento}%` }} />
                </div>
                <span className={`text-[10px] font-bold tabular-nums ${cor.text} w-12 text-right`}>
                  {c.pct_faturamento.toFixed(1)}%
                </span>
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-neutral-100 text-[10px] text-neutral-500 leading-snug">
        Classe <strong>A</strong> = 80% do faturamento · <strong>B</strong> = 15% · <strong>C</strong> = 5%.
        Concentre retenção em A; campanhas de upsell em B; volume em C.
      </div>
    </div>
  )
}

// ── Novos vs Recorrentes ──────────────────────────────────────

function NovosRecorrentesCard({ data }: { data: NovosRecorrentesSection }) {
  const novosPct = data.total > 0 ? (data.novos_qty / data.total) * 100 : 0
  const recPct = 100 - novosPct
  const novosTicketMaior = data.novos_ticket_medio > data.recorrentes_ticket_medio
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <UserPlus size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Novos vs Recorrentes
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(data.total)} pacientes únicos atendidos no mês
      </div>

      <div className="flex h-7 rounded-md overflow-hidden ring-1 ring-neutral-200 mb-3">
        <div
          className="bg-emerald-500 flex items-center justify-center text-[10.5px] font-bold text-white"
          style={{ width: `${Math.max(novosPct, 2)}%` }}
          title={`Novos: ${fmtNum(data.novos_qty)} (${novosPct.toFixed(1)}%)`}
        >
          {novosPct >= 12 ? `${novosPct.toFixed(0)}%` : ''}
        </div>
        <div
          className="bg-blue-500 flex items-center justify-center text-[10.5px] font-bold text-white"
          style={{ width: `${Math.max(recPct, 2)}%` }}
          title={`Recorrentes: ${fmtNum(data.recorrentes_qty)} (${recPct.toFixed(1)}%)`}
        >
          {recPct >= 12 ? `${recPct.toFixed(0)}%` : ''}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div className="bg-emerald-50 rounded-md px-3 py-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="text-[11px] font-semibold text-emerald-700">Novos</span>
          </div>
          <div className="text-[18px] font-bold text-emerald-700 tabular-nums">{fmtNum(data.novos_qty)}</div>
          <div className="text-[10px] text-neutral-600 mt-1">
            <div>R$ {fmtBRL(data.novos_amount_aprovado, true).replace('R$ ', '')} aprovados</div>
            <div>ticket {fmtBRL(data.novos_ticket_medio, true)}</div>
          </div>
        </div>
        <div className="bg-blue-50 rounded-md px-3 py-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="w-2 h-2 rounded-full bg-blue-500" />
            <span className="text-[11px] font-semibold text-blue-700">Recorrentes</span>
          </div>
          <div className="text-[18px] font-bold text-blue-700 tabular-nums">{fmtNum(data.recorrentes_qty)}</div>
          <div className="text-[10px] text-neutral-600 mt-1">
            <div>R$ {fmtBRL(data.recorrentes_amount_aprovado, true).replace('R$ ', '')} aprovados</div>
            <div>ticket {fmtBRL(data.recorrentes_ticket_medio, true)}</div>
          </div>
        </div>
      </div>

      {data.novos_ticket_medio > 0 && data.recorrentes_ticket_medio > 0 && (
        <div className="mt-3 pt-3 border-t border-neutral-100 flex items-center gap-2 text-[11px] text-neutral-600">
          {novosTicketMaior ? (
            <Flame size={13} className="text-amber-500 shrink-0" />
          ) : (
            <Activity size={13} className="text-blue-500 shrink-0" />
          )}
          <span>
            {novosTicketMaior ? (
              <>Novos chegam com ticket <strong className="text-emerald-700">
                {(data.novos_ticket_medio / data.recorrentes_ticket_medio).toFixed(1)}x maior
              </strong> que recorrentes — captação está atraindo casos grandes.</>
            ) : (
              <>Recorrentes têm ticket <strong className="text-blue-700">
                {(data.recorrentes_ticket_medio / data.novos_ticket_medio).toFixed(1)}x maior
              </strong> que novos — base existente sustenta o caixa.</>
            )}
          </span>
        </div>
      )}
    </div>
  )
}

// ── Evolution chart ───────────────────────────────────────────

function EvolutionChart({ data }: { data: PacientesEvolutionPoint[] }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Evolução — pacientes atendidos (12 meses)
        </span>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: -10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip
            contentStyle={{ fontSize: 11, borderRadius: 8 }}
            formatter={(v) => fmtNum(Number(v))}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar dataKey="recorrentes" stackId="pac" name="Recorrentes" fill="#3b82f6" />
          <Bar dataKey="novos" stackId="pac" name="Novos" fill="#10b981" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Para Resgatar — diferencial estratégico ───────────────────

function ParaResgatarCard({
  data, onPickPaciente,
}: { data: ParaResgatarPaciente[]; onPickPaciente: (pid: number) => void }) {
  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Phone size={14} className="text-rose-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Para Resgatar
          </span>
        </div>
        <div className="text-sm text-neutral-400 py-6 text-center">
          Nenhum paciente em risco com LTV alto no momento.
        </div>
      </div>
    )
  }
  return (
    <div className="bg-gradient-to-br from-rose-50 to-amber-50 border border-rose-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Phone size={14} className="text-rose-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-rose-700">
            Para Resgatar — top {data.length} por LTV
          </span>
        </div>
        <span className="text-[10px] text-rose-600 font-semibold uppercase tracking-wider">
          ⚡ ação imediata
        </span>
      </div>
      <div className="text-[11px] text-rose-700/80 mb-3 leading-snug">
        Pacientes em <strong>risco</strong> ou <strong>inativos</strong> com LTV alto — ligar antes de virar perdido.
      </div>
      <div className="bg-white rounded-md overflow-hidden">
        <table className="w-full text-[12px]">
          <thead className="bg-neutral-50 text-[10px] uppercase tracking-wider text-neutral-500">
            <tr>
              <th className="px-3 py-2 text-left">Paciente</th>
              <th className="px-3 py-2 text-right">LTV</th>
              <th className="px-3 py-2 text-center">Status</th>
              <th className="px-3 py-2 text-right">Sem visita</th>
              <th className="px-3 py-2 text-left">Telefone</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p, i) => {
              const meta = BUCKET_META[p.bucket]
              return (
                <tr key={p.external_id} className={i % 2 ? 'bg-neutral-50/50' : ''}>
                  <td className="px-3 py-2 truncate max-w-xs" title={p.name || ''}>
                    <button
                      type="button"
                      onClick={() => onPickPaciente(p.external_id)}
                      className="hover:underline text-left"
                    >
                      {p.name || `#${p.external_id}`}
                    </button>
                  </td>
                  <td className="px-3 py-2 text-right font-bold tabular-nums text-amber-700">
                    {fmtBRL(p.ltv, true)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.bg} ${meta.text}`}>
                      {meta.label}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums text-neutral-600">
                    {p.days_since_last_seen}d
                  </td>
                  <td className="px-3 py-2 text-neutral-600 tabular-nums">
                    {p.mobile_phone || <span className="text-neutral-400">—</span>}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Orçamentos pendentes — oportunidade quente ────────────────

function OrcamentosPendentesCard({
  data, onPickPaciente,
}: { data: OrcamentoPendentePaciente[]; onPickPaciente: (pid: number) => void }) {
  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Clock size={14} className="text-amber-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Orçamentos em decisão
          </span>
        </div>
        <div className="text-sm text-neutral-400 py-6 text-center">
          Nenhum orçamento pendente nos últimos 60 dias.
        </div>
      </div>
    )
  }
  const totalAmount = data.reduce((s, o) => s + o.amount, 0)
  return (
    <div className="bg-gradient-to-br from-amber-50 to-emerald-50 border border-amber-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <Clock size={14} className="text-amber-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-amber-700">
            Orçamentos em decisão — top {data.length}
          </span>
        </div>
        <span className="text-[10px] text-amber-700 font-semibold uppercase tracking-wider">
          ⚡ oportunidade quente
        </span>
      </div>
      <div className="text-[11px] text-amber-700/80 mb-3 leading-snug">
        Orçamentos pendentes (FOLLOWUP/OPEN) gerados nos <strong>últimos 60 dias</strong> ·
        soma do top mostrado: <strong className="text-amber-800 tabular-nums">{fmtBRL(totalAmount, true)}</strong>
      </div>
      <div className="bg-white rounded-md overflow-hidden">
        <table className="w-full text-[12px]">
          <thead className="bg-neutral-50 text-[10px] uppercase tracking-wider text-neutral-500">
            <tr>
              <th className="px-3 py-2 text-left">Paciente</th>
              <th className="px-3 py-2 text-left">Profissional</th>
              <th className="px-3 py-2 text-right">Valor</th>
              <th className="px-3 py-2 text-center">Status</th>
              <th className="px-3 py-2 text-right">Há quanto</th>
              <th className="px-3 py-2 text-left">Telefone</th>
            </tr>
          </thead>
          <tbody>
            {data.map((o, i) => (
              <tr key={o.treatment_external_id} className={i % 2 ? 'bg-neutral-50/50' : ''}>
                <td className="px-3 py-2 truncate max-w-[180px]" title={o.patient_name || ''}>
                  <button
                    type="button"
                    onClick={() => onPickPaciente(o.patient_external_id)}
                    className="hover:underline text-left"
                  >
                    {o.patient_name || `#${o.patient_external_id}`}
                  </button>
                </td>
                <td className="px-3 py-2 truncate max-w-[140px] text-neutral-600" title={o.professional_name || ''}>
                  {o.professional_name || <span className="text-neutral-400">—</span>}
                </td>
                <td className="px-3 py-2 text-right font-bold tabular-nums text-emerald-700">
                  {fmtBRL(o.amount, true)}
                </td>
                <td className="px-3 py-2 text-center">
                  <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold ${
                    o.status === 'FOLLOWUP' ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {o.status === 'FOLLOWUP' ? 'EM DECISÃO' : 'ABERTO'}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-neutral-600">
                  {o.days_ago}d
                </td>
                <td className="px-3 py-2 text-neutral-600 tabular-nums">
                  {o.mobile_phone || <span className="text-neutral-400">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Top LTV ───────────────────────────────────────────────────

function TopLtvCard({
  data, onPickPaciente,
}: { data: TopLtvPaciente[]; onPickPaciente: (pid: number) => void }) {
  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <Crown size={14} className="text-amber-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">Top LTV</span>
        </div>
        <div className="text-sm text-neutral-400 py-6 text-center">Sem dados.</div>
      </div>
    )
  }
  const max = Math.max(...data.map((p) => p.ltv), 1)
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <Crown size={14} className="text-amber-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top LTV — pacientes mais valiosos
        </span>
      </div>
      <ul className="space-y-2.5">
        {data.map((p, i) => {
          const meta = BUCKET_META[p.bucket] || BUCKET_META.sem_visita
          return (
            <li key={p.external_id}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                  i === 0 ? 'bg-amber-100 text-amber-700' :
                  i === 1 ? 'bg-neutral-100 text-neutral-600' :
                  i === 2 ? 'bg-orange-100 text-orange-700' :
                  'bg-neutral-50 text-neutral-500'
                }`}>{i + 1}</span>
                <button
                  type="button"
                  onClick={() => onPickPaciente(p.external_id)}
                  className="text-[12px] font-medium text-neutral-800 hover:underline truncate flex-1 text-left"
                  title={p.name || ''}
                >
                  {p.name || `#${p.external_id}`}
                </button>
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${meta.bg} ${meta.text}`}>
                  {meta.label}
                </span>
                <span className="text-[12px] font-bold tabular-nums text-amber-700 shrink-0">
                  {fmtBRL(p.ltv, true)}
                </span>
              </div>
              <div className="ml-7 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: `${(p.ltv / max) * 100}%` }} />
                </div>
                <span className="text-[10px] text-neutral-500 tabular-nums w-24 text-right">
                  {p.total_payments} pagto · {p.qtd_consultas_total} cons.
                </span>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ── Novos do mês ──────────────────────────────────────────────

function NovosDoMesCard({
  data, onPickPaciente,
}: { data: NovoPacienteMes[]; onPickPaciente: (pid: number) => void }) {
  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
        <div className="flex items-center gap-2 mb-2">
          <UserPlus size={14} className="text-emerald-600" />
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
            Novos pacientes do mês
          </span>
        </div>
        <div className="text-sm text-neutral-400 py-6 text-center">Sem novos pacientes no período.</div>
      </div>
    )
  }
  const aprovaramQty = data.filter((p) => p.aprovou).length
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <UserPlus size={14} className="text-emerald-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Novos do mês — top {data.length}
        </span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {aprovaramQty} de {data.length} mostrados aprovaram orçamento no mês
      </div>
      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-[11.5px]">
          <thead className="text-[10px] uppercase tracking-wider text-neutral-500 border-b border-neutral-200">
            <tr>
              <th className="px-2 py-1.5 text-left">Paciente</th>
              <th className="px-2 py-1.5 text-left">Profissional</th>
              <th className="px-2 py-1.5 text-center">1ª visita</th>
              <th className="px-2 py-1.5 text-center">Status</th>
              <th className="px-2 py-1.5 text-right">R$</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p, i) => (
              <tr key={p.external_id} className={i % 2 ? 'bg-neutral-50/50' : ''}>
                <td className="px-2 py-1.5 truncate max-w-[180px]" title={p.name || ''}>
                  <button
                    type="button"
                    onClick={() => onPickPaciente(p.external_id)}
                    className="hover:underline text-left"
                  >
                    {p.name || `#${p.external_id}`}
                  </button>
                </td>
                <td className="px-2 py-1.5 truncate max-w-[140px] text-neutral-600" title={p.professional_name || ''}>
                  {p.professional_name || <span className="text-neutral-400">—</span>}
                </td>
                <td className="px-2 py-1.5 text-center text-neutral-600 tabular-nums">
                  {fmtDate(p.first_seen_at)}
                </td>
                <td className="px-2 py-1.5 text-center">
                  {p.aprovou ? (
                    <span className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-100 text-emerald-700">
                      APROVOU
                    </span>
                  ) : p.teve_orcamento ? (
                    <span className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold bg-amber-100 text-amber-700">
                      EM DECISÃO
                    </span>
                  ) : (
                    <span className="inline-block px-1.5 py-0.5 rounded text-[9px] font-bold bg-neutral-100 text-neutral-500">
                      AVULSO
                    </span>
                  )}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {p.valor_aprovado > 0 ? (
                    <span className="text-emerald-700 font-semibold">{fmtBRL(p.valor_aprovado, true)}</span>
                  ) : (
                    <span className="text-neutral-400">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Insight pra SonIA ─────────────────────────────────────────

function buildPacientesInsight(data: AnalisePacientesResponse): SonIAInsight {
  const k = data.kpis
  const saude = data.saude_base
  const resgate = data.para_resgatar.length
  const orcPend = data.orcamentos_pendentes.length

  const emRiscoPct = saude.em_risco_pct + saude.perdido_pct
  const recPct = k.taxa_recorrencia_pct.value ?? 0

  // Mês em andamento: saúde da base e LTV são fotos do "agora" (válidos),
  // mas MoM de qty é enganoso. Suprimir MoM dos bullets e tom mais neutro.
  const partial = k.pacientes_ativos.is_partial
  if (partial) {
    const days = k.pacientes_ativos.partial_days ?? 0
    const total = k.pacientes_ativos.partial_days_in_month ?? 30
    const pctMes = total > 0 ? Math.round((days / total) * 100) : 0

    // Alertas absolutos ainda válidos (saúde da base não depende de MoM).
    const moodPartial: SonIAInsight['mood'] = emRiscoPct >= 35 ? 'alert' : 'curious'
    return {
      mood: moodPartial,
      headline: emRiscoPct >= 35
        ? 'Olhei a base e queria te mostrar uma coisa.'
        : `Olhei a base de pacientes — uma foto até agora.`,
      detail: emRiscoPct >= 35
        ? `${emRiscoPct.toFixed(0)}% da base está em risco ou já perdida. ${fmtNum(resgate)} pacientes podem ser resgatados — um contato gentil pode ajudar.`
        : `Estamos no dia ${days} de ${total} (${pctMes}% do mês). ${k.pacientes_ativos.value_label} pacientes ativos no momento, recorrência ${recPct.toFixed(0)}%. Espero o mês fechar pra falar de tendência.`,
      bullets: [
        { text: `${k.pacientes_ativos.value_label} pacientes ativos (foto atual).`, tone: 'neutral' },
        { text: `Recorrência ${k.taxa_recorrencia_pct.value_label}.`, tone: 'neutral' },
        { text: `LTV médio ${k.ltv_medio.value_label}.`, tone: 'neutral' },
        { text: `${saude.ativo_qty} ativos · ${saude.em_risco_qty} em risco · ${saude.inativo_qty} inativos.`, tone: emRiscoPct >= 30 ? 'warning' : 'neutral' },
        ...(resgate > 0 ? [{ text: `${fmtNum(resgate)} pacientes na lista pra resgatar.`, tone: 'warning' as const }] : []),
        ...(orcPend > 0 ? [{ text: `${fmtNum(orcPend)} orçamentos pendentes — oportunidades quentes.`, tone: 'warning' as const }] : []),
      ],
    }
  }

  const moodAlert = emRiscoPct >= 35 || (resgate >= 10 && recPct < 30)
  const moodHappy = recPct >= 60 && emRiscoPct < 20

  const mood: SonIAInsight['mood'] = moodAlert ? 'alert' : moodHappy ? 'happy' : 'curious'

  const headline = moodAlert
    ? 'Olhei a base e queria te mostrar uma coisa.'
    : moodHappy
    ? 'Olha que notícia boa.'
    : 'Olhei os pacientes com calma.'

  const detail = moodAlert
    ? `${emRiscoPct.toFixed(0)}% da sua base está em risco ou já perdida. Tem ${fmtNum(resgate)} pacientes na lista pra resgatar — quem sabe um contato gentil ajuda a trazê-los de volta?`
    : moodHappy
    ? `${k.pacientes_ativos.value_label} pacientes ativos e ${recPct.toFixed(0)}% de recorrência. A base está saudável.`
    : `${k.pacientes_ativos.value_label} pacientes ativos, recorrência em ${recPct.toFixed(0)}%. ${resgate > 0 ? `${fmtNum(resgate)} pacientes podem ser resgatados.` : ''}`

  const bullets: SonIAInsight['bullets'] = [
    { text: `${k.pacientes_ativos.value_label} pacientes ativos${pctSuffix(k.pacientes_ativos.mom_pct)}.`, tone: tonePctP(k.pacientes_ativos.mom_pct, false) },
    { text: `Recorrência ${k.taxa_recorrencia_pct.value_label}${pctSuffix(k.taxa_recorrencia_pct.mom_pct)}.`, tone: tonePctP(k.taxa_recorrencia_pct.mom_pct, false) },
    { text: `LTV médio ${k.ltv_medio.value_label}.`, tone: 'neutral' },
    { text: `${saude.ativo_qty} ativos · ${saude.em_risco_qty} em risco · ${saude.inativo_qty} inativos.`, tone: emRiscoPct >= 30 ? 'warning' : 'neutral' },
  ]
  if (resgate > 0) {
    bullets.push({ text: `${fmtNum(resgate)} pacientes na lista pra resgatar.`, tone: 'warning' })
  }
  if (orcPend > 0) {
    bullets.push({ text: `${fmtNum(orcPend)} orçamentos pendentes — oportunidades quentes.`, tone: 'warning' })
  }

  return { mood, headline, detail, bullets }
}

function pctSuffix(p: number | null): string {
  if (p === null) return ''
  const sign = p > 0 ? '+' : ''
  return ` (${sign}${p.toFixed(1)}% vs mês passado)`
}

function tonePctP(p: number | null, inverse: boolean): 'positive' | 'negative' | 'neutral' | 'warning' {
  if (p === null) return 'neutral'
  if (Math.abs(p) < 2) return 'neutral'
  const positivo = inverse ? p < 0 : p > 0
  if (positivo) return 'positive'
  return Math.abs(p) >= 10 ? 'negative' : 'warning'
}
