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

/** Junta dois TransformResponse num só (soma totais, concatena results). */
function mergeTransform(a: TransformResponse, b: TransformResponse): TransformResponse {
  return {
    results: [...a.results, ...b.results],
    total_inserted: a.total_inserted + b.total_inserted,
    total_updated: a.total_updated + b.total_updated,
    total_errors: a.total_errors + b.total_errors,
  }
}

export const pipelineService = {
  /** STAGING → CORE Clinicorp: cadastros + eventos + patients. */
  transformAllCC: () =>
    api.post<TransformResponse>('/transform/clinicorp/all').then((r) => r.data),

  /** STAGING → CORE Conta Azul: cadastros + eventos financeiros + rateio. */
  transformAllCA: () =>
    api.post<TransformResponse>('/transform/contaazul/all').then((r) => r.data),

  /** CORE → ANALYTICS: dimensões + fatos. */
  analyticsRebuildAll: () =>
    api.post<AnalyticsResponse>('/analytics/rebuild/all').then((r) => r.data),

  /** Pipeline completo: transform CC + transform CA → analytics rebuild.
   * Sequencial — analytics depende do core estar atualizado. */
  rebuildAll: async (): Promise<RebuildPipelineResult> => {
    const t0 = performance.now()
    const transformCc = await pipelineService.transformAllCC()
    const transformCa = await pipelineService.transformAllCA()
    const transform = mergeTransform(transformCc, transformCa)
    const analytics = await pipelineService.analyticsRebuildAll()
    return { transform, analytics, duration_ms: Math.round(performance.now() - t0) }
  },
}
