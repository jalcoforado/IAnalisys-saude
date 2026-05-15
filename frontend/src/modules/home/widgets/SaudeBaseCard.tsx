import { Activity } from 'lucide-react'

import {
  BUCKET_META,
  WidgetError,
  WidgetLoading,
  fmtNum,
  useAnalisePacientesAtual,
} from './_shared'

export function SaudeBaseCard() {
  const q = useAnalisePacientesAtual()

  if (q.isLoading) return <WidgetLoading label="saúde da base" />
  if (q.isError || !q.data) return <WidgetError label="Saúde da base" />

  const data = q.data.saude_base
  const segments = [
    { key: 'ativo',      qtd: data.ativo_qty,      pct: data.ativo_pct      },
    { key: 'em_risco',   qtd: data.em_risco_qty,   pct: data.em_risco_pct   },
    { key: 'inativo',    qtd: data.inativo_qty,    pct: data.inativo_pct    },
    { key: 'perdido',    qtd: data.perdido_qty,    pct: data.perdido_pct    },
    { key: 'sem_visita', qtd: data.sem_visita_qty, pct: data.sem_visita_pct },
  ].filter((s) => s.qtd > 0)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm overflow-hidden h-full flex flex-col">
      <header className="px-5 py-4 flex items-start justify-between gap-4 flex-wrap border-b border-neutral-100">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Activity size={14} className="text-neutral-600" />
            <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
              Saúde da base
            </span>
          </div>
          <div className="text-sm text-neutral-700 mt-1">
            <strong className="text-neutral-900">{fmtNum(data.total)}</strong> pacientes ·
            ativos{' '}
            <strong className="text-emerald-700 tabular-nums">
              {data.ativo_pct.toFixed(1)}%
            </strong>
          </div>
        </div>
        <div className="text-[10px] text-neutral-500 max-w-xs leading-snug">
          <strong>ativo</strong> &lt;90d · <strong>em risco</strong> 90-180d ·{' '}
          <strong>inativo</strong> 180-365d · <strong>perdido</strong> &gt;365d.
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
                    <span className={`text-[14px] font-bold tabular-nums ${meta.text}`}>
                      {fmtNum(s.qtd)}
                    </span>
                    <span className="text-[10px] text-neutral-500 tabular-nums">
                      {s.pct.toFixed(1)}%
                    </span>
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
