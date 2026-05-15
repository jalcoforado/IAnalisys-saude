import api from '@/services/api'
import type {
  MetaStatus,
  MetaTokenInput,
  MetaValidation,
  MetaSyncEntity,
  MetaSyncEntityResult,
  MetaSyncAllResult,
  MetaDashboard,
  MetaCommentsInsights,
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

  commentsInsights: (days = 30) =>
    api.get<MetaCommentsInsights>('/meta/comments/insights', { params: { days } }).then((r) => r.data),

  classifyComments: (limit = 200) =>
    api.post<{ processed: number; fast_path: number; ia: number; errors: number }>(
      '/meta/comments/classify',
      null,
      { params: { limit } },
    ).then((r) => r.data),

  /** Botão "Atualizar tudo": sync_all + ig_comments + classify em sequência. */
  runAll: () =>
    api.post<Record<string, unknown>>('/meta/run-all').then((r) => r.data),

  /** Stories IG capturados nos últimos N dias + agregados. */
  stories: (days = 7) =>
    api.get<{
      period_days: number
      totals: {
        stories: number
        reach_total: number
        navigation_total: number
        replies_total: number
        avg_reach: number
        n_image: number
        n_video: number
      }
      items: Array<{
        external_id: string
        posted_at: string | null
        expires_at: string | null
        media_type: 'IMAGE' | 'VIDEO' | string | null
        thumbnail_url: string | null
        permalink: string | null
        reach: number
        replies: number
        navigation: number
      }>
    }>('/meta/stories', { params: { days } }).then((r) => r.data),

  /** Estado do APScheduler (próxima execução de cada job). */
  schedulerStatus: () =>
    api.get<{
      running: boolean
      timezone?: string
      jobs: { id: string; name: string; next_run: string | null }[]
      server_time?: string
    }>('/meta/scheduler/status').then((r) => r.data),

  /** Listagem paginada de comentários classificados (modal de auditoria). */
  commentsList: (params: {
    limit?: number
    offset?: number
    sentimento?: string
    flag?: string
    q?: string
    days?: number
  }) =>
    api.get<{
      total: number
      limit: number
      offset: number
      items: Array<{
        external_id: string
        autor: string | null
        texto: string
        commented_at: string | null
        post_external_id: string | null
        sentimento: 'positivo' | 'neutro' | 'negativo' | null
        flags: {
          lead_quente: boolean
          depoimento: boolean
          duvida_clinica: boolean
          objecao: boolean
          reclamacao: boolean
        }
        procedimento: string | null
        urgencia: 'alta' | 'media' | 'baixa' | null
        modelo_ia: string | null
        classificado_em: string | null
      }>
    }>('/meta/comments', { params }).then((r) => r.data),
}
