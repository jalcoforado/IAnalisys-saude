import { BarChart3 } from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  WidgetError,
  WidgetLoading,
  fmtBRL,
  useAnaliseFinanceiroAtual,
} from './_shared'

export function EvolucaoFaturamentoCard() {
  const q = useAnaliseFinanceiroAtual()

  if (q.isLoading) return <WidgetLoading label="evolução" />
  if (q.isError || !q.data) return <WidgetError label="Evolução 12m" />

  const formatted = q.data.evolution.map((p) => ({
    label: p.label,
    Faturamento: p.faturamento,
    Recebido: p.recebido,
  }))

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Evolução 12 meses
        </span>
        <span className="text-[11px] text-neutral-400 ml-2 truncate">
          Faturamento vs Recebido
        </span>
      </div>
      <div className="flex-1 min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={formatted} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#a3a3a3" />
            <YAxis
              tick={{ fontSize: 11 }}
              stroke="#a3a3a3"
              tickFormatter={(v) => `R$ ${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              formatter={(v) => fmtBRL(typeof v === 'number' ? v : Number(v))}
              contentStyle={{ fontSize: 12, borderRadius: 8 }}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line
              type="monotone"
              dataKey="Faturamento"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
            <Line
              type="monotone"
              dataKey="Recebido"
              stroke="#06b6d4"
              strokeWidth={2.5}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
