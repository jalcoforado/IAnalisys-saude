import { AlertTriangle, TrendingUp } from 'lucide-react'

import type { InadimplenciaCriticaSection } from '@/types/home'

import { fmtBRL, fmtNum } from './_utils'
import { CardBase, CardHeader, EmptyState } from './primitives'

export function InadimplenciaCriticaCard({ data }: { data: InadimplenciaCriticaSection }) {
  return (
    <CardBase>
      <CardHeader
        icon={<AlertTriangle size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-error-DEFAULT to-red-800"
        title="Inadimplência crítica"
        subtitle={
          data.total > 0
            ? `${fmtNum(data.total)} parcelas · ${fmtBRL(data.valor_total)}`
            : 'Vencidas há +60d e valor +R$ 500'
        }
        badge={data.total > 5 ? 'Alta' : data.total > 0 ? 'Atenção' : undefined}
        badgeColor={data.total > 5 ? 'bg-error-bg text-error-text' : 'bg-warning-bg text-warning-text'}
      />
      <div className="flex-1">
        {data.items.length === 0 ? (
          <EmptyState icon={<TrendingUp size={20} />} label="Sem inadimplência crítica. 🎯" />
        ) : (
          <div className="divide-y divide-neutral-100 max-h-[360px] overflow-y-auto">
            {data.items.map((item) => (
              <div key={item.parcela_external_id} className="px-5 py-3">
                <div className="flex items-baseline justify-between gap-2 mb-0.5">
                  <span className="text-sm font-medium text-neutral-900 truncate" title={item.pessoa_nome}>
                    {item.pessoa_nome}
                  </span>
                  <span className="text-sm font-bold tabular-nums text-error-text shrink-0">
                    {fmtBRL(item.valor_em_aberto, true)}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-neutral-500">
                  <span className="text-error-text font-semibold">{item.dias_atraso}d atraso</span>
                  <span className="text-neutral-300">·</span>
                  <span className="truncate">{item.categoria || 'Sem categoria'}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </CardBase>
  )
}
