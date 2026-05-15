import { FileText } from 'lucide-react'

import {
  WidgetError,
  WidgetLoading,
  fmtBRL,
  fmtNum,
  fmtPct,
  useAnaliseFinanceiroAtual,
} from './_shared'

export function FunilOrcamentosCard() {
  const q = useAnaliseFinanceiroAtual()

  if (q.isLoading) return <WidgetLoading label="funil" />
  if (q.isError || !q.data) return <WidgetError label="Funil de orçamentos" />

  const data = q.data.funil
  const max = Math.max(data.gerados_amount, data.aprovados_amount, data.pagos_amount, 1)
  const stages = [
    { label: 'Gerados',   qty: data.gerados_qty,   amount: data.gerados_amount,   color: 'bg-blue-500' },
    { label: 'Aprovados', qty: data.aprovados_qty, amount: data.aprovados_amount, color: 'bg-emerald-500' },
    { label: 'Pagos',     qty: data.pagos_qty,     amount: data.pagos_amount,     color: 'bg-cyan-500' },
  ]

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full flex flex-col">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Funil de Orçamentos
        </span>
      </div>
      <div className="space-y-2">
        {stages.map((s) => {
          const pct = (s.amount / max) * 100
          return (
            <div key={s.label}>
              <div className="flex items-center justify-between mb-1 text-[12px]">
                <span className="font-semibold text-neutral-700">{s.label}</span>
                <span className="text-neutral-500">
                  <span className="font-bold text-neutral-900">{fmtNum(s.qty)}</span> orç. ·{' '}
                  <span className="font-bold text-neutral-900">{fmtBRL(s.amount, true)}</span>
                </span>
              </div>
              <div className="h-3 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className={`h-full ${s.color} rounded-full transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>
      <div className="mt-3 pt-3 border-t border-neutral-100 grid grid-cols-2 gap-3 text-[12px]">
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-400">Conversão (R$)</div>
          <div className="font-bold text-emerald-700 text-lg">
            {data.conversao_aprovacao_valor_pct.toFixed(1)}%
          </div>
          {data.aprovacao_valor_mom_pct !== null && (
            <div className={`text-[10px] ${data.aprovacao_valor_mom_pct >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {fmtPct(data.aprovacao_valor_mom_pct)} MoM
            </div>
          )}
        </div>
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide text-neutral-400">Pagamento (R$)</div>
          <div className="font-bold text-cyan-700 text-lg">
            {data.conversao_pagamento_valor_pct.toFixed(1)}%
          </div>
          <div className="text-[10px] text-neutral-400">dos aprovados</div>
        </div>
      </div>
    </div>
  )
}
