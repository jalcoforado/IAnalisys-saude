import type { PeriodInfo } from '@/types/dashboard'

export interface FinanceiroKpis {
  entradas: number
  saidas: number
  saldo_liquido: number
  a_receber: number
  a_pagar: number
  inadimplencia_pct: number
  qtd_parcelas_vencidas: number
}

export interface CategoriaItem {
  external_id: string | null
  nome: string
  total: number
  pct: number
}

export interface CentroCustoItem {
  external_id: string | null
  nome: string
  entradas: number
  saidas: number
  saldo: number
}

export interface StatusMixItem {
  status: 'pago' | 'em_aberto' | 'vencido' | string
  label_pt: string
  qtd: number
  total: number
}

export interface FinanceiroEvolutionPoint {
  year_month_key: string
  label_pt: string
  entradas: number
  saidas: number
  saldo: number
}

export interface FinanceiroOverviewResponse {
  period: PeriodInfo
  previous: PeriodInfo
  kpis: FinanceiroKpis
  kpis_previous: FinanceiroKpis
  top_receitas: CategoriaItem[]
  top_despesas: CategoriaItem[]
  centros_custo: CentroCustoItem[]
  status_mix: StatusMixItem[]
  evolution: FinanceiroEvolutionPoint[]
}
