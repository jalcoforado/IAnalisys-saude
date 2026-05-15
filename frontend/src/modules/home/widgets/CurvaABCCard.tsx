/**
 * Curva ABC de procedimentos (Sub-PR 22.3.C parcial).
 *
 * Lista procedimentos ordenados por faturamento, com barra de % acumulado
 * destacando as classes A/B/C (regra clássica de Pareto):
 *   - A: top que acumula até 80% do faturamento (poucos · alto valor)
 *   - B: do que vai de 80% a 95%
 *   - C: cauda longa (95-100%)
 *
 * Difere do `top_procedimentos`: aquele mostra top 5 absoluto por volume.
 * Curva ABC ajuda a ver concentração — em que procedimentos a clínica vive.
 */
import { useAnaliseComercialAtual, WidgetLoading, WidgetError, fmtBRL, fmtNum } from './_shared'

type Classe = 'A' | 'B' | 'C'

function classify(acumPct: number): Classe {
  if (acumPct <= 80) return 'A'
  if (acumPct <= 95) return 'B'
  return 'C'
}

const CLASSE_STYLES: Record<Classe, { bg: string; text: string; border: string }> = {
  A: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-300' },
  B: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-300' },
  C: { bg: 'bg-neutral-100', text: 'text-neutral-600', border: 'border-neutral-300' },
}

export function CurvaABCCard() {
  const q = useAnaliseComercialAtual()
  if (q.isLoading) return <WidgetLoading label="Curva ABC procedimentos" />
  if (q.isError || !q.data) return <WidgetError label="Curva ABC procedimentos" />

  const procedimentos = q.data.top_procedimentos || []
  if (procedimentos.length === 0) {
    return (
      <section className="bg-white border border-neutral-200 rounded-xl p-4 h-full flex items-center justify-center text-xs text-neutral-400">
        Sem procedimentos executados no período.
      </section>
    )
  }

  // Procedimentos vêm ordenados por volume (qtd_executados desc) do backend;
  // pra Curva ABC precisamos ordenar por faturamento desc.
  const sorted = [...procedimentos].sort((a, b) => (b.faturamento || 0) - (a.faturamento || 0))
  const totalFat = sorted.reduce((sum, p) => sum + (p.faturamento || 0), 0)

  let acumValor = 0
  const enriched = sorted.map((p) => {
    acumValor += p.faturamento || 0
    const acumPct = totalFat > 0 ? (acumValor / totalFat) * 100 : 0
    const pctIndividual = totalFat > 0 ? ((p.faturamento || 0) / totalFat) * 100 : 0
    return { ...p, acumPct, pctIndividual, classe: classify(acumPct) }
  })

  const counts = { A: 0, B: 0, C: 0 }
  enriched.forEach((p) => { counts[p.classe] += 1 })

  return (
    <section className="bg-white border border-neutral-200 rounded-xl h-full flex flex-col overflow-hidden">
      <header className="px-4 pt-3 pb-2 border-b border-neutral-100">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-neutral-900">Curva ABC procedimentos</h3>
            <p className="text-[11px] text-neutral-500">
              Concentração do faturamento · {fmtBRL(totalFat, true)} total
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-[10px]">
            {(['A', 'B', 'C'] as const).map((c) => (
              <span
                key={c}
                className={`px-1.5 py-0.5 rounded font-semibold ${CLASSE_STYLES[c].bg} ${CLASSE_STYLES[c].text}`}
              >
                {c}: {counts[c]}
              </span>
            ))}
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto">
        <ul className="divide-y divide-neutral-100">
          {enriched.map((p) => {
            const styles = CLASSE_STYLES[p.classe]
            return (
              <li key={p.procedure_name} className="px-4 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`inline-flex items-center justify-center w-5 h-5 rounded text-[10px] font-bold border ${styles.bg} ${styles.text} ${styles.border}`}
                  >
                    {p.classe}
                  </span>
                  <span className="text-xs text-neutral-700 truncate flex-1" title={p.procedure_name}>
                    {p.procedure_name}
                  </span>
                  <span className="text-xs text-neutral-900 tabular-nums shrink-0">
                    {fmtBRL(p.faturamento, true)}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[10px] text-neutral-500">
                  <div className="flex-1 bg-neutral-100 rounded-full h-1 overflow-hidden">
                    <div
                      className={styles.bg.replace('bg-', 'bg-').replace('-50', '-500')}
                      style={{ width: `${Math.min(100, p.pctIndividual)}%`, height: '100%' }}
                    />
                  </div>
                  <span className="tabular-nums w-12 text-right">
                    {p.pctIndividual.toFixed(1)}%
                  </span>
                  <span className="tabular-nums w-12 text-right text-neutral-400">
                    Σ{p.acumPct.toFixed(0)}%
                  </span>
                  <span className="tabular-nums w-12 text-right text-neutral-400 hidden sm:inline">
                    {fmtNum(p.qtd_executados)}u
                  </span>
                </div>
              </li>
            )
          })}
        </ul>
      </div>
    </section>
  )
}
