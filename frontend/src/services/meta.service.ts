import api from '@/services/api'
import type {
  MetaStatus,
  MetaTokenInput,
  MetaValidation,
  MetaSyncEntity,
  MetaSyncEntityResult,
  MetaSyncAllResult,
  MetaDashboard,
} from '@/types/meta'

export const metaService = {
  status: () =>
    api.get<MetaStatus>('/meta/status').then((r) => r.data),

  putToken: (payload: MetaTokenInput) =>
    api.put<MetaStatus>('/meta/token', payload).then((r) => r.data),

  validate: () =>
    api.post<MetaValidation>('/meta/validate').then((r) => r.data),

  disconnect: () =>
    api.delete('/meta/token').then(() => undefined),

  syncEntity: (entity: MetaSyncEntity) =>
    api.post<MetaSyncEntityResult>(`/meta/sync/${entity}`).then((r) => r.data),

  syncAll: () =>
    api.post<MetaSyncAllResult>('/meta/sync/all').then((r) => r.data),

  dashboard: () =>
    api.get<MetaDashboard>('/meta/dashboard').then((r) => r.data),
}
