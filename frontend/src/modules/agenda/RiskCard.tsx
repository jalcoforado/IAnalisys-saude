/**
 * Camada 2 — Risco de no-show (faltas previstas).
 *
 * Mostra:
 *  - Baseline da clínica (% típica de faltas)
 *  - Estimativa de faltas hoje (intervalo)
 *  - Top pacientes de alto risco com razão e ação sugerida
 */
import { ShieldAlert, TrendingDown, Phone } from 'lucide-react'
import type { RiskSection } from '@/types/home'
import { initials } from './helpers'

// Cor do badge por nível de risco
function riscoNivel(pct: number): { label: string; bar: string; chip: string; text: string } {
  if (pct >= 60) return { label: 'Crítico', bar: 'bg-red-500', chip: 'bg-red-50 border-red-200', text: 'text-red-700' }
  if (pct >= 40) return { label: 'Alto', bar: 'bg-orange-500', chip: 'bg-orange-50 border-orange-200', text: 'text-orange-700' }
  return { label: 'Médio', bar: 'bg-amber-500', chip: 'bg-amber-50 border-amber-200', text: 'text-amber-700' }
}

export function RiskCard({ data }: { data: RiskSection }) {
  if (data.consultas_avaliadas === 0) {
    return null  // dia sem consultas pendentes pra avaliar (todas já resolvidas)
  }

  const totalEsperado = data.faltas_esperadas_min === data.faltas_esperadas_max
    ? `${data.faltas_esperadas_min}`
    : `${data.faltas_esperadas_min}–${data.faltas_esperadas_max}`

  return (
    <div className="rounded-xl border border-neutral-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center">
          <ShieldAlert size={16} className="text-white" />
        </div>
        <div>
          <div className="text-sm font-semibold text-neutral-800">Risco de no-show</div>
          <div className="text-[11px] text-neutral-500">
            Baseline da clínica: {data.baseline_pct}% · Histórico {data.historico_dias}d
          </div>
        </div>
      </div>

      {/* KPI: faltas esperadas */}
      <div className="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-neutral-100">
        <div className="px-4 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 flex items-center justify-center gap-1">
            <TrendingDown size={11} />
            Faltas esperadas
          </div>
          <div className="text-2xl font-bold text-rose-600 mt-1 tabular-nums">{totalEsperado}</div>
          <div className="text-[11px] text-neutral-500">
            de {data.consultas_avaliadas} avaliadas
          </div>
        </div>
        <div className="px-4 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400">
            Baseline
          </div>
          <div className="text-2xl font-bold text-neutral-700 mt-1 tabular-nums">{data.baseline_pct}%</div>
          <div className="text-[11px] text-neutral-500">média histórica</div>
        </div>
        <div className="px-4 py-3 text-center">
          <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400">
            Alto risco
          </div>
          <div className="text-2xl font-bold text-orange-600 mt-1 tabular-nums">
            {data.pacientes_alto_risco.length}
          </div>
          <div className="text-[11px] text-neutral-500">pacientes destacados</div>
        </div>
      </div>

      {/* Lista top alto risco */}
      <div className="border-t border-neutral-100 px-4 py-3">
        <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2 flex items-center gap-1">
          <Phone size={11} />
          Atenção — confirmar antes da consulta
        </div>
        {data.pacientes_alto_risco.length === 0 ? (
          <div className="text-xs text-neutral-400">Nenhum paciente com risco alto identificado.</div>
        ) : (
          <div className="space-y-1.5">
            {data.pacientes_alto_risco.map((p) => {
              const nivel = riscoNivel(p.risco_pct)
              return (
                <div
                  key={`${p.paciente_external_id}-${p.horario ?? '?'}`}
                  className={`flex items-center gap-2 text-[11px] py-1.5 px-2 rounded border ${nivel.chip}`}
                >
                  <span className="w-7 h-7 rounded-full bg-white text-neutral-700 flex items-center justify-center text-[10px] font-bold shrink-0 ring-1 ring-neutral-200">
                    {initials(p.paciente_nome)}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-neutral-800 truncate">{p.paciente_nome}</span>
                      <span className={`text-[9px] uppercase font-bold tracking-wide ${nivel.text}`}>
                        {nivel.label}
                      </span>
                    </div>
                    <div className="text-[10px] text-neutral-600 truncate">
                      {p.horario ?? '—'} · {p.profissional_nome?.split(' ')[0] ?? '—'} · {p.razao}
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className={`text-base font-bold tabular-nums ${nivel.text}`}>
                      {p.risco_pct}%
                    </div>
                    {p.total_historico > 0 && (
                      <div className="text-[9px] text-neutral-500">{p.total_historico} visitas</div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
