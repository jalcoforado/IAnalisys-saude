export interface PeriodInfo {
  year: number
  month: number
  label: string
  label_pt: string
}

export interface KpiValue {
  value: number
  previous: number | null
  delta_pct: number | null
}

export interface DashboardKpis {
  faturamento: KpiValue
  consultas: KpiValue
  absenteismo_pct: KpiValue
  conversao_pct: KpiValue
  ticket_medio: KpiValue
  pacientes_ativos: KpiValue
}

export interface EvolutionPoint {
  year_month_key: string
  label_pt: string
  faturamento: number
  consultas: number
}

export interface FunilComercial {
  total_orcamentos: number
  aprovados: number
  abertos: number
  em_followup: number
  recusados: number
  valor_total: number
  valor_aprovado: number
  valor_pipeline: number
  valor_perdido: number
  taxa_conversao_pct: number
}

export interface Inadimplencia {
  recebido: number
  a_receber: number
  total_emitido: number
  inadimplencia_pct: number
}

export interface MixPagamentoItem {
  forma: string
  total: number
  qtd: number
  pct: number
}

export interface TopProfissionalItem {
  external_id: number
  name: string | null
  orcamentos: number
  aprovados: number
  valor_aprovado: number
  taxa_conversao_pct: number
}

export interface TopCategoriaItem {
  categoria: string
  consultas: number
  canceladas: number
  absenteismo_pct: number
}

export interface ComparacaoYoY {
  period_yoy: PeriodInfo
  faturamento_atual: number
  faturamento_yoy: number
  faturamento_yoy_pct: number | null
  consultas_atual: number
  consultas_yoy: number
  consultas_yoy_pct: number | null
}

export interface CurvaAbcItem {
  classe: 'A' | 'B' | 'C' | string
  qtd_pacientes: number
  faturamento: number
  pct_pacientes: number
  pct_faturamento: number
}

export interface ChurnBucket {
  bucket: 'ativo' | 'em_risco' | 'inativo' | 'perdido' | 'sem_visita' | string
  label_pt: string
  qtd: number
  pct: number
}

export interface TopLtvPaciente {
  external_id: number
  name: string | null
  ltv: number
  total_payments: number
}

export interface NovosRecorrentes {
  novos: number
  recorrentes: number
  total: number
}

export interface PacientesAnalise {
  total_base: number
  curva_abc: CurvaAbcItem[]
  churn_buckets: ChurnBucket[]
  top_ltv: TopLtvPaciente[]
  novos_recorrentes: NovosRecorrentes
}

export interface DashboardExecutivoResponse {
  period: PeriodInfo
  previous: PeriodInfo
  kpis: DashboardKpis
  funil: FunilComercial
  inadimplencia: Inadimplencia
  mix_pagamento: MixPagamentoItem[]
  top_profissionais: TopProfissionalItem[]
  top_categorias_agenda: TopCategoriaItem[]
  comparacao_yoy: ComparacaoYoY
  pacientes: PacientesAnalise
  evolution: EvolutionPoint[]
}

// ── Drill-down auditável (PR-15) ───────────────────────────────

export type KpiId =
  | 'faturamento'
  | 'consultas'
  | 'absenteismo'
  | 'conversao'
  | 'ticket_medio'
  | 'pacientes_ativos'

export type KpiUnit = 'BRL' | 'count' | 'pct'

export interface DrillDownItem {
  external_id: string
  label: string
  secondary_label: string | null
  date_iso: string | null
  value: number | null
  extras: Record<string, string>
}

export interface DrillDownResponse {
  kpi_id: KpiId
  kpi_label: string
  period: PeriodInfo
  kpi_value: number
  kpi_unit: KpiUnit
  total_value: number | null
  total_count: number
  audit_ok: boolean | null
  items_returned: number
  items: DrillDownItem[]
}
