import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Search, X } from 'lucide-react'

import { analiseService } from '@/services/analise.service'
import type { PrazoAuditItem } from '@/types/analise'

const fmtBRL = (n: number) =>
  new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 2,
  }).format(n)

const fmtDate = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y.slice(2)}`
}

interface BucketOption {
  label: string
  min?: number
  max?: number
}

const BUCKETS: BucketOption[] = [
  { label: 'Todos' },
  { label: '1x à vista', min: 1, max: 1 },
  { label: '2-3x', min: 2, max: 3 },
  { label: '4-6x', min: 4, max: 6 },
  { label: '7-12x', min: 7, max: 12 },
  { label: '13+', min: 13, max: 999 },
]

export interface PrazoAuditModalProps {
  year: number
  month: number
  initialBucket?: { min: number; max: number; label: string }
  onClose: () => void
}

export default function PrazoAuditModal({ year, month, initialBucket, onClose }: PrazoAuditModalProps) {
  const initialIdx = initialBucket
    ? BUCKETS.findIndex((b) => b.min === initialBucket.min && b.max === initialBucket.max)
    : 0
  const [bucketIdx, setBucketIdx] = useState(initialIdx >= 0 ? initialIdx : 0)
  const [search, setSearch] = useState('')

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const bucket = BUCKETS[bucketIdx]
  const q = useQuery({
    queryKey: ['prazos-detalhe', year, month, bucket.min, bucket.max],
    queryFn: () =>
      analiseService.financeiroPrazosDetalhe(year, month, {
        bucketMin: bucket.min,
        bucketMax: bucket.max,
        limit: 2000,
      }),
    staleTime: 30_000,
  })

  const filtered = useMemo(() => {
    if (!q.data) return [] as PrazoAuditItem[]
    const s = search.trim().toLowerCase()
    if (!s) return q.data.items
    return q.data.items.filter((it) =>
      (it.patient_name || '').toLowerCase().includes(s) ||
      String(it.treatment_external_id).includes(s) ||
      (it.professional_name || '').toLowerCase().includes(s),
    )
  }, [q.data, search])

  const sumFiltered = filtered.reduce((acc, it) => acc + (it.amount || 0), 0)

  return (
    <>
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
        aria-hidden
      />
      <aside
        className="fixed top-0 right-0 h-full w-full md:w-[80vw] lg:w-[75vw] max-w-[1200px] bg-white shadow-2xl z-50 flex flex-col"
        role="dialog"
        aria-modal
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-200 bg-gradient-to-r from-blue-700 to-indigo-700 text-white flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider font-bold opacity-80">
              Auditoria de prazos · {q.data?.period.label || '...'}
            </div>
            <div className="text-lg font-bold mt-0.5">
              Pagamentos dos orçamentos aprovados
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              Cada linha = uma parcela em <code className="font-mono">core_payments</code> ligada a um orçamento aprovado no mês.
            </div>
          </div>
          <button
            onClick={onClose}
            className="shrink-0 p-1.5 rounded-md hover:bg-white/20 transition"
            aria-label="Fechar"
          >
            <X size={20} />
          </button>
        </div>

        {/* Toolbar: filtros + busca */}
        <div className="px-5 py-3 border-b border-neutral-200 bg-neutral-50 flex flex-wrap gap-3 items-center">
          <div className="flex flex-wrap gap-1.5">
            {BUCKETS.map((b, idx) => {
              const active = idx === bucketIdx
              return (
                <button
                  key={b.label}
                  onClick={() => setBucketIdx(idx)}
                  className={`text-[11.5px] font-semibold px-2.5 py-1 rounded-md transition ${
                    active
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-white text-neutral-700 border border-neutral-200 hover:border-blue-300'
                  }`}
                >
                  {b.label}
                </button>
              )
            })}
          </div>
          <div className="flex-1 min-w-[200px] relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar paciente, profissional, ID…"
              className="w-full pl-8 pr-3 py-1.5 text-[12px] border border-neutral-200 rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-auto">
          {q.isLoading && (
            <div className="flex items-center justify-center py-20 text-neutral-400 text-sm">
              <Loader2 size={16} className="animate-spin mr-2" /> Carregando…
            </div>
          )}
          {q.isError && (
            <div className="m-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              Erro ao carregar listagem.
            </div>
          )}
          {q.data && filtered.length === 0 && (
            <div className="text-center py-16 text-sm text-neutral-500">
              Nenhuma parcela encontrada.
            </div>
          )}
          {q.data && filtered.length > 0 && (
            <table className="w-full text-[12px] tabular-nums">
              <thead className="bg-neutral-100 sticky top-0 z-10">
                <tr className="text-left text-neutral-600 uppercase tracking-wider">
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Paciente</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Profissional</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Orçamento</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Forma</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Parcela</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Vencimento</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px] text-right">Valor</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it, i) => (
                  <tr
                    key={`${it.treatment_external_id}-${it.payment_header_external_id}-${it.installment_number}-${i}`}
                    className="border-b border-neutral-100 hover:bg-blue-50/40"
                  >
                    <td className="px-3 py-2 align-top">
                      <div className="font-medium text-neutral-800">{it.patient_name || '—'}</div>
                      <div className="text-[10px] text-neutral-400 font-mono">#{it.treatment_external_id}</div>
                    </td>
                    <td className="px-3 py-2 align-top text-neutral-700">{it.professional_name || '—'}</td>
                    <td className="px-3 py-2 align-top">
                      <div className="text-neutral-700">{fmtDate(it.estimate_date)}</div>
                      {it.estimate_amount != null && (
                        <div className="text-[10.5px] text-neutral-500">{fmtBRL(it.estimate_amount)}</div>
                      )}
                    </td>
                    <td className="px-3 py-2 align-top text-neutral-700">{it.payment_form || '—'}</td>
                    <td className="px-3 py-2 align-top">
                      <span className={`inline-block px-1.5 py-0.5 rounded text-[10.5px] font-semibold ${
                        (it.installments_count || 1) === 1
                          ? 'bg-emerald-100 text-emerald-700'
                          : (it.installments_count || 1) <= 6
                            ? 'bg-amber-100 text-amber-700'
                            : 'bg-rose-100 text-rose-700'
                      }`}>
                        {it.installment_number ?? '—'}/{it.installments_count ?? '—'}
                      </span>
                    </td>
                    <td className="px-3 py-2 align-top text-neutral-700">{fmtDate(it.due_date)}</td>
                    <td className="px-3 py-2 align-top text-right font-semibold text-neutral-800">
                      {fmtBRL(it.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        {q.data && (
          <div className="px-5 py-3 border-t border-neutral-200 bg-neutral-50 flex flex-wrap items-center justify-between gap-3 text-[11.5px] text-neutral-700">
            <div>
              Exibindo <strong className="tabular-nums">{filtered.length}</strong>
              {filtered.length !== q.data.returned_count && <> de {q.data.returned_count}</>}
              {q.data.total_count > q.data.returned_count && (
                <span className="text-amber-600 ml-1">
                  (limite {q.data.limit} — total {q.data.total_count})
                </span>
              )}
              {' parcelas'}
            </div>
            <div className="font-semibold tabular-nums">
              Soma exibida: <span className="text-blue-700">{fmtBRL(sumFiltered)}</span>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}
