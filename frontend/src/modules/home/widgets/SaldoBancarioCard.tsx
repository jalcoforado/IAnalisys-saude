import { Banknote, Loader2, PiggyBank } from 'lucide-react'

import { useFinanceiroOverviewAtual } from './_shared'

const fmtBRL = (n: number) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(n)

export function SaldoBancarioCard() {
  const q = useFinanceiroOverviewAtual()

  if (q.isLoading) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl h-full flex items-center justify-center text-neutral-400 text-xs">
        <Loader2 size={16} className="animate-spin mr-2" /> Carregando…
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="bg-error-bg border border-error-border rounded-xl h-full flex items-center justify-center text-error-text text-xs px-4 text-center">
        Erro ao carregar saldo bancário.
      </div>
    )
  }

  const saldos = q.data.saldos_bancarios
  const total = saldos.saldo_bancos + saldos.saldo_caixinhas

  return (
    <div className="bg-white border border-primary-200 shadow-sm rounded-xl p-4 hover:shadow-md transition-shadow h-full flex flex-col">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-7 h-7 rounded-lg bg-primary-50 flex items-center justify-center shrink-0">
          <Banknote size={14} className="text-primary-600" />
        </span>
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Saldo consolidado
        </span>
      </div>

      <div className="text-2xl font-bold text-neutral-900 tabular-nums mb-2">
        {fmtBRL(total)}
      </div>

      <div className="space-y-1.5 text-[11px] mt-auto">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-neutral-600">
            <Banknote size={11} className="text-neutral-400" />
            Bancos ({saldos.qtd_bancos_ativos})
          </span>
          <span className="font-semibold tabular-nums text-neutral-900">
            {fmtBRL(saldos.saldo_bancos)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-neutral-600">
            <PiggyBank size={11} className="text-neutral-400" />
            Caixinhas ({saldos.qtd_caixinhas_ativas})
          </span>
          <span className="font-semibold tabular-nums text-neutral-900">
            {fmtBRL(saldos.saldo_caixinhas)}
          </span>
        </div>
      </div>

      {saldos.atualizado_em && (
        <div className="text-[10px] text-neutral-400 mt-2 pt-2 border-t border-neutral-100">
          Atualizado: {new Date(saldos.atualizado_em).toLocaleDateString('pt-BR')}
        </div>
      )}
    </div>
  )
}
