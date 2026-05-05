import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, ExternalLink, Loader2, X } from 'lucide-react'

import { dashboardService } from '@/services/dashboard.service'
import type { DrillDownItem, DrillDownResponse, KpiId, KpiUnit } from '@/types/dashboard'

// ── helpers locais ────────────────────────────────────────────

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000) {
    if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
    return `R$ ${(n / 1_000).toFixed(0)}k`
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 2,
  }).format(n)
}
const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtDate = (iso: string | null) => {
  if (!iso) return '—'
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

const formatKpiValue = (value: number, unit: KpiUnit): string => {
  if (unit === 'BRL') return fmtBRL(value)
  if (unit === 'pct') return `${value.toFixed(2)}%`
  return fmtNum(value)
}

// ── Status pill (orçamentos) ──────────────────────────────────

const STATUS_COLORS: Record<string, string> = {
  aprovado: 'bg-success-bg text-success-text',
  followup: 'bg-warning-bg text-warning-text',
  aberto: 'bg-info-bg text-info-text',
  recusado: 'bg-error-bg text-error-text',
  indefinido: 'bg-neutral-100 text-neutral-600',
}

function StatusPill({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] || STATUS_COLORS.indefinido
  return (
    <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded ${cls}`}>
      {status}
    </span>
  )
}

// ── Drawer principal ──────────────────────────────────────────

export interface KpiDrillDownProps {
  kpiId: KpiId
  year: number
  month: number
  onClose: () => void
}

export default function KpiDrillDown({ kpiId, year, month, onClose }: KpiDrillDownProps) {
  // Fechar com ESC
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  const q = useQuery({
    queryKey: ['drilldown', kpiId, year, month],
    queryFn: () => dashboardService.itens(kpiId, year, month, 500),
    staleTime: 30_000,
  })

  return (
    <>
      {/* Overlay — clica fora pra fechar */}
      <div
        className="fixed inset-0 bg-black/30 z-40 transition-opacity"
        onClick={onClose}
        aria-hidden
      />
      {/* Drawer slide-in da direita */}
      <aside
        className="fixed top-0 right-0 h-full w-full md:w-[55vw] lg:w-[50vw] max-w-[800px] bg-white shadow-2xl z-50 flex flex-col"
        role="dialog"
        aria-modal
      >
        <DrawerHeader data={q.data} onClose={onClose} loading={q.isLoading} />
        <div className="flex-1 overflow-y-auto">
          {q.isLoading && (
            <div className="flex items-center justify-center py-16 text-neutral-400 text-sm">
              <Loader2 size={16} className="animate-spin mr-2" /> Carregando linhas…
            </div>
          )}
          {q.isError && (
            <div className="m-4 p-4 bg-error-bg border border-error-border rounded-lg text-error-text text-sm">
              Erro ao carregar drill-down. Tente novamente.
            </div>
          )}
          {q.data && <ItemsTable data={q.data} />}
        </div>
        {q.data && <DrawerFooter data={q.data} />}
      </aside>
    </>
  )
}

// ── Header ────────────────────────────────────────────────────

function DrawerHeader({ data, onClose, loading }: { data: DrillDownResponse | undefined; onClose: () => void; loading: boolean }) {
  return (
    <div className="px-5 py-4 border-b bg-gradient-to-r from-primary-50 to-white flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-[11px] uppercase tracking-wide text-primary-700 font-bold">
          {loading ? 'Carregando…' : data?.period.label_pt}
        </div>
        <div className="text-lg font-bold text-neutral-900 mt-0.5">
          {data?.kpi_label || '...'}
        </div>
        {data && (
          <div className="text-2xl font-bold text-primary-700 tabular-nums mt-1">
            {formatKpiValue(data.kpi_value, data.kpi_unit)}
          </div>
        )}
      </div>
      <button
        onClick={onClose}
        className="w-8 h-8 rounded-lg hover:bg-neutral-100 flex items-center justify-center text-neutral-500 hover:text-neutral-900 shrink-0"
        aria-label="Fechar"
      >
        <X size={18} />
      </button>
    </div>
  )
}

// ── Tabela de itens ───────────────────────────────────────────

function ItemsTable({ data }: { data: DrillDownResponse }) {
  if (data.items.length === 0) {
    return (
      <div className="px-5 py-12 text-center text-sm text-neutral-400">
        Nenhuma linha encontrada para este KPI no período.
      </div>
    )
  }

  // Linhas mostram colunas levemente diferentes por KPI — todas têm
  // label/secondary/date; valor numérico só pra unit BRL/count com sentido.
  const showValue = data.kpi_unit === 'BRL' || data.kpi_id === 'conversao'
  const showStatus = data.kpi_id === 'conversao'
  const valueIsBRL = data.kpi_unit === 'BRL' || data.kpi_id === 'conversao'

  return (
    <table className="w-full text-sm">
      <thead className="bg-neutral-50 border-b sticky top-0 z-10">
        <tr className="text-[11px] uppercase tracking-wide text-neutral-500">
          <th className="px-4 py-2 text-left font-semibold">#</th>
          <th className="px-4 py-2 text-left font-semibold">Identificação</th>
          <th className="px-4 py-2 text-left font-semibold hidden md:table-cell">Detalhe</th>
          <th className="px-4 py-2 text-left font-semibold">Data</th>
          {showStatus && <th className="px-4 py-2 text-left font-semibold">Status</th>}
          {showValue && <th className="px-4 py-2 text-right font-semibold">Valor</th>}
        </tr>
      </thead>
      <tbody className="divide-y">
        {data.items.map((item, i) => (
          <ItemRow
            key={`${item.external_id}-${i}`}
            item={item}
            index={i}
            showValue={showValue}
            showStatus={showStatus}
            valueIsBRL={valueIsBRL}
          />
        ))}
      </tbody>
    </table>
  )
}

function ItemRow({ item, index, showValue, showStatus, valueIsBRL }: {
  item: DrillDownItem
  index: number
  showValue: boolean
  showStatus: boolean
  valueIsBRL: boolean
}) {
  return (
    <tr className="hover:bg-primary-50/30 transition-colors">
      <td className="px-4 py-2 text-xs text-neutral-400 tabular-nums">{index + 1}</td>
      <td className="px-4 py-2">
        <div className="flex items-center gap-1.5 text-neutral-900 font-medium truncate" title={item.label}>
          <span className="truncate">{item.label}</span>
        </div>
        <div className="text-[11px] text-neutral-400 tabular-nums flex items-center gap-1">
          #{item.external_id}
          <ExternalLink size={10} className="opacity-50" />
        </div>
      </td>
      <td className="px-4 py-2 hidden md:table-cell text-neutral-600 truncate max-w-[180px]" title={item.secondary_label || ''}>
        {item.secondary_label || '—'}
        {item.extras.categoria && (
          <div className="text-[11px] text-neutral-400 truncate">{item.extras.categoria}</div>
        )}
      </td>
      <td className="px-4 py-2 text-neutral-600 tabular-nums whitespace-nowrap">{fmtDate(item.date_iso)}</td>
      {showStatus && (
        <td className="px-4 py-2">
          {item.extras.status ? <StatusPill status={item.extras.status} /> : '—'}
        </td>
      )}
      {showValue && (
        <td className="px-4 py-2 text-right tabular-nums font-semibold text-neutral-900">
          {item.value != null ? (valueIsBRL ? fmtBRL(item.value) : fmtNum(item.value)) : '—'}
        </td>
      )}
    </tr>
  )
}

// ── Footer com auditoria ──────────────────────────────────────

function DrawerFooter({ data }: { data: DrillDownResponse }) {
  // Auditoria só pra KPIs cumulativos (audit_ok != null)
  const isCumulative = data.audit_ok !== null

  const truncated = data.total_count > data.items_returned

  return (
    <div className="border-t bg-neutral-50 px-5 py-3">
      <div className="flex items-center justify-between text-xs">
        <div className="text-neutral-600">
          <span className="font-semibold text-neutral-900">{fmtNum(data.items_returned)}</span>
          {' '}de {fmtNum(data.total_count)} {data.total_count === 1 ? 'linha' : 'linhas'}
          {truncated && <span className="text-warning-text ml-1">(primeiras {fmtNum(data.items_returned)})</span>}
        </div>
        {isCumulative && data.total_value != null && (
          <div className="flex items-center gap-3">
            <div className="text-right">
              <div className="text-[10px] uppercase text-neutral-500 font-bold">Total das linhas</div>
              <div className="text-sm font-bold tabular-nums text-neutral-900">
                {data.kpi_unit === 'BRL' ? fmtBRL(data.total_value) : fmtNum(data.total_value)}
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] uppercase text-neutral-500 font-bold">KPI exibido</div>
              <div className="text-sm font-bold tabular-nums text-primary-700">
                {data.kpi_unit === 'BRL' ? fmtBRL(data.kpi_value) : fmtNum(data.kpi_value)}
              </div>
            </div>
            {data.audit_ok ? (
              <span className="flex items-center gap-1 text-success-text text-[11px] font-bold uppercase">
                <CheckCircle2 size={14} /> bate
              </span>
            ) : (
              <span className="text-error-text text-[11px] font-bold uppercase">
                ⚠ divergente
              </span>
            )}
          </div>
        )}
        {!isCumulative && (
          <div className="text-[11px] text-neutral-500 italic">
            Indicador percentual / médio — auditoria por amostra das linhas.
          </div>
        )}
      </div>
    </div>
  )
}
