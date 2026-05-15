import { Phone } from 'lucide-react'

import {
  BUCKET_META,
  WidgetError,
  WidgetLoading,
  fmtBRL,
  useAnalisePacientesAtual,
} from './_shared'

export function ParaResgatarCard() {
  const q = useAnalisePacientesAtual()

  if (q.isLoading) return <WidgetLoading label="para resgatar" />
  if (q.isError || !q.data) return <WidgetError label="Para Resgatar" />

  const data = q.data.para_resgatar

  if (data.length === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full">
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
    <div className="bg-gradient-to-br from-rose-50 to-amber-50 border border-rose-200 rounded-xl p-4 shadow-sm h-full flex flex-col">
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
        Pacientes em <strong>risco</strong> ou <strong>inativos</strong> com LTV alto.
      </div>
      <div className="bg-white rounded-md overflow-hidden flex-1 overflow-y-auto">
        <table className="w-full text-[12px]">
          <thead className="bg-neutral-50 text-[10px] uppercase tracking-wider text-neutral-500 sticky top-0">
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
                  <td className="px-3 py-2 truncate max-w-[160px]" title={p.name || ''}>
                    {p.name || `#${p.external_id}`}
                  </td>
                  <td className="px-3 py-2 text-right font-bold tabular-nums text-amber-700">
                    {fmtBRL(p.ltv, true)}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.bg} ${meta.text}`}
                    >
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
