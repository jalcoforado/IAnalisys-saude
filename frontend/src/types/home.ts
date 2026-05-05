export interface AgendaItem {
  external_id: string
  paciente_external_id: number | null
  paciente_nome: string
  profissional_external_id: number | null
  profissional_nome: string | null
  horario: string | null              // HH:MM
  categoria: string
  category_color: string | null
  duration_minutes: number | null
}

export interface AgendaSection {
  date_iso: string
  is_today: boolean
  total: number
  horarios_ocupados: number
  proximas: number
  items: AgendaItem[]
}

export interface RecallItem {
  paciente_external_id: number
  paciente_nome: string
  qtd_consultas: number
  intervalo_medio_dias: number
  dias_desde_ultima: number
  atraso_relativo: number
  ultima_consulta_iso: string
  total_payments: number
}

export interface RecallSection {
  total_elegiveis: number
  items: RecallItem[]
}

export interface OrcamentoParadoItem {
  external_id: string
  paciente_external_id: number | null
  paciente_nome: string
  profissional_nome: string | null
  amount: number
  dias_aprovado: number
  data_aprovacao_iso: string
}

export interface OrcamentosParadosSection {
  total: number
  valor_total: number
  items: OrcamentoParadoItem[]
}

export interface InadimplenciaCriticaItem {
  parcela_external_id: string
  pessoa_nome: string
  categoria: string | null
  valor_em_aberto: number
  dias_atraso: number
  data_vencimento_iso: string
}

export interface InadimplenciaCriticaSection {
  total: number
  valor_total: number
  items: InadimplenciaCriticaItem[]
}

export interface ResumoDiaSection {
  entradas_previstas: number
  saidas_previstas: number
  saldo_previsto: number
  qtd_parcelas_hoje: number
}

export interface TopProfissionalSemanaItem {
  external_id: number
  nome: string
  valor_aprovado: number
  qtd_aprovados: number
}

export interface TopProfsSemanaSection {
  inicio_iso: string
  fim_iso: string
  items: TopProfissionalSemanaItem[]
}

export interface HomeDashboardResponse {
  role: string
  role_label: string
  user_full_name: string
  today_iso: string
  agenda: AgendaSection | null
  recall: RecallSection | null
  orcamentos_parados: OrcamentosParadosSection | null
  inadimplencia_critica: InadimplenciaCriticaSection | null
  resumo_dia: ResumoDiaSection | null
  top_profs_semana: TopProfsSemanaSection | null
}
