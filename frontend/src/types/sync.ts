export type SyncSource = 'clinicorp' | 'contaazul'

export type SyncEntity =
  // Estáticas
  | 'business'
  | 'users'
  | 'professionals'
  | 'specialties'
  | 'procedures'
  | 'appointment_categories'
  | 'appointment_statuses'
  | 'crm_campaigns'
  // Transacionais
  | 'appointments'
  | 'estimates'
  | 'payments'
  | 'invoices'
  | 'receipts'
  | 'summary_entries'
  // Agregada (Clinicorp)
  | 'kpis_monthly'
  // Conta Azul — estáticas
  | 'pessoas'
  | 'produtos'
  | 'servicos'
  | 'vendedores'
  | 'categorias'
  | 'centros_custo'
  // Conta Azul — transacionais
  | 'contas_receber'
  | 'contas_pagar'
  // Conta Azul — saldos bancários (Fase 1 Show no Financeiro)
  | 'contas_financeiras'
  | 'saldos_atuais'
  | 'saldos_iniciais'
  // Conta Azul — DRE (Fase 2 Show no Financeiro)
  | 'categorias_dre'

export const STATIC_ENTITIES: SyncEntity[] = [
  'business',
  'users',
  'professionals',
  'specialties',
  'procedures',
  'appointment_categories',
  'appointment_statuses',
  'crm_campaigns',
]

export const TRANSACTIONAL_ENTITIES: SyncEntity[] = [
  'appointments',
  'estimates',
  'payments',
  'invoices',
  'receipts',
  'summary_entries',
]

export const CA_STATIC_ENTITIES: SyncEntity[] = [
  'pessoas',
  'produtos',
  'servicos',
  'vendedores',
  'categorias',
  'centros_custo',
  'categorias_dre',
]

export const CA_TRANSACTIONAL_ENTITIES: SyncEntity[] = [
  'contas_receber',
  'contas_pagar',
]

export const ENTITY_LABELS: Record<SyncEntity, string> = {
  business: 'Unidades',
  users: 'Usuários Clinicorp',
  professionals: 'Profissionais',
  specialties: 'Especialidades',
  procedures: 'Procedimentos',
  appointment_categories: 'Categorias de agenda',
  appointment_statuses: 'Status de agenda',
  crm_campaigns: 'Campanhas CRM',
  appointments: 'Agendamentos',
  estimates: 'Orçamentos',
  payments: 'Pagamentos',
  invoices: 'Faturas',
  receipts: 'Recibos',
  summary_entries: 'Lançamentos contábeis',
  kpis_monthly: 'KPIs mensais',
  // Conta Azul
  pessoas: 'Pessoas (clientes + fornecedores)',
  produtos: 'Produtos',
  servicos: 'Serviços',
  vendedores: 'Vendedores',
  categorias: 'Categorias',
  centros_custo: 'Centros de Custo',
  contas_receber: 'Contas a Receber',
  contas_pagar: 'Contas a Pagar',
  contas_financeiras: 'Contas financeiras (bancos)',
  saldos_atuais: 'Saldos atuais',
  saldos_iniciais: 'Saldos iniciais (12m)',
  categorias_dre: 'Plano DRE (estrutura)',
}

export const CA_SALDOS_ENTITIES: SyncEntity[] = [
  'contas_financeiras',
  'saldos_atuais',
  'saldos_iniciais',
]

export type SyncStatus = 'pending' | 'running' | 'success' | 'error' | 'idle'

export interface SyncJob {
  id: number
  tenant_id: string
  source: string
  entity: SyncEntity
  status: SyncStatus
  period_from: string | null   // YYYY-MM-DD
  period_to: string | null
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  records_fetched: number | null
  records_inserted: number | null
  records_updated: number | null
  errors_count: number | null
  error_message: string | null
  created_at: string
}

export interface Checkpoint {
  tenant_id: string
  source: string
  entity: SyncEntity
  last_period_from: string | null
  last_period_to: string | null
  last_synced_at: string | null
  last_sync_job_id: number | null
  status: SyncStatus
  total_records: number
}

export interface BatchResponse {
  jobs: SyncJob[]
  total_inserted: number
  total_updated: number
  total_errors: number
}
