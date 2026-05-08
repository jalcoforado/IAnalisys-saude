/**
 * Types do dashboards segmentados (Sub-PR 20).
 * Mirror dos schemas Pydantic em backend/app/schemas/analise.py.
 */

export interface PeriodInfo {
  year: number
  month: number
  year_month_key: string
  label: string
}

export interface KpiCard {
  value: number
  value_label: string
  mom_value: number | null
  mom_pct: number | null
  mom_label: string | null
  yoy_value: number | null
  yoy_pct: number | null
  yoy_label: string | null
  trend: 'up' | 'down' | 'flat'
  sparkline_12m: number[]
  insight: string | null
  is_inverse: boolean
  // Mês parcial (mês corrente)
  is_partial: boolean
  partial_progress: number | null
  partial_days: number | null
  partial_days_in_month: number | null
  projected_value: number | null
  projected_label: string | null
}

export interface RecebidoBreakdown {
  liquido: number
  bruto: number
  taxas: number
  taxas_pct: number
}

export interface FinanceiroKpis {
  faturamento: KpiCard
  conversao: KpiCard
  ticket_medio: KpiCard
  recebido: KpiCard
  recebido_breakdown: RecebidoBreakdown
}

export interface FunilOrcamentos {
  gerados_qty: number
  gerados_amount: number
  aprovados_qty: number
  aprovados_amount: number
  pagos_qty: number
  pagos_amount: number
  // Conversões por QUANTIDADE
  conversao_aprovacao_pct: number
  conversao_pagamento_pct: number
  // Conversões por VALOR (R$) — alinha Clinicorp
  conversao_aprovacao_valor_pct: number
  conversao_pagamento_valor_pct: number
  aprovacao_mom_pct: number | null
  pagamento_mom_pct: number | null
  aprovacao_valor_mom_pct: number | null
  pagamento_valor_mom_pct: number | null
}

export interface TopProfFaturamento {
  professional_external_id: number
  nome: string
  faturamento: number
  valor_gerado: number
  qtd_aprovados: number
  qtd_gerados: number
  taxa_conversao_pct: number          // qtd
  taxa_conversao_valor_pct: number    // valor (Clinicorp)
  ticket_medio: number
  pct_total: number
}

export interface TopMedicoFaturamento {
  dentist_external_id: number
  nome: string
  faturamento: number
  qtd_procedimentos: number
  qtd_orcamentos: number
  ticket_medio_procedimento: number
  pct_total: number
}

export interface TopCategoriaFaturamento {
  categoria: string
  faturamento: number
  qtd_aprovados: number
  pct_total: number
  ticket_medio: number
  mom_pct: number | null
}

export interface MixPagamentoEnriched {
  forma_pagamento: string
  valor: number
  pct: number
  qtd_transacoes: number
  mom_pct: number | null
}

export interface SaudeRecebiveis {
  tempo_medio_aprovacao_dias: number | null
  tempo_medio_recebimento_dias: number | null
  inadimplencia_qty: number
  inadimplencia_amount: number
  inadimplencia_60d_qty: number
  inadimplencia_60d_amount: number
  inadimplencia_pct_total: number | null
}

export interface FinanceiroEvolutionPoint {
  year_month_key: string
  label: string
  faturamento: number
  recebido: number
  aprovados_qty: number
}

export interface PrazoBucket {
  label: string
  qtd_pagamentos: number
  valor: number
  ticket_medio: number
  pct_qtd: number
  pct_valor: number
}

export interface PrazoRecebimentoSection {
  qtd_pagamentos_total: number
  valor_total: number
  pct_a_vista_qtd: number
  pct_a_vista_valor: number
  prazo_medio_dias: number
  ticket_medio_a_vista: number
  ticket_medio_parcelado: number
  buckets: PrazoBucket[]
  mom_a_vista_pct: number | null
  yoy_a_vista_pct: number | null
  // Cobertura do plano de pagamento (Clinicorp gera as parcelas em partes)
  faturamento_aprovado: number    // header total dos APPROVED no mês (= KPI Faturamento)
  qtd_sem_parcelas: number        // orçamentos aprovados sem nenhuma parcela lançada
  valor_sem_parcelas: number      // header desses orçamentos
}

export interface TaxaPorForma {
  forma_pagamento: string
  bruto: number
  liquido: number
  taxa: number
  taxa_pct: number       // taxa efetiva DESSA forma (taxa / bruto)
  pct_volume: number     // bruto desta forma / bruto_total
  qtd_transacoes: number
  is_estimated: boolean  // True quando taxa por forma vem de heurística
}

export interface TaxasSection {
  taxas_total: number
  bruto_total: number
  bruto_com_taxa: number
  bruto_sem_taxa: number
  taxa_global_pct: number
  taxa_efetiva_pct: number
  por_forma: TaxaPorForma[]
  mom_efetiva_pct: number | null
  yoy_efetiva_pct: number | null
  economia_potencial_anual: number
  is_estimated: boolean
}

export interface PrazoAuditItem {
  treatment_external_id: number
  payment_header_external_id: number | null
  patient_name: string | null
  professional_name: string | null
  estimate_date: string | null
  estimate_amount: number | null
  payment_form: string | null
  installment_number: number | null
  installments_count: number | null
  amount: number
  due_date: string | null
}

export interface PrazoAuditResponse {
  period: PeriodInfo
  items: PrazoAuditItem[]
  total_count: number
  returned_count: number
  limit: number
}

export interface DescontosSection {
  qtd_orcamentos_aprovados: number
  qtd_procs_aprovados: number
  original_amount_tabela: number
  faturamento: number
  desconto_total: number
  desconto_total_pct: number
  desconto_procedimento: number
  desconto_procedimento_pct: number
  desconto_negociacao: number
  desconto_negociacao_pct: number
  escopo_nao_aprovado: number     // informativo: procs sugeridos mas não aprovados pelo paciente
  mom_total_pct: number | null    // pontos percentuais
  yoy_total_pct: number | null
}

export interface AnaliseFinanceiroResponse {
  period: PeriodInfo
  previous: PeriodInfo
  yoy: PeriodInfo
  kpis: FinanceiroKpis
  funil: FunilOrcamentos
  descontos: DescontosSection
  prazos: PrazoRecebimentoSection
  taxas: TaxasSection
  mix_pagamento: MixPagamentoEnriched[]
  top_profissionais: TopProfFaturamento[]
  top_medicos: TopMedicoFaturamento[]
  top_categorias: TopCategoriaFaturamento[]
  evolution: FinanceiroEvolutionPoint[]
}

// ── Comercial ─────────────────────────────────────────────────

export interface ConversaoBreakdown {
  total_atendidos: number
  aprovou_no_mes: number
  aprovou_no_mes_pct: number
  gerou_nao_aprovou: number
  gerou_nao_aprovou_pct: number
  em_tratamento: number
  em_tratamento_pct: number
  avulso_sem_orcamento: number
  avulso_sem_orcamento_pct: number
  historico_sem_aprov: number
  historico_sem_aprov_pct: number
}

export interface ComercialKpis {
  consultas: KpiCard
  absenteismo_pct: KpiCard
  conversao_consulta_orcamento_pct: KpiCard
  conversao_breakdown: ConversaoBreakdown
  pacientes_unicos: KpiCard
}

export interface FunilComercial {
  pacientes_atendidos: number       // nível 1 — pacientes distintos com is_efetiva=1
  total_consultas: number           // contexto: nº de eventos efetivos (eventos)
  com_orcamento_qty: number         // pacientes atendidos com orçamento gerado no mês
  aprovados_qty: number             // pacientes atendidos com orçamento aprovado no mês
  aprovados_amount: number
  taxa_oferta_pct: number           // com_orcamento / pacientes_atendidos
  taxa_aprovacao_pct: number        // aprovados / com_orcamento
  taxa_conversao_total_pct: number  // aprovados / pacientes_atendidos (= KPI)
  tempo_medio_consulta_aprov_dias: number | null
  taxa_oferta_mom_pct: number | null
  taxa_aprovacao_mom_pct: number | null
}

export interface TopProcedimentoExecutado {
  procedure_name: string
  qtd_executados: number
  faturamento: number
  pct_volume: number
  ticket_medio: number
}

export interface TopEspecialidadeDemanda {
  especialidade: string
  qtd_procedimentos: number
  pct_volume: number
  faturamento: number
}

export interface TopProfissionalConsultas {
  professional_external_id: number
  nome: string
  qtd_consultas: number
  qtd_canceladas: number
  absenteismo_pct: number
  pacientes_distintos: number
  ocupacao_pct: number | null
  pct_volume: number
}

export interface MixCategoriaConsulta {
  categoria: string
  qtd: number
  pct: number
  canceladas: number
  absenteismo_pct: number
  mom_pct: number | null
}

export interface OperacionalComercial {
  encaixe_qty: number
  encaixe_pct: number
  retorno_pendente_qty: number
  remarcar_qty: number
  cancelados_qty: number
  cancelados_amount_estimado: number
}

export interface SaudeAgendaSection {
  total: number
  efetivas: number
  faltas: number
  canceladas: number
  indefinidas: number
  outros: number
  pct_efetivas: number
  pct_faltas: number
  pct_canceladas: number
  pct_indefinidas: number
  pct_outros: number
  absenteismo_clinico_pct: number
}

export interface ComercialEvolutionPoint {
  year_month_key: string
  label: string
  efetivas: number             // CHECKOUT
  faltas: number               // MISSED
  canceladas: number           // is_canceled=1
  indefinidas: number          // status NULL não-cancelado
  pacientes_unicos: number     // contexto, não entra no empilhamento
}

export interface AnaliseComercialResponse {
  period: PeriodInfo
  previous: PeriodInfo
  yoy: PeriodInfo
  kpis: ComercialKpis
  funil: FunilComercial
  saude_agenda: SaudeAgendaSection
  top_procedimentos: TopProcedimentoExecutado[]
  top_especialidades: TopEspecialidadeDemanda[]
  top_profissionais: TopProfissionalConsultas[]
  mix_categorias: MixCategoriaConsulta[]
  operacional: OperacionalComercial
  evolution: ComercialEvolutionPoint[]
}
