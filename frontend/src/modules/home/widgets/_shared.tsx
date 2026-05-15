/**
 * Infraestrutura compartilhada dos widgets do MY-Analisys.
 *
 * - Hooks de dados por endpoint (TanStack Query dedupe automaticamente: se 4
 *   widgets KPI pegam o mesmo `/analise/financeiro?year=&month=`, só roda 1
 *   fetch e os 4 leem do cache).
 * - `KpiWidget`: wrapper que aplica loading/error padronizado em cima do
 *   `KpiCardEnriched`, evitando boilerplate em cada widget.
 */
import { Loader2 } from 'lucide-react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { analiseService } from '@/services/analise.service'
import { financeiroService } from '@/services/financeiro.service'
import { metaService } from '@/services/meta.service'
import { KpiCardEnriched } from '@/modules/analise/components/KpiCardEnriched'
import type { KpiCard } from '@/types/analise'

// ── Formatadores compartilhados ───────────────────────────────

export const fmtBRL = (n: number, compact = false): string => {
  if (compact && Math.abs(n) >= 1_000) {
    if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
    return `R$ ${(n / 1_000).toFixed(0)}k`
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(n)
}

export const fmtNum = (n: number): string => new Intl.NumberFormat('pt-BR').format(n)

export const fmtPct = (n: number | null | undefined): string => {
  if (n === null || n === undefined) return '—'
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

export const fmtTime = (iso: string | null): string => {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return '—'
  }
}

// Buckets de paciente (visita) — espelha o do DashboardPacientesPage.
export const BUCKET_META: Record<string, { label: string; bg: string; text: string; bar: string }> = {
  ativo:      { label: 'Ativo',      bg: 'bg-emerald-50',  text: 'text-emerald-700', bar: 'bg-emerald-500' },
  em_risco:   { label: 'Em risco',   bg: 'bg-amber-50',    text: 'text-amber-700',   bar: 'bg-amber-500' },
  inativo:    { label: 'Inativo',    bg: 'bg-orange-50',   text: 'text-orange-700',  bar: 'bg-orange-500' },
  perdido:    { label: 'Perdido',    bg: 'bg-rose-50',     text: 'text-rose-700',    bar: 'bg-rose-500' },
  sem_visita: { label: 'Sem visita', bg: 'bg-neutral-100', text: 'text-neutral-600', bar: 'bg-neutral-400' },
}

// ── Wrappers de estado ────────────────────────────────────────

export function WidgetLoading({ label }: { label?: string }) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl h-full flex items-center justify-center text-neutral-400 text-xs">
      <Loader2 size={16} className="animate-spin mr-2" />
      {label ? `Carregando ${label}…` : 'Carregando…'}
    </div>
  )
}

export function WidgetError({ label }: { label: string }) {
  return (
    <div className="bg-error-bg border border-error-border rounded-xl h-full flex items-center justify-center text-error-text text-xs px-4 text-center">
      Erro ao carregar “{label}”.
    </div>
  )
}

/** Período de referência: mês atual (timezone do browser). KpiCard tem
 * `is_partial` + `projected_label` pra explicar que ainda é parcial. */
export function currentPeriod(): { year: number; month: number } {
  const now = new Date()
  return { year: now.getFullYear(), month: now.getMonth() + 1 }
}

// ── Hooks de dados ─────────────────────────────────────────────

export function useAnaliseFinanceiroAtual() {
  const { year, month } = currentPeriod()
  return useQuery({
    queryKey: ['analise', 'financeiro', year, month],
    queryFn: () => analiseService.financeiro(year, month),
    staleTime: 5 * 60_000,
  })
}

export function useAnaliseComercialAtual() {
  const { year, month } = currentPeriod()
  return useQuery({
    queryKey: ['analise', 'comercial', year, month],
    queryFn: () => analiseService.comercial(year, month),
    staleTime: 5 * 60_000,
  })
}

export function useAnalisePacientesAtual() {
  const { year, month } = currentPeriod()
  return useQuery({
    queryKey: ['analise', 'pacientes', year, month],
    queryFn: () => analiseService.pacientes(year, month),
    staleTime: 5 * 60_000,
  })
}

export function useFinanceiroOverviewAtual() {
  const { year, month } = currentPeriod()
  return useQuery({
    queryKey: ['financeiro', 'overview', year, month],
    queryFn: () => financeiroService.overview(year, month),
    staleTime: 5 * 60_000,
  })
}

export function useMetaDashboard() {
  return useQuery({
    queryKey: ['meta', 'dashboard'],
    queryFn: () => metaService.dashboard(),
    staleTime: 5 * 60_000,
  })
}

// ── KpiWidget wrapper ─────────────────────────────────────────

export interface KpiWidgetProps<T> {
  query: UseQueryResult<T>
  selectKpi: (data: T) => KpiCard
  label: string
  icon?: React.ReactNode
  iconBg?: string
  emphasized?: boolean
}

export function KpiWidget<T>({
  query,
  selectKpi,
  label,
  icon,
  iconBg,
  emphasized,
}: KpiWidgetProps<T>) {
  if (query.isLoading) {
    return (
      <div className="bg-white border border-neutral-200 rounded-xl h-full flex items-center justify-center text-neutral-400 text-xs">
        <Loader2 size={16} className="animate-spin mr-2" /> Carregando…
      </div>
    )
  }
  if (query.isError || !query.data) {
    return (
      <div className="bg-error-bg border border-error-border rounded-xl h-full flex items-center justify-center text-error-text text-xs px-4 text-center">
        Erro ao carregar “{label}”.
      </div>
    )
  }
  const kpi = selectKpi(query.data)
  return (
    <KpiCardEnriched
      data={kpi}
      label={label}
      icon={icon}
      iconBg={iconBg}
      emphasized={emphasized}
      className="h-full flex flex-col"
    />
  )
}
