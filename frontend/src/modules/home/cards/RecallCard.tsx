import { Clock, Phone, Sparkles } from 'lucide-react'

import type { RecallItem, RecallSection } from '@/types/home'

import { fmtNum } from './_utils'
import { Avatar, CardBase, CardHeader, EmptyState } from './primitives'

export function RecallCard({ data }: { data: RecallSection }) {
  return (
    <CardBase span={2}>
      <CardHeader
        icon={<Phone size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-amber-500 to-amber-700"
        title="Pacientes pra ligar"
        subtitle={`${fmtNum(data.items.length)} de ${fmtNum(data.total_elegiveis)} candidatos · vinham regularmente e estão atrasados`}
        badge="Oportunidades"
        badgeColor="bg-amber-100 text-amber-800"
      />
      <div className="flex-1 overflow-hidden">
        {data.items.length === 0 ? (
          <EmptyState icon={<Sparkles size={20} />} label="Nenhum paciente elegível a recall agora." />
        ) : (
          <div className="divide-y divide-neutral-100 max-h-[420px] overflow-y-auto">
            {data.items.map((item) => (
              <RecallRow key={item.paciente_external_id} item={item} />
            ))}
          </div>
        )}
      </div>
    </CardBase>
  )
}

function RecallRow({ item }: { item: RecallItem }) {
  const urgent = item.atraso_relativo >= 3
  const moderate = item.atraso_relativo >= 2 && !urgent
  const urgencyColor = urgent
    ? 'bg-error-bg text-error-text'
    : moderate
    ? 'bg-warning-bg text-warning-text'
    : 'bg-info-bg text-info-text'

  return (
    <div className="px-5 py-3 flex items-center gap-3 hover:bg-neutral-50/60 transition-colors">
      <Avatar name={item.paciente_nome} color="bg-amber-50 text-amber-700" />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2 mb-0.5">
          <span className="text-sm font-medium text-neutral-900 truncate" title={item.paciente_nome}>
            {item.paciente_nome}
          </span>
          <span className={`text-[10px] uppercase tracking-wide font-bold px-1.5 py-0.5 rounded shrink-0 ${urgencyColor}`}>
            {item.atraso_relativo.toFixed(1)}× atrasado
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-neutral-500">
          <span className="flex items-center gap-1">
            <Clock size={10} /> {item.dias_desde_ultima}d sem visita
          </span>
          <span className="text-neutral-300">·</span>
          <span>vinha a cada {item.intervalo_medio_dias}d</span>
          <span className="text-neutral-300">·</span>
          <span>{item.qtd_consultas} consultas</span>
        </div>
      </div>
    </div>
  )
}
