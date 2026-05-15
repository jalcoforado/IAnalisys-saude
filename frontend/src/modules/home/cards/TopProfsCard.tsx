import { Crown, Trophy } from 'lucide-react'

import type { TopProfsSemanaSection } from '@/types/home'

import { fmtBRL, fmtDateShort } from './_utils'
import { CardBase, CardHeader, EmptyState } from './primitives'

export function TopProfsCard({ data }: { data: TopProfsSemanaSection }) {
  const max = Math.max(...data.items.map((i) => i.valor_aprovado), 1)
  return (
    <CardBase>
      <CardHeader
        icon={<Trophy size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-amber-500 to-orange-600"
        title="Top profissionais"
        subtitle={`Semana atual · ${fmtDateShort(data.inicio_iso)} → ${fmtDateShort(data.fim_iso)}`}
      />
      <div className="flex-1">
        {data.items.length === 0 ? (
          <EmptyState icon={<Trophy size={20} />} label="Sem orçamentos aprovados ainda nesta semana." />
        ) : (
          <div className="divide-y divide-neutral-100">
            {data.items.map((p, i) => {
              const widthPct = (p.valor_aprovado / max) * 100
              return (
                <div key={p.external_id} className="px-5 py-3">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    {i === 0 ? (
                      <span className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
                        <Crown size={12} />
                      </span>
                    ) : (
                      <span className="w-6 h-6 rounded-full bg-neutral-100 text-neutral-500 flex items-center justify-center text-[11px] font-bold shrink-0">
                        {i + 1}
                      </span>
                    )}
                    <span className="text-sm font-medium text-neutral-900 truncate flex-1" title={p.nome}>
                      {p.nome}
                    </span>
                    <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtBRL(p.valor_aprovado, true)}
                    </span>
                  </div>
                  <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${i === 0 ? 'bg-amber-500' : 'bg-primary-500'}`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-neutral-500 mt-1 text-right">
                    {p.qtd_aprovados} aprovados
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </CardBase>
  )
}
