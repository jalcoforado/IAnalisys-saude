/**
 * Card da lista de espera (tags "Aguardado vaga" e "Encaixe" do Clinicorp).
 *
 * Bonita junto com CapacityCard porque sempre que há encaixe disponível
 * (gap >= 30min na agenda do prof), o gestor pode olhar essa lista pra
 * preencher. É a Camada B do plano: virar o sistema operacional da fila.
 */
import { Hourglass, Calendar, Clock, ArrowRight } from 'lucide-react'
import type { WaitlistSection } from '@/types/home'
import { initials } from './helpers'

const fmtDate = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

const tagBadge = (isWaitlist: boolean, isEncaixe: boolean): { label: string; ring: string; dot: string } => {
  if (isWaitlist && isEncaixe)
    return { label: 'Aguardando + Encaixe', ring: 'ring-fuchsia-300', dot: 'bg-fuchsia-500' }
  if (isWaitlist)
    return { label: 'Aguardando vaga', ring: 'ring-green-300', dot: 'bg-green-500' }
  return { label: 'Encaixe', ring: 'ring-fuchsia-300', dot: 'bg-fuchsia-500' }
}

export function WaitlistCard({ data }: { data: WaitlistSection }) {
  if (data.total === 0) return null

  return (
    <section className="rounded-xl border border-neutral-200 bg-white shadow-sm overflow-hidden">
      <header className="px-5 py-3 flex items-center gap-3 border-b border-neutral-100">
        <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center text-green-600 ring-1 ring-green-100">
          <Hourglass size={18} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-neutral-500">
            Lista de espera
          </div>
          <div className="text-sm font-bold text-neutral-800">
            {data.total} paciente{data.total === 1 ? '' : 's'} na fila
          </div>
        </div>
        <div className="flex gap-2 text-[11px]">
          {data.waitlist_count > 0 && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-green-50 text-green-700 font-medium ring-1 ring-green-200">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
              Aguardando vaga · {data.waitlist_count}
            </span>
          )}
          {data.encaixe_count > 0 && (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded-full bg-fuchsia-50 text-fuchsia-700 font-medium ring-1 ring-fuchsia-200">
              <span className="w-1.5 h-1.5 rounded-full bg-fuchsia-500" />
              Encaixe · {data.encaixe_count}
            </span>
          )}
        </div>
      </header>

      <ul className="divide-y divide-neutral-100">
        {data.items.slice(0, 8).map((item) => {
          const badge = tagBadge(item.is_waitlist, item.is_encaixe)
          return (
            <li
              key={item.appointment_external_id}
              className="px-5 py-2.5 flex items-center gap-3 hover:bg-neutral-50/60 transition-colors"
            >
              {/* Avatar com iniciais */}
              <div className={`w-9 h-9 rounded-full bg-neutral-100 text-neutral-700 flex items-center justify-center text-[11px] font-bold ring-2 ${badge.ring} shrink-0`}>
                {initials(item.paciente_nome)}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="font-semibold text-sm text-neutral-800 truncate">
                    {item.paciente_nome.replace(/\*/g, '').trim()}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[10px] font-medium text-neutral-500">
                    <span className={`w-1.5 h-1.5 rounded-full ${badge.dot}`} />
                    {badge.label}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[11px] text-neutral-500">
                  {item.profissional_nome && (
                    <span className="truncate">com {item.profissional_nome.replace(/\*/g, '').trim()}</span>
                  )}
                  <span className="inline-flex items-center gap-1">
                    <Calendar size={11} />
                    {fmtDate(item.appointment_date_iso)}
                    {item.horario && (
                      <>
                        <Clock size={11} className="ml-1" />
                        {item.horario}
                      </>
                    )}
                  </span>
                </div>
              </div>

              <div className="text-right shrink-0">
                <div className="text-[10px] uppercase tracking-wider text-neutral-400">Aguarda</div>
                <div className="text-sm font-bold text-neutral-700 tabular-nums">
                  {item.dias_aguardando}d
                </div>
              </div>
            </li>
          )
        })}
      </ul>

      {data.items.length > 8 && (
        <footer className="px-5 py-2 border-t border-neutral-100 text-[11px] text-neutral-500 flex items-center justify-end gap-1">
          + {data.items.length - 8} outros pacientes na fila
          <ArrowRight size={11} />
        </footer>
      )}
    </section>
  )
}
