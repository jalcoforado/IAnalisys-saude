/**
 * Camada 1 — Capacidade & Encaixe.
 *
 * Mostra ocupação do dia (consultas e horas cadeira) contra o teto P95 dos
 * últimos 90 dias, profissionais com mais folga (candidatos a encaixe), e
 * janelas vagas >= 30min na agenda.
 */
import { Gauge, Clock4, UserPlus, AlertCircle } from 'lucide-react'
import type { CapacitySection } from '@/types/home'
import { initials } from './helpers'

const fmtMin = (m: number) => {
  if (m >= 60) {
    const h = Math.floor(m / 60)
    const rest = m % 60
    return rest === 0 ? `${h}h` : `${h}h${rest.toString().padStart(2, '0')}`
  }
  return `${m}min`
}

// Cor da barra de ocupação por faixa: vermelho >= 100, ambar 80-99, verde 50-79, neutro <50
function ocupColor(pct: number): { bar: string; text: string } {
  if (pct >= 100) return { bar: 'bg-red-500', text: 'text-red-700' }
  if (pct >= 80) return { bar: 'bg-amber-500', text: 'text-amber-700' }
  if (pct >= 50) return { bar: 'bg-emerald-500', text: 'text-emerald-700' }
  return { bar: 'bg-neutral-400', text: 'text-neutral-600' }
}

export function CapacityCard({ data }: { data: CapacitySection }) {
  const histInsuficiente = data.historico_dias_efetivo < 14

  return (
    <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-blue-600 flex items-center justify-center">
          <Gauge size={16} className="text-white" />
        </div>
        <div>
          <div className="text-sm font-semibold text-neutral-800">Capacidade da clínica</div>
          <div className="text-[11px] text-neutral-500">
            Teto P95 dos últimos {data.historico_dias} dias
            {histInsuficiente && (
              <span className="ml-1 text-amber-600">
                · histórico em construção ({data.historico_dias_efetivo}d)
              </span>
            )}
          </div>
        </div>
      </div>

      {histInsuficiente ? (
        <div className="px-4 py-6 text-center">
          <AlertCircle size={20} className="mx-auto mb-2 text-amber-500" />
          <div className="text-sm text-neutral-700 font-medium">
            Histórico em construção
          </div>
          <div className="text-[11px] text-neutral-500 mt-0.5 max-w-md mx-auto">
            Precisamos de pelo menos 14 dias com dados pra calcular o teto da
            clínica com confiança. Sincronize meses anteriores para acelerar.
          </div>
        </div>
      ) : (
        <>
          {/* Bloco 1: Ocupação geral */}
          <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-neutral-100">
            <OcupBar
              icon={<Gauge size={14} />}
              label="Consultas"
              hoje={data.consultas_hoje}
              teto={data.consultas_teto_p95}
              pct={data.consultas_ocupacao_pct}
              suffix="consultas"
            />
            <OcupBar
              icon={<Clock4 size={14} />}
              label="Horas cadeira"
              hoje={data.horas_cadeira_hoje}
              teto={data.horas_cadeira_teto_p95}
              pct={data.horas_cadeira_ocupacao_pct}
              valueFormat={fmtMin}
              suffix="ocupação"
            />
          </div>

          {/* Bloco 2: profs com folga + encaixes */}
          <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-neutral-100 border-t border-neutral-100">
            <div className="px-4 py-3">
              <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2 flex items-center gap-1">
                <UserPlus size={11} />
                Profissionais com folga
              </div>
              {data.profs_com_folga.length === 0 ? (
                <div className="text-xs text-neutral-400">Sem dados suficientes por profissional</div>
              ) : (
                <div className="space-y-1.5">
                  {data.profs_com_folga.map((p) => {
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
                            <span className={`tabular-nums font-bold ${text}`}>
                              {p.ocupacao_pct}%
                            </span>
                          </div>
                          <div className="h-1 mt-0.5 bg-neutral-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full ${bar} transition-all`}
                              style={{ width: `${Math.min(100, p.ocupacao_pct)}%` }}
                            />
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

            <div className="px-4 py-3">
              <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2 flex items-center gap-1">
                <Clock4 size={11} />
                Janelas livres ({data.encaixes.length} · {fmtMin(data.encaixe_total_min)})
              </div>
              {data.encaixes.length === 0 ? (
                <div className="text-xs text-neutral-400">Nenhuma janela ≥ 30min disponível</div>
              ) : (
                <div className="space-y-1 max-h-56 overflow-y-auto pr-1">
                  {data.encaixes.slice(0, 12).map((e, idx) => (
                    <div
                      key={`${e.professional_external_id}-${e.inicio}-${idx}`}
                      className="flex items-center gap-2 text-[11px] py-1 px-2 rounded hover:bg-neutral-50"
                    >
                      <span className="w-6 h-6 rounded-full bg-emerald-50 text-emerald-700 flex items-center justify-center text-[9px] font-bold shrink-0">
                        {initials(e.professional_nome ?? '?')}
                      </span>
                      <span className="font-medium text-neutral-700 flex-1 truncate">
                        {e.professional_nome ?? `Prof. #${e.professional_external_id}`}
                      </span>
                      <span className="font-mono tabular-nums text-neutral-500">
                        {e.inicio}–{e.fim}
                      </span>
                      <span className="text-emerald-700 font-bold tabular-nums w-12 text-right">
                        {fmtMin(e.duracao_min)}
                      </span>
                    </div>
                  ))}
                  {data.encaixes.length > 12 && (
                    <div className="text-[10px] text-neutral-400 text-center pt-1">
                      +{data.encaixes.length - 12} outras janelas
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function OcupBar({
  icon, label, hoje, teto, pct, suffix, valueFormat,
}: {
  icon: React.ReactNode
  label: string
  hoje: number
  teto: number
  pct: number
  suffix: string
  valueFormat?: (n: number) => string
}) {
  const { bar, text } = ocupColor(pct)
  const fmt = valueFormat ?? ((n: number) => n.toString())
  return (
    <div className="px-4 py-3">
      <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-1 flex items-center gap-1">
        {icon}
        {label}
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-2xl font-bold text-neutral-800 tabular-nums">{fmt(hoje)}</span>
        <span className="text-xs text-neutral-400">de</span>
        <span className="text-base font-semibold text-neutral-600 tabular-nums">{fmt(teto)}</span>
        <span className={`ml-auto text-sm font-bold tabular-nums ${text}`}>{pct}%</span>
      </div>
      <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
        <div
          className={`h-full ${bar} transition-all`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <div className="text-[10px] text-neutral-400 mt-1">teto P95 · {suffix}</div>
    </div>
  )
}
