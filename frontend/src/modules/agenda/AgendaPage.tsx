/**
 * Página dedicada à Agenda.
 * Consome /home/agenda?date=... — endpoint dedicado que aceita data alvo.
 * Seletor permite Hoje / Amanhã / Depois de amanhã (limite gerencial: +2d).
 */
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Calendar } from 'lucide-react'

import { homeService } from '@/services/home.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import type { AgendaSection, StatusType } from '@/types/home'
import { AgendaMatrix } from './AgendaMatrix'
import { AgendaInsightsCard } from './AgendaInsightsCard'
import { CapacityCard } from './CapacityCard'
import { RiskCard } from './RiskCard'
import { WaitlistCard } from './WaitlistCard'
import { STATUS_LABEL, STATUS_DOT } from './helpers'
import { useSonIA, type SonIAInsight } from '@/components/sonia/SonIAContext'

// Resolve YYYY-MM-DD em horário LOCAL (não UTC). Necessário porque o
// backend interpreta esse param no timezone do tenant.
function dateOffset(daysAhead: number): string {
  const d = new Date()
  d.setDate(d.getDate() + daysAhead)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

const DATE_OPTIONS: { key: 'today' | 'tomorrow' | 'day_after'; label: string; offset: number }[] = [
  { key: 'today', label: 'Hoje', offset: 0 },
  { key: 'tomorrow', label: 'Amanhã', offset: 1 },
  { key: 'day_after', label: 'Depois de amanhã', offset: 2 },
]

const fmtDateLong = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })
}
const fmtWeekday = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { weekday: 'long' })
}

// Ordem fixa pra apresentação consistente. Agendado (null) vem primeiro,
// depois fluxo cronológico do dia: Confirmado → Chegou → Em atendimento
// → Atendido → Atrasado/Faltou → outros.
const STATUS_HEADER_ORDER: StatusType[] = [
  'CONFIRMED', 'ARRIVED', 'IN_SESSION', 'CHECKOUT', 'LATE', 'MISSED', 'CALL', 'PENDING_MATERIAL',
]

function AgendaPageHeader({ agenda }: { agenda: AgendaSection }) {
  const counts = new Map<StatusType | 'AGENDADO', number>()
  for (const it of agenda.items) {
    const key = it.status_type ?? 'AGENDADO'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  const agendadoQty = counts.get('AGENDADO') ?? 0

  // Decide quais pílulas mostrar: Agendado (se houver) + qualquer status
  // com contagem > 0, na ordem definida.
  const pills: { label: string; count: number; dotClass: string }[] = []
  if (agendadoQty > 0) pills.push({ label: 'Agendado', count: agendadoQty, dotClass: 'bg-white/40' })
  for (const s of STATUS_HEADER_ORDER) {
    const c = counts.get(s) ?? 0
    if (c > 0) pills.push({ label: STATUS_LABEL[s], count: c, dotClass: STATUS_DOT[s] })
  }

  const wd = fmtWeekday(agenda.date_iso)
  const wdCap = wd.charAt(0).toUpperCase() + wd.slice(1)
  return (
    <>
      <PageHeader
        eyebrow={agenda.is_today ? 'AGENDA DE HOJE' : 'PRÓXIMO DIA COM CONSULTAS'}
        title={wdCap}
        subtitle={fmtDateLong(agenda.date_iso)}
        icon={<Calendar size={20} />}
        actions={
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-wider text-white/70 font-semibold">Total</div>
            <div className="text-3xl font-bold tabular-nums">{agenda.total}</div>
          </div>
        }
      />

      {/* Breakdown por status — pills com cor + contagem + percentual */}
      {pills.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {pills.map((p) => {
            const pct = agenda.total > 0 ? Math.round((p.count / agenda.total) * 100) : 0
            return (
              <div
                key={p.label}
                className="inline-flex items-center gap-1.5 bg-white border border-neutral-200 rounded-full pl-2 pr-2.5 py-1 text-[11px] shadow-sm"
              >
                <span className={`w-2 h-2 rounded-full ${p.dotClass === 'bg-white/40' ? 'bg-neutral-400' : p.dotClass}`} />
                <span className="font-medium text-neutral-700">{p.label}</span>
                <span className="font-bold text-neutral-900 tabular-nums">{p.count}</span>
                <span className="text-neutral-300">·</span>
                <span className="text-neutral-500 tabular-nums">{pct}%</span>
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}

export default function AgendaPage() {
  usePageTitle('Agenda', 'Visão do dia · matriz por profissional · insights de IA', 'OPERAÇÕES')

  const [selected, setSelected] = useState<typeof DATE_OPTIONS[number]['key']>('today')
  const targetOption = DATE_OPTIONS.find((o) => o.key === selected) ?? DATE_OPTIONS[0]
  const targetDate = dateOffset(targetOption.offset)

  const agendaQ = useQuery({
    queryKey: ['home', 'agenda', targetDate],
    // Hoje sem param (deixa o backend resolver via timezone do tenant +
    // fallback). Demais dias passam date explícita.
    queryFn: () => homeService.agenda(selected === 'today' ? undefined : targetDate),
    refetchInterval: selected === 'today' ? 60_000 : false,
  })

  const { publish, clear } = useSonIA()
  useEffect(() => {
    if (!agendaQ.data) return
    publish({
      pageKey: '/agenda',
      pageTitle: 'Agenda',
      data: { insight: buildAgendaInsight(agendaQ.data, targetOption.label) },
    })
    return () => clear('/agenda')
  }, [agendaQ.data, targetOption.label, publish, clear])

  return (
    <PageContainer variant="wide">
      {/* Seletor de dia */}
      <div className="flex items-center gap-2">
        <span className="text-[11px] uppercase tracking-wider font-semibold text-neutral-500 mr-1">
          Visão
        </span>
        {DATE_OPTIONS.map((opt) => {
          const isActive = opt.key === selected
          return (
            <button
              key={opt.key}
              onClick={() => setSelected(opt.key)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                isActive
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-white border border-neutral-200 text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50'
              }`}
            >
              {opt.label}
            </button>
          )
        })}
      </div>

      {agendaQ.isLoading && !agendaQ.data ? (
        <div className="py-12 flex items-center justify-center">
          <Loader2 size={28} className="animate-spin text-neutral-400" />
        </div>
      ) : !agendaQ.data ? (
        <div className="rounded-xl border border-neutral-200 bg-white p-12 text-center text-neutral-400">
          <Calendar size={32} className="mx-auto mb-3 text-neutral-300" />
          Sem dados de agenda disponíveis.
        </div>
      ) : agendaQ.data.total === 0 ? (
        <>
          <AgendaPageHeader agenda={agendaQ.data} />
          <div className="rounded-xl border border-dashed border-neutral-300 bg-white p-10 text-center">
            <Calendar size={32} className="mx-auto mb-3 text-neutral-300" />
            <div className="text-sm font-semibold text-neutral-700 mb-1">
              Nenhuma consulta agendada para {targetOption.label.toLowerCase()}
            </div>
            <div className="text-xs text-neutral-500 max-w-md mx-auto leading-relaxed">
              Pode ser que a clínica ainda não tenha marcado nada para esta data
              ou que a última sincronização não cobre este dia.
              Verifique o {' '}
              <a href="/admin/sync" className="text-primary-700 hover:underline font-medium">
                painel de sincronização
              </a>
              {' '} se necessário.
            </div>
          </div>
        </>
      ) : (
        <>
          <AgendaPageHeader agenda={agendaQ.data} />
          <AgendaInsightsCard data={agendaQ.data} />
          {agendaQ.data.capacity && <CapacityCard data={agendaQ.data.capacity} />}
          {agendaQ.data.waitlist && <WaitlistCard data={agendaQ.data.waitlist} />}
          {agendaQ.data.risk && <RiskCard data={agendaQ.data.risk} />}
          <AgendaMatrix data={agendaQ.data} />
        </>
      )}
    </PageContainer>
  )
}

// ── Insight pra SonIA ─────────────────────────────────────────

function buildAgendaInsight(data: AgendaSection, diaLabel: string): SonIAInsight {
  const total = data.items.length
  const confirmados = data.items.filter((i) => i.status_type === 'CONFIRMED').length
  const faltas = data.items.filter((i) => i.status_type === 'MISSED').length
  const efetivas = data.items.filter((i) =>
    ['ARRIVED', 'IN_SESSION', 'CHECKOUT'].includes(i.status_type ?? ''),
  ).length

  const confirmadosPct = total > 0 ? Math.round((confirmados / total) * 100) : 0
  const faltasPct = total > 0 ? Math.round((faltas / total) * 100) : 0

  const altoRisco = data.risk?.pacientes_alto_risco.length ?? 0
  const encaixe = data.capacity?.encaixe_total_min ?? 0
  const encaixeH = Math.floor(encaixe / 60)

  const moodAlerta = faltasPct >= 20 || altoRisco >= 3
  const mood = moodAlerta ? 'alert' : encaixe >= 60 ? 'curious' : 'default'

  const headline = moodAlerta
    ? 'Olhei a agenda — tem uns pontos pra olharmos juntos.'
    : encaixe >= 60
    ? 'Olhei a agenda com calma — tem espaço pra encaixe.'
    : `Aqui está como ${diaLabel.toLowerCase()} está se desenhando.`

  const detail = moodAlerta
    ? `${total} agendamentos, ${faltas} marcados como falta (${faltasPct}%) e ${altoRisco} pacientes com risco elevado. Vale acompanhar de perto.`
    : encaixe >= 60
    ? `${total} agendamentos previstos. Tenho ${encaixeH > 0 ? `${encaixeH}h de` : ''} folga no calendário — janelas que podem virar encaixe pra fila de espera.`
    : `${total} agendamentos no total, ${confirmados} confirmados (${confirmadosPct}%) e ${efetivas} já efetivados.`

  const bullets: SonIAInsight['bullets'] = [
    { text: `${total} agendamentos no dia.`, tone: 'neutral' },
    { text: `${confirmados} confirmados (${confirmadosPct}%).`, tone: confirmadosPct >= 60 ? 'positive' : 'warning' },
  ]
  if (faltas > 0) {
    bullets.push({ text: `${faltas} faltas marcadas (${faltasPct}%).`, tone: faltasPct >= 20 ? 'negative' : 'warning' })
  }
  if (altoRisco > 0) {
    bullets.push({ text: `${altoRisco} paciente${altoRisco > 1 ? 's' : ''} de alto risco.`, tone: 'warning' })
  }
  if (encaixe >= 30) {
    bullets.push({
      text: `${encaixeH > 0 ? `${encaixeH}h ${encaixe % 60}min` : `${encaixe}min`} de folga pra encaixe.`,
      tone: 'positive',
    })
  }

  return { mood, headline, detail, bullets }
}
