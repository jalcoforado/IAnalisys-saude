/**
 * Resumo compacto da agenda do dia, usado na HomePage.
 * Mostra KPIs + próxima consulta + link pra página completa /agenda.
 */
import { Link } from 'react-router-dom'
import { CalendarClock, ArrowRight } from 'lucide-react'

import type { AgendaSection, StatusType } from '@/types/home'
import { calcAge, ageIcon, genderColor, initials, STATUS_LABEL, STATUS_DOT } from './helpers'

const fmtDateShort = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

export function AgendaSummaryCard({ data }: { data: AgendaSection }) {
  // Próxima consulta (futuro mais próximo)
  const now = new Date()
  const nowMin = data.is_today ? now.getHours() * 60 + now.getMinutes() : -1
  const proxima = data.items
    .map((it) => {
      if (!it.horario) return null
      const [h, m] = it.horario.split(':').map(Number)
      return { item: it, min: h * 60 + m }
    })
    .filter((x): x is { item: typeof data.items[number]; min: number } =>
      x !== null && (nowMin < 0 || x.min >= nowMin),
    )
    .sort((a, b) => a.min - b.min)[0]

  // Profissionais distintos
  const profsCount = new Set(
    data.items.map((it) => it.profissional_external_id).filter((id) => id != null),
  ).size

  const proxAge = proxima ? calcAge(proxima.item.paciente_birth_date) : null
  const ProxIcon = ageIcon(proxAge)

  // Breakdown por status — pills só pros status com count > 0, na ordem fixa.
  const statusCounts = new Map<StatusType | 'AGENDADO', number>()
  for (const it of data.items) {
    const key = it.status_type ?? 'AGENDADO'
    statusCounts.set(key, (statusCounts.get(key) ?? 0) + 1)
  }
  const statusPills: { label: string; count: number; dotClass: string }[] = []
  const agendadoQty = statusCounts.get('AGENDADO') ?? 0
  if (agendadoQty > 0) statusPills.push({ label: 'Agendado', count: agendadoQty, dotClass: 'bg-neutral-300' })
  for (const s of STATUS_SUMMARY_ORDER) {
    const c = statusCounts.get(s) ?? 0
    if (c > 0) statusPills.push({ label: STATUS_LABEL[s], count: c, dotClass: STATUS_DOT[s] })
  }

  return (
    <div className="bg-white border border-neutral-200 rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden flex flex-col lg:col-span-3">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-neutral-100 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-blue-700 flex items-center justify-center shadow-sm">
          <CalendarClock size={18} className="text-white" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-neutral-800">Agenda do dia</div>
          <div className="text-[11px] text-neutral-500">
            {data.is_today ? 'Hoje' : `Próximo dia · ${fmtDateShort(data.date_iso)}`}
          </div>
        </div>
        <Link
          to="/agenda"
          className="text-xs font-medium text-primary-700 hover:text-primary-900 flex items-center gap-1 transition-colors"
        >
          Ver agenda completa
          <ArrowRight size={14} />
        </Link>
      </div>

      {/* Total + status breakdown + próxima */}
      <div className="grid grid-cols-1 lg:grid-cols-[160px_1fr_220px] gap-0 divide-y lg:divide-y-0 lg:divide-x divide-neutral-100">
        {/* Total */}
        <div className="px-5 py-4 text-center flex flex-col justify-center">
          <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400">Total</div>
          <div className="text-3xl font-bold text-neutral-800 mt-1 tabular-nums">{data.total}</div>
          <div className="text-[11px] text-neutral-500">{profsCount} {profsCount === 1 ? 'profissional' : 'profissionais'}</div>
        </div>

        {/* Status breakdown — pills */}
        <div className="px-5 py-4 flex flex-col justify-center">
          <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2">Status agora</div>
          {statusPills.length === 0 ? (
            <div className="text-xs text-neutral-400">Sem dados de status</div>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {statusPills.map((p) => {
                const pct = data.total > 0 ? Math.round((p.count / data.total) * 100) : 0
                return (
                  <div
                    key={p.label}
                    className="inline-flex items-center gap-1.5 bg-neutral-50 border border-neutral-200 rounded-full pl-2 pr-2.5 py-1 text-[11px]"
                  >
                    <span className={`w-2 h-2 rounded-full ${p.dotClass}`} />
                    <span className="font-medium text-neutral-700">{p.label}</span>
                    <span className="font-bold text-neutral-900 tabular-nums">{p.count}</span>
                    <span className="text-neutral-400">·</span>
                    <span className="text-neutral-500 tabular-nums">{pct}%</span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Próxima consulta */}
        <div className="px-5 py-4 flex flex-col justify-center">
          <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 text-center">Próxima</div>
          {proxima ? (
            <div className="mt-1 flex items-center gap-2 justify-center">
              <ProxIcon size={20} className={`${genderColor(proxima.item.paciente_gender)} shrink-0`} strokeWidth={2} />
              <div className="min-w-0">
                <div className="text-base font-bold text-neutral-800 tabular-nums leading-none">
                  {proxima.item.horario}
                </div>
                <div className="text-[11px] text-neutral-500 truncate">
                  {initials(proxima.item.paciente_nome)} · {proxima.item.profissional_nome?.split(' ')[0] || '—'}
                </div>
              </div>
            </div>
          ) : (
            <div className="mt-1 text-center text-sm text-neutral-400">Sem próximas</div>
          )}
        </div>
      </div>
    </div>
  )
}

const STATUS_SUMMARY_ORDER: StatusType[] = [
  'CONFIRMED', 'ARRIVED', 'IN_SESSION', 'CHECKOUT', 'LATE', 'MISSED', 'CALL', 'PENDING_MATERIAL',
]
