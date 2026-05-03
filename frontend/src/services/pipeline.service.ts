/**
 * Pipeline service: orquestra transformação STAGING → CORE → ANALYTICS.
 *
 * Esses passos são manuais por design (foi mais fácil debugar cada camada
 * separada). Esse service junta os dois numa só chamada do frontend.
 */
import api from '@/services/api'

export interface TransformResultItem {
  entity: string
  fetched: number
  inserted: number
  updated: number
  errors: number
}

export interface TransformResponse {
  results: TransformResultItem[]
  total_inserted: number
  total_updated: number
  total_errors: number
}

export interface BuilderResultResponse {
  entity: string
  rows_built: number
  inserted: number
  updated: number
}

export interface AnalyticsResponse {
  results: BuilderResultResponse[]
  total_inserted: number
  total_updated: number
}

export interface RebuildPipelineResult {
  transform: TransformResponse
  analytics: AnalyticsResponse
  duration_ms: number
}

export const pipelineService = {
  /** STAGING → CORE: cadastros + eventos + patients. */
  transformAll: () =>
    api.post<TransformResponse>('/transform/clinicorp/all').then((r) => r.data),

  /** CORE → ANALYTICS: dimensões + fatos. */
  analyticsRebuildAll: () =>
    api.post<AnalyticsResponse>('/analytics/rebuild/all').then((r) => r.data),

  /** Pipeline completo: transform → rebuild. Sequencial — o segundo depende do primeiro. */
  rebuildAll: async (): Promise<RebuildPipelineResult> => {
    const t0 = performance.now()
    const transform = await pipelineService.transformAll()
    const analytics = await pipelineService.analyticsRebuildAll()
    return { transform, analytics, duration_ms: Math.round(performance.now() - t0) }
  },
}
