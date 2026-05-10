import type { PeriodInfo } from '@/types/dashboard'

export interface FinanceiroKpis {
  entradas: number
  saidas: number
  saldo_liquido: number
  a_receber: number
  a_pagar: number
  inadimplencia_pct: number
  qtd_parcelas_vencidas: number
  encargos_entradas: number
  encargos_saidas: number
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

export interface ContaBancariaItem {
  external_id: string
  nome: string
  banco: string | null
  codigo_banco: string | null
  tipo: string | null
  saldo_atual: number
  ativo: boolean
  is_banco_real: boolean
}

export interface SaldosBancariosBlock {
  saldo_bancos: number
  saldo_caixinhas: number
  qtd_bancos_ativos: number
  qtd_caixinhas_ativas: number
  qtd_contas_total: number
  atualizado_em: string | null
  contas: ContaBancariaItem[]
}

export interface DreSubgrupoItem {
  external_id: string
  descricao: string
  codigo: string | null
  posicao: number | null
  qtd_categorias: number
  total: number
}

export interface DreGrupoItem {
  external_id: string
  descricao: string
  codigo: string
  posicao: number | null
  total: number
  subgrupos: DreSubgrupoItem[]
}

export interface DreBlock {
  grupos: DreGrupoItem[]
  total_classificado: number
  total_nao_classificado: number
}

export interface MetodoPagamentoItem {
  metodo: string
  label: string
  qtd_baixas: number
  valor_total: number
  pct_valor: number
}

export interface MetodosPagamentoBlock {
  metodos: MetodoPagamentoItem[]
  qtd_total: number
  valor_total: number
  cobertura_pct: number
  pendentes_detalhamento: number
}

export interface ContaDestinoItem {
  external_id: string | null
  nome: string
  banco: string | null
  qtd_baixas: number
  valor_total: number
  pct_valor: number
}

export interface ConciliacaoBlock {
  qtd_total: number
  qtd_conciliadas: number
  qtd_nao_conciliadas: number
  pct_conciliado: number
  valor_conciliado: number
  valor_nao_conciliado: number
  contas_destino: ContaDestinoItem[]
}

export interface TransferenciaFluxoItem {
  origem_external_id: string | null
  origem_nome: string
  origem_banco: string | null
  destino_external_id: string | null
  destino_nome: string
  destino_banco: string | null
  qtd: number
  valor_total: number
}

export interface TransferenciasBlock {
  qtd: number
  valor_total: number
  qtd_contas_origem: number
  qtd_contas_destino: number
  fluxos: TransferenciaFluxoItem[]
}

export interface FinanceiroOverviewResponse {
  period: PeriodInfo
  previous: PeriodInfo
  kpis: FinanceiroKpis
  kpis_previous: FinanceiroKpis
  saldos_bancarios: SaldosBancariosBlock
  dre: DreBlock
  metodos_pagamento: MetodosPagamentoBlock
  conciliacao: ConciliacaoBlock
  transferencias: TransferenciasBlock
  top_receitas: CategoriaItem[]
  top_despesas: CategoriaItem[]
  centros_custo: CentroCustoItem[]
  status_mix: StatusMixItem[]
  evolution: FinanceiroEvolutionPoint[]
}
