/**
 * Top Profissionais por Faturamento (mês atual) — Sub-PR 22.3.C parcial.
 *
 * Difere do widget `top_profs`:
 *   - top_profs: top profissionais por orçamentos APROVADOS na SEMANA
 *   - este: top profissionais por FATURAMENTO REAL (recebido) do MÊS
 *
 * Usa `useAnaliseFinanceiroAtual()` que já está cacheado pelos widgets KPI
 * financeiros (TanStack dedupe → sem fetch extra).
 */
import { Trophy } from 'lucide-react'
import { useAnaliseFinanceiroAtual, WidgetLoading, WidgetError, fmtBRL, fmtPct } from './_shared'

export function TopProfsFaturamentoCard() {
  const q = useAnaliseFinanceiroAtual()
  if (q.isLoading) return <WidgetLoading label="Top profissionais (faturamento)" />
  if (q.isError || !q.data) return <WidgetError label="Top profissionais (faturamento)" />

  const profs = q.data.top_profissionais || []
  if (profs.length === 0) {
    return (
      <section className="bg-white border border-neutral-200 rounded-xl p-4 h-full flex items-center justify-center text-xs text-neutral-400">
        Sem faturamento por profissional no período.
      </section>
    )
  }

  const top = profs.slice(0, 5)
  const maxFat = Math.max(...top.map((p) => p.faturamento || 0), 1)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl h-full flex flex-col overflow-hidden">
      <header className="px-4 pt-3 pb-2 border-b border-neutral-100 flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">Top profissionais por faturamento</h3>
          <p className="text-[11px] text-neutral-500">Mês atual · ordenado por valor recebido</p>
        </div>
        <Trophy size={16} className="text-amber-500" />
      </header>
      <ul className="flex-1 overflow-y-auto divide-y divide-neutral-100">
        {top.map((p, idx) => {
          const widthPct = maxFat > 0 ? Math.max(2, ((p.faturamento || 0) / maxFat) * 100) : 0
          const medalColor =
            idx === 0 ? 'bg-amber-100 text-amber-700' :
            idx === 1 ? 'bg-neutral-200 text-neutral-700' :
            idx === 2 ? 'bg-orange-100 text-orange-700' :
            'bg-neutral-100 text-neutral-500'
          return (
            <li key={p.professional_external_id} className="px-4 py-2.5">
              <div className="flex items-center gap-2 mb-1.5">
                <span
                  className={`inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${medalColor}`}
                >
                  {idx + 1}
                </span>
                <span className="text-xs font-medium text-neutral-800 truncate flex-1" title={p.nome}>
                  {p.nome}
                </span>
                <span className="text-xs text-neutral-900 font-semibold tabular-nums shrink-0">
                  {fmtBRL(p.faturamento, true)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-neutral-100 rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full transition-all"
                    style={{ width: `${widthPct}%` }}
                  />
                </div>
                <span className="text-[10px] tabular-nums text-neutral-500 w-10 text-right">
                  {(p.pct_total || 0).toFixed(0)}%
                </span>
              </div>
              <div className="flex items-center gap-3 mt-1 text-[10px] text-neutral-400 tabular-nums">
                <span>conv. valor {fmtPct(p.taxa_conversao_valor_pct)}</span>
                <span>·</span>
                <span>ticket {fmtBRL(p.ticket_medio, true)}</span>
                <span>·</span>
                <span>{p.qtd_aprovados} aprovados</span>
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
