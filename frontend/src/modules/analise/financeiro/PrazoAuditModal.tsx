/**
 * Modal de auditoria do card "Prazo de Recebimento".
 *
 * Reformulado em 2026-05-09: 1 linha por ORÇAMENTO (era 1 por parcela).
 * Cada orçamento aprovado no mês exibe contratado / lançado / pago + status
 * financeiro. Linha clicável expande as parcelas do plano de pagamento.
 *
 * Os 5 status são gerados pelo backend (ver _classify_orcamento). Na prática
 * com Clinicorp Parente: parcelas só são lançadas quando pagas, então
 * "nao_pago" e "parcial" tendem a ficar zerados — são pré-existentes pra
 * compatibilidade com clínicas que registram cobrança antes do recebimento.
 */
import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  CheckCircle2, ChevronDown, ChevronRight, Clock, Info, Loader2,
  Search, X,
} from 'lucide-react'

import { analiseService } from '@/services/analise.service'
import type { OrcamentoParcela, OrcamentoStatus, OrcamentoStatusItem } from '@/types/analise'

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000_000)
    return `R$ ${(n / 1_000_000).toFixed(2)}M`
  if (compact && Math.abs(n) >= 1_000)
    return `R$ ${(n / 1_000).toFixed(0)}k`
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 2,
  }).format(n)
}

const fmtDate = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y.slice(2)}`
}

// Clinicorp numera parcelas a partir de 0 (0/4, 1/4, 2/4, 3/4 num plano de 4x).
// Pra leitura humana exibimos 1-based (1/4, 2/4, 3/4, 4/4). `installments_count`
// já vem correto na fonte (não precisa ajustar).
const fmtParcela = (
  n: number | null | undefined,
  total: number | null | undefined,
) => {
  const num = n != null ? n + 1 : null
  return `${num ?? '—'}/${total ?? '—'}`
}

// Metadados de cada status — label, cor, descrição. Únicas instâncias da
// taxonomia (frontend e backend devem estar alinhados nesta ordem).
type StatusMeta = {
  label: string
  short: string
  badge: string
  ring: string
  description: string
}

const STATUS_META: Record<OrcamentoStatus, StatusMeta> = {
  pago_integral: {
    label: 'Pago integral',
    short: 'Pago',
    badge: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    ring: 'ring-emerald-200',
    description: 'Pago = contratado. Cobertura total do orçamento.',
  },
  pago_lancado: {
    label: 'Pago do lançado',
    short: 'Pago do lançado',
    badge: 'bg-cyan-100 text-cyan-700 border-cyan-200',
    ring: 'ring-cyan-200',
    description: 'Pagou tudo que foi lançado, mas o contratado é maior — falta a Clinicorp lançar/cobrar o restante.',
  },
  parcial: {
    label: 'Parcial',
    short: 'Parcial',
    badge: 'bg-amber-100 text-amber-700 border-amber-200',
    ring: 'ring-amber-200',
    description: 'Recebeu parte mas há parcelas pendentes.',
  },
  nao_pago: {
    label: 'Não pago',
    short: 'Não pago',
    badge: 'bg-rose-100 text-rose-700 border-rose-200',
    ring: 'ring-rose-200',
    description: 'Tem parcelas lançadas mas zero recebido.',
  },
  sem_parcelas: {
    label: 'Sem parcelas',
    short: 'Sem parcelas',
    badge: 'bg-neutral-200 text-neutral-700 border-neutral-300',
    ring: 'ring-neutral-300',
    description: 'Orçamento aprovado mas a Clinicorp ainda não registrou nenhuma parcela.',
  },
}

// Ordem de exibição das tabs — lê pior → melhor pra puxar atenção pra problemas
const STATUS_ORDER: OrcamentoStatus[] = [
  'sem_parcelas', 'nao_pago', 'parcial', 'pago_lancado', 'pago_integral',
]

export interface PrazoAuditModalProps {
  year: number
  month: number
  initialBucket?: { min: number; max: number; label: string }  // mantido por compat — ignorado
  onClose: () => void
}

export default function PrazoAuditModal({ year, month, onClose }: PrazoAuditModalProps) {
  const [statusFilter, setStatusFilter] = useState<OrcamentoStatus | 'all'>('all')
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const q = useQuery({
    queryKey: ['orcamentos-status', year, month],
    queryFn: () => analiseService.financeiroOrcamentosStatus(year, month),
    staleTime: 30_000,
  })

  const filtered = useMemo(() => {
    if (!q.data) return [] as OrcamentoStatusItem[]
    let items = q.data.items
    if (statusFilter !== 'all') {
      items = items.filter((it) => it.status === statusFilter)
    }
    const s = search.trim().toLowerCase()
    if (s) {
      items = items.filter((it) =>
        (it.patient_name || '').toLowerCase().includes(s) ||
        (it.professional_name || '').toLowerCase().includes(s) ||
        String(it.treatment_external_id).includes(s),
      )
    }
    return items
  }, [q.data, statusFilter, search])

  const sumFiltered = filtered.reduce(
    (acc, it) => ({
      contratado: acc.contratado + it.contratado,
      pago: acc.pago + it.pago,
    }),
    { contratado: 0, pago: 0 },
  )

  const toggle = (tid: number) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(tid)) next.delete(tid)
      else next.add(tid)
      return next
    })

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} aria-hidden />
      <aside
        className="fixed top-0 right-0 h-full w-full md:w-[88vw] lg:w-[85vw] max-w-[1400px] bg-white shadow-2xl z-50 flex flex-col"
        role="dialog"
        aria-modal
      >
        {/* Header */}
        <div className="px-5 py-4 border-b border-neutral-200 bg-gradient-to-r from-blue-700 to-indigo-700 text-white flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider font-bold opacity-80">
              Auditoria · {q.data?.period.label || '...'}
            </div>
            <div className="text-lg font-bold mt-0.5">
              Status financeiro dos orçamentos aprovados
            </div>
            <div className="text-xs opacity-80 mt-0.5">
              1 linha por orçamento. Clique pra expandir e ver as parcelas do plano de pagamento.
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

        {/* Totais agregados (sempre da resposta inteira, não do filtro) */}
        {q.data && (
          <div className="px-5 py-3 border-b border-neutral-200 bg-neutral-50 grid grid-cols-3 gap-3">
            <TotalCard label="Contratado" value={q.data.totais_contratado} hint={`${q.data.items.length} orçamentos aprovados`} />
            <TotalCard label="Lançado em parcelas" value={q.data.totais_lancado} hint="o que a Clinicorp já registrou" />
            <TotalCard label="Pago (recebido)" value={q.data.totais_pago} hint="parcelas com is_received=1" emphasized />
          </div>
        )}

        {/* Banner — limite de visibilidade da API Clinicorp.
            Pagamentos parados em fase 1-3 (recebidos mas não conferidos no
            financeiro) NÃO aparecem aqui — a API só expõe pagamentos que
            chegaram à Fase 4. Ver memória `reference_clinicorp_payment_phases`. */}
        <div className="px-5 py-2.5 border-b border-amber-200 bg-amber-50/70 flex items-start gap-2 text-[11px] text-amber-900 leading-snug">
          <Info size={14} className="text-amber-600 shrink-0 mt-0.5" />
          <div>
            A Clinicorp marca pagamentos em <strong>4 fases</strong> (Lançado → Confirmado → Recebido → <strong>Conferido</strong>).
            A API só retorna parcelas que passaram pela <strong>Fase 4</strong> — pagamentos já recebidos mas pendentes de conciliação financeira na UI da Clinicorp não aparecem aqui.
            Se há gap entre <em>Contratado</em> e <em>Lançado</em>, parte pode ser plano parcial e parte pode ser conferência pendente.
          </div>
        </div>

        {/* Toolbar: tabs por status + busca */}
        <div className="px-5 py-3 border-b border-neutral-200 bg-white flex flex-wrap gap-3 items-center">
          <div className="flex flex-wrap gap-1.5">
            <StatusTab
              label="Todos"
              count={q.data?.items.length ?? 0}
              active={statusFilter === 'all'}
              onClick={() => setStatusFilter('all')}
              color="bg-blue-600 text-white"
            />
            {STATUS_ORDER.map((s) => {
              const meta = STATUS_META[s]
              const count = q.data?.contagens[s] ?? 0
              if (count === 0 && statusFilter !== s) return null
              return (
                <StatusTab
                  key={s}
                  label={meta.short}
                  count={count}
                  active={statusFilter === s}
                  onClick={() => setStatusFilter(s)}
                  color={meta.badge}
                />
              )
            })}
          </div>
          <div className="flex-1 min-w-[200px] relative">
            <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar paciente, profissional, ID do orçamento…"
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
              Nenhum orçamento encontrado com esse filtro.
            </div>
          )}
          {q.data && filtered.length > 0 && (
            <table className="w-full text-[12px] tabular-nums">
              <thead className="bg-neutral-100 sticky top-0 z-10">
                <tr className="text-left text-neutral-600 uppercase tracking-wider">
                  <th className="px-3 py-2 font-semibold text-[10.5px] w-6"></th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Orçamento</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Paciente</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Profissional</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Data</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px] text-right">Contratado</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px] text-right">Lançado</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px] text-right">Pago</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px] text-right">% contratado</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px] text-right">% lançado</th>
                  <th className="px-3 py-2 font-semibold text-[10.5px]">Status</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((it) => {
                  const meta = STATUS_META[it.status]
                  const isOpen = expanded.has(it.treatment_external_id)
                  return (
                    <>
                      <tr
                        key={it.treatment_external_id}
                        className="border-b border-neutral-100 hover:bg-blue-50/40 cursor-pointer"
                        onClick={() => toggle(it.treatment_external_id)}
                      >
                        <td className="px-3 py-2 align-top text-neutral-400">
                          {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </td>
                        <td className="px-3 py-2 align-top text-neutral-700 font-mono text-[11px]">
                          #{it.treatment_external_id}
                        </td>
                        <td className="px-3 py-2 align-top">
                          <div className="font-medium text-neutral-800">{it.patient_name || '—'}</div>
                        </td>
                        <td className="px-3 py-2 align-top text-neutral-700">{it.professional_name || '—'}</td>
                        <td className="px-3 py-2 align-top text-neutral-700">{fmtDate(it.estimate_date)}</td>
                        <td className="px-3 py-2 align-top text-right font-semibold text-neutral-800">
                          {fmtBRL(it.contratado)}
                        </td>
                        <td className="px-3 py-2 align-top text-right text-neutral-700">
                          {fmtBRL(it.lancado)}
                        </td>
                        <td className="px-3 py-2 align-top text-right font-semibold text-emerald-700">
                          {fmtBRL(it.pago)}
                        </td>
                        <td className="px-3 py-2 align-top text-right text-neutral-700">
                          {it.pct_pago_contratado.toFixed(0)}%
                        </td>
                        <td className="px-3 py-2 align-top text-right text-neutral-700">
                          {it.pct_pago_lancado.toFixed(0)}%
                        </td>
                        <td className="px-3 py-2 align-top">
                          <span
                            className={`inline-block px-1.5 py-0.5 rounded border text-[10.5px] font-semibold ${meta.badge}`}
                            title={meta.description}
                          >
                            {meta.short}
                          </span>
                          {it.parcelas_vencidas_qty > 0 && (
                            <span className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] font-bold text-rose-700">
                              <Clock size={10} /> {it.parcelas_vencidas_qty} venc.
                            </span>
                          )}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr key={`${it.treatment_external_id}-detail`}>
                          <td colSpan={11} className="px-3 py-3 bg-neutral-50 border-b border-neutral-100">
                            <ParcelasDetail item={it} />
                          </td>
                        </tr>
                      )}
                    </>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer */}
        {q.data && (
          <div className="px-5 py-3 border-t border-neutral-200 bg-neutral-50 flex flex-wrap items-center justify-between gap-3 text-[11.5px] text-neutral-700">
            <div>
              Exibindo <strong className="tabular-nums">{filtered.length}</strong>
              {filtered.length !== q.data.items.length && <> de {q.data.items.length}</>}
              {' orçamentos'}
            </div>
            <div className="font-semibold tabular-nums">
              Soma exibida: contratado <span className="text-blue-700">{fmtBRL(sumFiltered.contratado)}</span>
              {' · '}pago <span className="text-emerald-700">{fmtBRL(sumFiltered.pago)}</span>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}

// ── Sub-componentes ───────────────────────────────────────────

function TotalCard({
  label, value, hint, emphasized,
}: { label: string; value: number; hint: string; emphasized?: boolean }) {
  return (
    <div className={`rounded-md border px-3 py-2 ${
      emphasized ? 'bg-emerald-50 border-emerald-200' : 'bg-white border-neutral-200'
    }`}>
      <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-500">{label}</div>
      <div className={`text-lg font-bold tabular-nums ${emphasized ? 'text-emerald-800' : 'text-neutral-900'}`}>
        {fmtBRL(value)}
      </div>
      <div className="text-[10px] text-neutral-500 leading-tight">{hint}</div>
    </div>
  )
}

function StatusTab({
  label, count, active, onClick, color,
}: {
  label: string; count: number; active: boolean
  onClick: () => void; color: string
}) {
  return (
    <button
      onClick={onClick}
      className={`text-[11.5px] font-semibold px-2.5 py-1 rounded-md transition border ${
        active
          ? `${color} shadow-sm border-transparent`
          : 'bg-white text-neutral-700 border-neutral-200 hover:border-blue-300'
      }`}
    >
      {label}
      <span className={`ml-1.5 tabular-nums ${active ? 'opacity-90' : 'text-neutral-500'}`}>
        {count}
      </span>
    </button>
  )
}

// 4 bolinhas das fases do ciclo de pagamento Clinicorp.
// Verde se concluída, cinza se pendente. Hover em cada bolinha mostra o nome
// da fase. Como a API só retorna fase 4, hoje todas costumam estar verdes —
// o componente fica como referência visual da taxonomia (e fica preparado
// caso no futuro busquemos pagamentos pré-conferência via JWT da UI).
function FasesPagamento({ p }: { p: OrcamentoParcela }) {
  const fases = [
    { n: 1, label: 'Lançada', done: true },
    { n: 2, label: 'Confirmada', done: p.is_confirmed },
    { n: 3, label: 'Recebida', done: p.is_received },
    { n: 4, label: 'Conferida', done: p.is_conferida },
  ]
  return (
    <div className="inline-flex items-center gap-0.5">
      {fases.map((f, i) => (
        <div key={f.n} className="flex items-center">
          <span
            className={`w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center ${
              f.done
                ? 'bg-emerald-500 text-white'
                : 'bg-neutral-200 text-neutral-400'
            }`}
            title={`${f.n} — ${f.label}${f.done ? ' ✓' : ' (pendente)'}`}
          >
            {f.n}
          </span>
          {i < fases.length - 1 && (
            <span className={`w-1.5 h-px ${f.done && fases[i + 1].done ? 'bg-emerald-400' : 'bg-neutral-200'}`} />
          )}
        </div>
      ))}
    </div>
  )
}

function ParcelasDetail({ item }: { item: OrcamentoStatusItem }) {
  if (item.parcelas.length === 0) {
    return (
      <div className="text-[12px] text-neutral-600 px-2">
        Esse orçamento ainda não tem nenhuma parcela registrada em <code className="font-mono">core_payments</code>.
        Pode ser plano lançado em partes (Clinicorp registra parcelas conforme o paciente paga)
        OU pagamentos parados em fase 1-3 esperando conferência financeira na UI da Clinicorp.
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <div className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
        {item.parcelas.length} parcela{item.parcelas.length > 1 ? 's' : ''} no plano
      </div>
      <table className="w-full text-[11.5px] tabular-nums bg-white rounded-md border border-neutral-200">
        <thead>
          <tr className="text-left text-neutral-500 uppercase tracking-wider border-b border-neutral-200">
            <th className="px-3 py-1.5 font-semibold text-[10px]">Parcela</th>
            <th className="px-3 py-1.5 font-semibold text-[10px]">Forma</th>
            <th className="px-3 py-1.5 font-semibold text-[10px]">Vencimento</th>
            <th className="px-3 py-1.5 font-semibold text-[10px]">Recebido em</th>
            <th className="px-3 py-1.5 font-semibold text-[10px] text-right">Valor</th>
            <th className="px-3 py-1.5 font-semibold text-[10px]">Fase</th>
            <th className="px-3 py-1.5 font-semibold text-[10px]">Situação</th>
          </tr>
        </thead>
        <tbody>
          {item.parcelas.map((p) => (
            <tr key={p.payment_external_id} className="border-b border-neutral-100 last:border-0">
              <td className="px-3 py-1.5 text-neutral-700">
                {fmtParcela(p.installment_number, p.installments_count)}
              </td>
              <td className="px-3 py-1.5 text-neutral-700">{p.payment_form || '—'}</td>
              <td className="px-3 py-1.5 text-neutral-700">{fmtDate(p.due_date)}</td>
              <td className="px-3 py-1.5 text-neutral-700">{p.received_date ? fmtDate(p.received_date) : '—'}</td>
              <td className="px-3 py-1.5 text-right font-semibold text-neutral-800">{fmtBRL(p.amount)}</td>
              <td className="px-3 py-1.5">
                <FasesPagamento p={p} />
              </td>
              <td className="px-3 py-1.5">
                {p.is_received ? (
                  <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-emerald-700">
                    <CheckCircle2 size={11} /> Pago
                  </span>
                ) : p.is_vencida ? (
                  <span className="inline-flex items-center gap-1 text-[10.5px] font-semibold text-rose-700">
                    <Clock size={11} /> Vencida
                  </span>
                ) : (
                  <span className="text-[10.5px] font-semibold text-amber-700">A vencer</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
