import { Crown } from 'lucide-react'

import {
  BUCKET_META,
  WidgetError,
  WidgetLoading,
  fmtBRL,
  useAnalisePacientesAtual,
} from './_shared'

export function TopLtvCard() {
  const q = useAnalisePacientesAtual()

  if (q.isLoading) return <WidgetLoading label="top LTV" />
  if (q.isError || !q.data) return <WidgetError label="Top LTV" />

  const data = q.data.top_ltv

  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full">
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
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <Crown size={14} className="text-amber-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top LTV — pacientes mais valiosos
        </span>
      </div>
      <ul className="space-y-2.5 overflow-y-auto flex-1">
        {data.slice(0, 10).map((p, i) => {
          const meta = BUCKET_META[p.bucket] || BUCKET_META.sem_visita
          return (
            <li key={p.external_id}>
              <div className="flex items-center gap-2 mb-1">
                <span
                  className={`w-5 h-5 rounded-full text-[10px] font-bold flex items-center justify-center shrink-0 ${
                    i === 0
                      ? 'bg-amber-100 text-amber-700'
                      : i === 1
                      ? 'bg-neutral-100 text-neutral-600'
                      : i === 2
                      ? 'bg-orange-100 text-orange-700'
                      : 'bg-neutral-50 text-neutral-500'
                  }`}
                >
                  {i + 1}
                </span>
                <span
                  className="text-[12px] font-medium text-neutral-800 truncate flex-1"
                  title={p.name || ''}
                >
                  {p.name || `#${p.external_id}`}
                </span>
                <span
                  className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wide ${meta.bg} ${meta.text}`}
                >
                  {meta.label}
                </span>
                <span className="text-[12px] font-bold tabular-nums text-amber-700 shrink-0">
                  {fmtBRL(p.ltv, true)}
                </span>
              </div>
              <div className="ml-7 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-amber-500 rounded-full"
                    style={{ width: `${(p.ltv / max) * 100}%` }}
                  />
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
