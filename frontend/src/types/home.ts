export type CategoryGroup =
  | 'consulta' | 'retorno' | 'manutencao' | 'procedimento'
  | 'reabilitacao' | 'ortodontia' | 'bloqueio' | 'outro'

export type StatusType =
  | 'CONFIRMED' | 'ARRIVED' | 'IN_SESSION' | 'CHECKOUT'
  | 'MISSED' | 'LATE' | 'CALL' | 'PENDING_MATERIAL'

export interface StrategicDayKPIs {
  date_iso: string
  label: string
  is_today: boolean
  total: number
  ocupacao_pct: number
  faltas_esperadas_min: number
  faltas_esperadas_max: number
  confirmados: number
  confirmados_pct: number
  riscos_altos: number
  encaixe_min: number
  horas_cadeira_hoje: number
}

export interface StrategicOverview {
  days: StrategicDayKPIs[]
  total_3d: number
  faltas_esperadas_3d_min: number
  faltas_esperadas_3d_max: number
  encaixe_total_3d_min: number
  waitlist_3d: number
  encaixe_3d: number
  top_pacientes_risco: RiskTopPatient[]
  top_profs_ociosos: CapacityProfBucket[]
  baseline_pct: number
}

export interface CapacityProfBucket {
  professional_external_id: number
  professional_nome: string | null
  consultas_hoje: number
  consultas_teto_p95: number
  ocupacao_pct: number
}

export interface EncaixeSlot {
  professional_external_id: number
  professional_nome: string | null
  inicio: string  // HH:MM
  fim: string     // HH:MM
  duracao_min: number
}

export interface CapacitySection {
  historico_dias: number
  historico_dias_efetivo: number
  consultas_teto_p95: number
  consultas_hoje: number
  consultas_ocupacao_pct: number
  horas_cadeira_teto_p95: number    // em minutos
  horas_cadeira_hoje: number        // em minutos
  horas_cadeira_ocupacao_pct: number
  profs_com_folga: CapacityProfBucket[]
  encaixes: EncaixeSlot[]
  encaixe_total_min: number
}

export type TagClass =
  | 'waitlist' | 'encaixe' | 'remarcar' | 'lembrete'
  | 'orcamento_pendente' | 'retorno_pendente' | 'financeiro_conferido' | 'outro'

export interface AppointmentTagBrief {
  name: string
  color: string | null
  tag_class: TagClass | null
}

export interface AgendaItem {
  external_id: string
  paciente_external_id: number | null
  paciente_nome: string
  paciente_birth_date: string | null  // YYYY-MM-DD
  paciente_gender: 'M' | 'F' | null
  profissional_external_id: number | null
  profissional_nome: string | null
  horario: string | null              // HH:MM
  categoria: string
  category_color: string | null
  category_group: CategoryGroup | null
  duration_minutes: number | null
  status_type: StatusType | null      // null = Agendado (default)
  status_description: string | null
  status_color: string | null
  risco_pct: number | null            // 0–100; null = não calculado
  risco_razao: string | null
  tags: AppointmentTagBrief[]
}

export interface RiskTopPatient {
  paciente_external_id: number
  paciente_nome: string
  horario: string | null
  profissional_nome: string | null
  risco_pct: number
  no_show_rate_pct: number
  total_historico: number
  razao: string
}

export interface RiskSection {
  historico_dias: number
  baseline_pct: number
  consultas_avaliadas: number
  faltas_esperadas_min: number
  faltas_esperadas_max: number
  pacientes_alto_risco: RiskTopPatient[]
}

export interface WaitlistSuggestion {
  tipo: 'vaga_livre' | 'risco_falta'
  date_iso: string
  horario: string
  duration_min: number
  razao: string
  paciente_em_risco_nome: string | null
  paciente_em_risco_id: number | null
  risco_pct: number | null
}

export interface WaitlistItem {
  appointment_external_id: string
  paciente_external_id: number | null
  paciente_nome: string
  profissional_external_id: number | null
  profissional_nome: string | null
  horario: string | null
  appointment_date_iso: string
  is_waitlist: boolean
  is_encaixe: boolean
  dias_aguardando: number
  tag_color: string | null
  suggestions: WaitlistSuggestion[]
}

export interface WaitlistSection {
  total: number
  waitlist_count: number
  encaixe_count: number
  items: WaitlistItem[]
}

export interface AgendaSection {
  date_iso: string
  is_today: boolean
  total: number
  horarios_ocupados: number
  proximas: number
  items: AgendaItem[]
  capacity: CapacitySection | null
  risk: RiskSection | null
  waitlist: WaitlistSection | null
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

export interface PendenciaItem {
  appointment_external_id: string
  paciente_external_id: number | null
  paciente_nome: string
  profissional_nome: string | null
  appointment_date_iso: string | null
  horario: string | null
  tag_name: string
  tag_class: string
  dias_aplicada: number
}

export interface PendenciaBucket {
  tag_class: string
  label: string
  total: number
  items: PendenciaItem[]
}

export interface PendenciasOperacionaisSection {
  total: number
  buckets: PendenciaBucket[]
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
  pendencias: PendenciasOperacionaisSection | null
}
