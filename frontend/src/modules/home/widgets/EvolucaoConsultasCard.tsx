import { useState } from 'react'
import { BarChart3 } from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  WidgetError,
  WidgetLoading,
  fmtNum,
  useAnaliseComercialAtual,
} from './_shared'

const COLORS = {
  Atendidas: '#10b981',
  Faltas: '#f43f5e',
  Canceladas: '#f97316',
  'Sem status': '#a3a3a3',
} as const

const ORDER = ['Atendidas', 'Faltas', 'Canceladas', 'Sem status'] as const

export function EvolucaoConsultasCard() {
  const q = useAnaliseComercialAtual()
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  if (q.isLoading) return <WidgetLoading label="evolução" />
  if (q.isError || !q.data) return <WidgetError label="Evolução de consultas" />

  const toggle = (key: string) =>
    setHidden((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  const formatted = q.data.evolution.map((p) => ({
    label: p.label,
    Atendidas: p.efetivas,
    Faltas: p.faltas,
    Canceladas: p.canceladas,
    'Sem status': p.indefinidas,
  }))

  const visible = ORDER.filter((k) => !hidden.has(k))
  const topKey = visible[visible.length - 1]

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Evolução da agenda — 12 meses
        </span>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={formatted} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#64748b' }} />
            <YAxis tick={{ fontSize: 10, fill: '#64748b' }} />
            <Tooltip
              formatter={(v) => fmtNum(typeof v === 'number' ? v : Number(v))}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11, cursor: 'pointer' }}
              onClick={(e) => toggle(String(e.dataKey ?? e.value))}
              formatter={(value) => (
                <span style={{ opacity: hidden.has(String(value)) ? 0.4 : 1 }}>{value}</span>
              )}
            />
            {ORDER.map((key) => (
              <Bar
                key={key}
                dataKey={key}
                stackId="agenda"
                fill={COLORS[key]}
                hide={hidden.has(key)}
                radius={topKey === key ? [3, 3, 0, 0] : undefined}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
