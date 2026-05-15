import { useState } from 'react'
import { ChevronDown, ChevronRight, Landmark, Vault } from 'lucide-react'

import type { ContaBancariaItem } from '@/types/financeiro'

import {
  WidgetError,
  WidgetLoading,
  fmtBRL,
  fmtTime,
  useFinanceiroOverviewAtual,
} from './_shared'

export function SaldoPorBancoCard() {
  const q = useFinanceiroOverviewAtual()
  const [showCaixinhas, setShowCaixinhas] = useState(false)
  const [showInativas, setShowInativas] = useState(false)

  if (q.isLoading) return <WidgetLoading label="contas bancárias" />
  if (q.isError || !q.data) return <WidgetError label="Distribuição por banco" />

  const data = q.data.saldos_bancarios
  if (data.qtd_contas_total === 0) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full">
        <div className="text-sm text-neutral-400 py-6 text-center">
          Nenhuma conta bancária cadastrada.
        </div>
      </div>
    )
  }

  const bancos = data.contas.filter((c) => c.ativo && c.is_banco_real)
  const caixinhas = data.contas.filter((c) => c.ativo && !c.is_banco_real)
  const inativas = data.contas.filter((c) => !c.ativo)

  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 shadow-sm h-full flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 mb-3">
        <Landmark size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Distribuição por banco
        </span>
        <span className="ml-auto text-[10px] text-neutral-400 truncate">
          atualizado {fmtTime(data.atualizado_em)}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto">
        {bancos.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-2 gap-2">
            {bancos.map((c) => (
              <ContaBancoItem key={c.external_id} c={c} />
            ))}
          </div>
        )}

        {caixinhas.length > 0 && (
          <div className="mt-3 pt-3 border-t border-neutral-100">
            <button
              type="button"
              onClick={() => setShowCaixinhas(!showCaixinhas)}
              className="rgl-no-drag text-[11px] text-amber-800 hover:text-amber-900 flex items-center gap-1.5"
            >
              {showCaixinhas ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              <Vault size={12} />
              <strong>{caixinhas.length}</strong> caixinha{caixinhas.length === 1 ? '' : 's'}{' '}
              <span className="text-amber-700">({fmtBRL(data.saldo_caixinhas, true)})</span>
            </button>
            {showCaixinhas && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                {caixinhas.map((c) => (
                  <ContaBancoItem key={c.external_id} c={c} />
                ))}
              </div>
            )}
          </div>
        )}

        {inativas.length > 0 && (
          <div className="mt-3 pt-3 border-t border-neutral-100">
            <button
              type="button"
              onClick={() => setShowInativas(!showInativas)}
              className="rgl-no-drag text-[11px] text-neutral-500 hover:text-neutral-700 flex items-center gap-1.5"
            >
              {showInativas ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
              {inativas.length} conta{inativas.length === 1 ? '' : 's'} inativa
              {inativas.length === 1 ? '' : 's'}
            </button>
            {showInativas && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                {inativas.map((c) => (
                  <ContaBancoItem key={c.external_id} c={c} muted />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function ContaBancoItem({ c, muted = false }: { c: ContaBancariaItem; muted?: boolean }) {
  const positive = c.saldo_atual >= 0
  return (
    <div
      className={`rounded-md border border-neutral-100 bg-neutral-50/50 px-3 py-2 ${
        muted ? 'opacity-60' : ''
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${
            c.is_banco_real ? 'bg-blue-500' : 'bg-amber-500'
          }`}
        />
        <span
          className="text-[11px] font-semibold text-neutral-800 truncate"
          title={c.nome}
        >
          {c.nome}
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={`text-[13px] font-bold tabular-nums ${
            positive ? 'text-neutral-900' : 'text-rose-700'
          }`}
        >
          {positive ? '' : '-'}
          {fmtBRL(Math.abs(c.saldo_atual))}
        </span>
        {c.tipo && (
          <span className="text-[9px] uppercase tracking-wide text-neutral-500 font-semibold shrink-0">
            {c.tipo.replace(/_/g, ' ')}
          </span>
        )}
      </div>
      {c.banco && (
        <div className="text-[10px] text-neutral-500 mt-0.5 truncate">{c.banco}</div>
      )}
    </div>
  )
}
