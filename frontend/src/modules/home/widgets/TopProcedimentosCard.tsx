import { TrendingUp } from 'lucide-react'

import {
  WidgetError,
  WidgetLoading,
  fmtBRL,
  fmtNum,
  useAnaliseComercialAtual,
} from './_shared'

export function TopProcedimentosCard() {
  const q = useAnaliseComercialAtual()

  if (q.isLoading) return <WidgetLoading label="top procedimentos" />
  if (q.isError || !q.data) return <WidgetError label="Top procedimentos" />

  const data = q.data.top_procedimentos
  const consultasEfetivas = q.data.saude_agenda.efetivas
  const max = Math.max(...data.map((p) => p.qtd_executados), 1)
  const totalProcs = data.reduce((s, p) => s + p.qtd_executados, 0)

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full flex flex-col">
      <div className="flex items-center gap-2 mb-1">
        <TrendingUp size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Top procedimentos executados
        </span>
        <span className="ml-auto text-[10px] text-neutral-400">por volume</span>
      </div>
      <div className="text-[10px] text-neutral-400 mb-3">
        {fmtNum(totalProcs)} procedimentos em {fmtNum(consultasEfetivas)} consultas
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-6 text-center">Sem procedimentos no período.</div>
      ) : (
        <ul className="space-y-2.5 overflow-y-auto flex-1">
          {data.slice(0, 8).map((p, i) => (
            <li key={p.procedure_name + i}>
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
                  title={p.procedure_name}
                >
                  {p.procedure_name}
                </span>
                <span className="text-[12px] font-bold tabular-nums text-neutral-900 shrink-0">
                  {fmtNum(p.qtd_executados)}
                </span>
              </div>
              <div className="ml-7 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${i === 0 ? 'bg-amber-500' : 'bg-primary-500'}`}
                    style={{ width: `${(p.qtd_executados / max) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-neutral-500 w-10 text-right">
                  {p.pct_volume.toFixed(0)}%
                </span>
              </div>
              <div className="ml-7 mt-1 text-[10px] text-neutral-500 flex items-center gap-2 flex-wrap">
                <span>{fmtBRL(p.faturamento, true)}</span>
                <span className="text-neutral-400">·</span>
                <span>ticket {fmtBRL(p.ticket_medio, true)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
