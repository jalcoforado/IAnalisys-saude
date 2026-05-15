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
import { KpiCardEnriched } from '@/modules/analise/components/KpiCardEnriched'
import type { KpiCard } from '@/types/analise'

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
    />
  )
}
