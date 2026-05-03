import api from '@/services/api'
import type { BatchResponse, Checkpoint, SyncEntity, SyncJob } from '@/types/sync'

export const syncService = {
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

  jobs: (limit = 30, entity?: SyncEntity, year?: number) =>
    api
      .get<SyncJob[]>('/sync/jobs', { params: { limit, entity, year } })
      .then((r) => r.data),

  checkpoints: () =>
    api.get<Checkpoint[]>('/sync/checkpoints').then((r) => r.data),
}
