import api from '@/services/api'
import type {
  BatchResponse,
  Checkpoint,
  SyncEntity,
  SyncJob,
  SyncSource,
} from '@/types/sync'

export const syncService = {
  // ── Clinicorp ────────────────────────────────────────────────
  static: () =>
    api.post<BatchResponse>('/sync/clinicorp/static').then((r) => r.data),

  transactional: (entity: SyncEntity, year: number, month: number) =>
    api
      .post<SyncJob>('/sync/clinicorp/transactional', { entity, year, month })
      .then((r) => r.data),

  transactionalBatch: (year: number, month: number, entities?: SyncEntity[]) =>
    api
      .post<BatchResponse>('/sync/clinicorp/transactional/batch', {
        year,
        month,
        entities,
      })
      .then((r) => r.data),

  kpisMonthly: (year: number, month: number) =>
    api
      .post<SyncJob>('/sync/clinicorp/kpis_monthly', { year, month })
      .then((r) => r.data),

  /** Enriquece pacientes via /patient/get (BirthDate, Email, CPF, Status, Phone).
   * Itera todos os pacientes do tenant — pode demorar minutos. */
  clinicorpPatientsDetails: () =>
    api.post<SyncJob>('/sync/clinicorp/patients/details').then((r) => r.data),

  // ── Conta Azul ───────────────────────────────────────────────
  contaazulStatic: () =>
    api.post<BatchResponse>('/sync/contaazul/static').then((r) => r.data),

  contaazulFinancial: (year: number, month: number) =>
    api
      .post<BatchResponse>('/sync/contaazul/financial', { year, month })
      .then((r) => r.data),

  contaazulTransactional: (entity: SyncEntity, year: number, month: number) =>
    api
      .post<SyncJob>('/sync/contaazul/transactional', { entity, year, month })
      .then((r) => r.data),

  contaazulAlteracoes: (hoursBack: number) =>
    api
      .post<BatchResponse>('/sync/contaazul/alteracoes', { hours_back: hoursBack })
      .then((r) => r.data),

  // ── Read (com filtro source opcional) ────────────────────────
  jobs: (limit = 30, entity?: SyncEntity, year?: number, source?: SyncSource) =>
    api
      .get<SyncJob[]>('/sync/jobs', {
        params: { limit, entity, year, source },
      })
      .then((r) => r.data),

  checkpoints: (source?: SyncSource) =>
    api
      .get<Checkpoint[]>('/sync/checkpoints', { params: { source } })
      .then((r) => r.data),
}
