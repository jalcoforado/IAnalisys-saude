import { FileText, Target } from 'lucide-react'

import type { OrcamentosParadosSection } from '@/types/home'

import { fmtBRL, fmtNum } from './_utils'
import { Avatar, CardBase, CardHeader, EmptyState } from './primitives'

export function OrcamentosParadosCard({ data }: { data: OrcamentosParadosSection }) {
  return (
    <CardBase span={2}>
      <CardHeader
        icon={<FileText size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-purple-600 to-indigo-700"
        title="Orçamentos parados"
        subtitle={
          data.total > 0
            ? `${fmtNum(data.total)} aprovados sem retorno · total ${fmtBRL(data.valor_total)}`
            : 'Aprovados há 30-90 dias sem nova consulta'
        }
        badge={data.total > 0 ? 'Atenção' : undefined}
        badgeColor="bg-purple-100 text-purple-800"
      />
      <div className="flex-1 overflow-hidden">
        {data.items.length === 0 ? (
          <EmptyState icon={<Target size={20} />} label="Nenhum orçamento parado. Pipeline em dia." />
        ) : (
          <div className="divide-y divide-neutral-100 max-h-[360px] overflow-y-auto">
            {data.items.map((item) => (
              <div
                key={item.external_id}
                className="px-5 py-3 flex items-center gap-3 hover:bg-neutral-50/60"
              >
                <Avatar name={item.paciente_nome} color="bg-purple-50 text-purple-700" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2 mb-0.5">
                    <span className="text-sm font-medium text-neutral-900 truncate" title={item.paciente_nome}>
                      {item.paciente_nome}
                    </span>
                    <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtBRL(item.amount, true)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-neutral-500">
                    <span className="truncate">{item.profissional_nome || 'Sem profissional'}</span>
                    <span className="text-neutral-300">·</span>
                    <span className="text-warning-text font-medium">{item.dias_aprovado}d sem retorno</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </CardBase>
  )
}
