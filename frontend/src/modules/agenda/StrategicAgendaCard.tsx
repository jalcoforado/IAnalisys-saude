/**
 * Visão estratégica da agenda (Hoje + Amanhã + Depois) pra HomePage do dono.
 *
 * Estrutura:
 *  - Header com totais agregados (3 dias) + link pra /agenda
 *  - Grid 3 colunas: 1 dia em cada coluna com KPIs essenciais
 *  - Bloco "Atenção esta semana": top pacientes a confirmar + top profs ociosos
 */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import {
  CalendarRange, ArrowRight, ShieldAlert, UserPlus,
  TrendingUp, Phone, Clock4, Loader2,
} from 'lucide-react'

import { homeService } from '@/services/home.service'
import type { StrategicOverview, StrategicDayKPIs } from '@/types/home'
import { initials } from './helpers'

const fmtMin = (m: number) => {
  if (m >= 60) {
    const h = Math.floor(m / 60)
    const rest = m % 60
    return rest === 0 ? `${h}h` : `${h}h${rest.toString().padStart(2, '0')}`
  }
  return `${m}min`
}

function ocupColor(pct: number): { bar: string; text: string } {
  if (pct >= 100) return { bar: 'bg-red-500', text: 'text-red-700' }
  if (pct >= 80) return { bar: 'bg-amber-500', text: 'text-amber-700' }
  if (pct >= 50) return { bar: 'bg-emerald-500', text: 'text-emerald-700' }
  return { bar: 'bg-neutral-400', text: 'text-neutral-600' }
}

function riskColor(pct: number): string {
  if (pct >= 60) return 'text-red-700 bg-red-50 border-red-200'
  if (pct >= 40) return 'text-orange-700 bg-orange-50 border-orange-200'
  return 'text-amber-700 bg-amber-50 border-amber-200'
}

export function StrategicAgendaCard({ data }: { data: StrategicOverview }) {
  const faltasFmt = data.faltas_esperadas_3d_min === data.faltas_esperadas_3d_max
    ? `${data.faltas_esperadas_3d_min}`
    : `${data.faltas_esperadas_3d_min}–${data.faltas_esperadas_3d_max}`

  return (
    <div className="bg-white border border-neutral-200 rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden flex flex-col lg:col-span-3">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-neutral-100 flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-sm">
          <CalendarRange size={18} className="text-white" />
        </div>
        <div className="flex-1">
          <div className="text-sm font-semibold text-neutral-800">Agenda — visão estratégica</div>
          <div className="text-[11px] text-neutral-500 flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>{data.total_3d} consultas em 3 dias</span>
            <span>·</span>
            <span>{faltasFmt} faltas esperadas</span>
            <span>·</span>
            <span>{fmtMin(data.encaixe_total_3d_min)} de encaixe</span>
            {data.waitlist_3d > 0 && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-green-50 text-green-700 ring-1 ring-green-200 text-[10px] font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                {data.waitlist_3d} na fila
              </span>
            )}
            {data.encaixe_3d > 0 && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-fuchsia-50 text-fuchsia-700 ring-1 ring-fuchsia-200 text-[10px] font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-fuchsia-500" />
                {data.encaixe_3d} encaixe(s)
              </span>
            )}
          </div>
        </div>
        <Link
          to="/agenda"
          className="text-xs font-medium text-primary-700 hover:text-primary-900 flex items-center gap-1 transition-colors"
        >
          Ver agenda
          <ArrowRight size={14} />
        </Link>
      </div>

      {/* Grid 3 dias */}
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-neutral-100">
        {data.days.map((d) => <DayColumn key={d.date_iso} day={d} />)}
      </div>

      {/* Atenção: top pacientes risco + profs ociosos */}
      {(data.top_pacientes_risco.length > 0 || data.top_profs_ociosos.length > 0) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-neutral-100 border-t border-neutral-100">
          {/* Pacientes a confirmar */}
          <div className="px-5 py-3">
            <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2 flex items-center gap-1">
              <Phone size={11} />
              Confirmar antes — {data.top_pacientes_risco.length} pacientes em risco
            </div>
            {data.top_pacientes_risco.length === 0 ? (
              <div className="text-xs text-neutral-400">Nenhum paciente com risco alto.</div>
            ) : (
              <div className="space-y-1.5">
                {data.top_pacientes_risco.map((p) => (
                  <div
                    key={`${p.paciente_external_id}-${p.horario ?? '?'}`}
                    className={`flex items-center gap-2 text-[11px] py-1.5 px-2 rounded border ${riskColor(p.risco_pct)}`}
                  >
                    <span className="w-7 h-7 rounded-full bg-white text-neutral-700 flex items-center justify-center text-[10px] font-bold shrink-0 ring-1 ring-neutral-200">
                      {initials(p.paciente_nome)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="font-semibold text-neutral-800 truncate">{p.paciente_nome}</div>
                      <div className="text-[10px] text-neutral-600 truncate">
                        {p.horario ?? '—'} · {p.razao}
                      </div>
                    </div>
                    <div className="font-bold tabular-nums text-base shrink-0">{p.risco_pct}%</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Profs com folga */}
          <div className="px-5 py-3">
            <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2 flex items-center gap-1">
              <UserPlus size={11} />
              Oportunidade — profissionais com folga
            </div>
            {data.top_profs_ociosos.length === 0 ? (
              <div className="text-xs text-neutral-400">Sem profissionais com folga relevante.</div>
            ) : (
              <div className="space-y-1.5">
                {data.top_profs_ociosos.map((p) => {
                  const { bar, text } = ocupColor(p.ocupacao_pct)
                  return (
                    <div key={p.professional_external_id} className="flex items-center gap-2 text-[11px]">
                      <span className="w-7 h-7 rounded-full bg-neutral-100 text-neutral-700 flex items-center justify-center text-[10px] font-bold shrink-0">
                        {initials(p.professional_nome ?? '?')}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-medium text-neutral-700 truncate">
                            {p.professional_nome ?? `Prof. #${p.professional_external_id}`}
                          </span>
                          <span className={`tabular-nums font-bold ${text}`}>{p.ocupacao_pct}%</span>
                        </div>
                        <div className="h-1 mt-0.5 bg-neutral-100 rounded-full overflow-hidden">
                          <div className={`h-full ${bar}`} style={{ width: `${Math.min(100, p.ocupacao_pct)}%` }} />
                        </div>
                        <div className="text-[10px] text-neutral-500 mt-0.5 tabular-nums">
                          {p.consultas_hoje} de {p.consultas_teto_p95}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function DayColumn({ day }: { day: StrategicDayKPIs }) {
  const ocup = ocupColor(day.ocupacao_pct)
  const isTodayBadge = day.is_today
    ? 'bg-info-bg text-info-text'
    : 'bg-neutral-100 text-neutral-600'

  return (
    <div className="px-4 py-3 flex flex-col gap-2">
      {/* Header dia */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-wider font-semibold text-neutral-400">
            {day.label}
          </div>
          <div className="text-xs text-neutral-500 tabular-nums">{day.date_iso.substring(8, 10)}/{day.date_iso.substring(5, 7)}</div>
        </div>
        <span className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${isTodayBadge}`}>
          {day.is_today ? 'Hoje' : day.label}
        </span>
      </div>

      {/* Total + ocupação */}
      <div>
        <div className="flex items-baseline gap-1.5">
          <span className="text-2xl font-bold text-neutral-800 tabular-nums">{day.total}</span>
          <span className="text-[10px] text-neutral-500">consultas</span>
          <span className={`ml-auto text-sm font-bold tabular-nums ${ocup.text}`}>{day.ocupacao_pct}%</span>
        </div>
        <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden mt-1">
          <div className={`h-full ${ocup.bar}`} style={{ width: `${Math.min(100, day.ocupacao_pct)}%` }} />
        </div>
      </div>

      {/* Sub-KPIs */}
      <div className="grid grid-cols-2 gap-1.5 mt-1">
        <Mini icon={<TrendingUp size={10} />} label="Confirmados" value={day.confirmados_pct > 0 ? `${day.confirmados_pct}%` : '—'} accent="text-emerald-700" />
        <Mini icon={<ShieldAlert size={10} />} label="Faltas esp." value={day.faltas_esperadas_min === day.faltas_esperadas_max ? `${day.faltas_esperadas_min}` : `${day.faltas_esperadas_min}-${day.faltas_esperadas_max}`} accent="text-rose-700" />
        <Mini icon={<ShieldAlert size={10} />} label="Risco alto" value={day.riscos_altos > 0 ? `${day.riscos_altos}` : '0'} accent={day.riscos_altos > 0 ? 'text-orange-700' : 'text-neutral-500'} />
        <Mini icon={<Clock4 size={10} />} label="Encaixe" value={day.encaixe_min > 0 ? fmtMin(day.encaixe_min) : '—'} accent="text-blue-700" />
      </div>
    </div>
  )
}

function Mini({
  icon, label, value, accent,
}: {
  icon: React.ReactNode; label: string; value: string; accent: string
}) {
  return (
    <div className="bg-neutral-50 rounded px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wide font-semibold text-neutral-400 flex items-center gap-1">
        {icon}
        {label}
      </div>
      <div className={`text-sm font-bold tabular-nums ${accent}`}>{value}</div>
    </div>
  )
}

/**
 * Wrapper que faz a query da visão estratégica e plota o card.
 * Usado na HomePage do dono. Cache de 60s — KPIs não mudam tão rápido.
 */
export function StrategicAgendaSection() {
  const q = useQuery({
    queryKey: ['home', 'agenda-strategic'],
    queryFn: () => homeService.agendaStrategic(),
    refetchInterval: 60_000,
    staleTime: 30_000,
  })

  if (q.isLoading) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl shadow-md p-8 flex items-center justify-center lg:col-span-3">
        <Loader2 size={20} className="animate-spin text-neutral-400" />
      </div>
    )
  }
  if (!q.data) return null
  return <StrategicAgendaCard data={q.data} />
}
