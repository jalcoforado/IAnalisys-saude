/**
 * Tipos do módulo Meta — sub-PR 21b.
 * Espelha os schemas Pydantic em `backend/app/schemas/meta.py`.
 */

export interface MetaStatus {
  connected: boolean
  status: 'ativo' | 'token_invalido' | 'desconectado'
  token_validated_at: string | null
  token_is_valid: boolean
  app_id: string | null
  app_name: string | null
  business_id: string | null
  business_name: string | null
  system_user_id: string | null
  system_user_name: string | null
  fb_page_id: string | null
  fb_page_name: string | null
  ig_account_id: string | null
  ig_username: string | null
  ad_account_id: string | null
  ad_account_authorized: boolean
  pixel_id: string | null
  pixel_last_fired_at: string | null
  token_scopes: string[] | null
  graph_api_version: string | null
  created_at: string | null
  updated_at: string | null
}

export interface MetaTokenInput {
  app_id: string
  app_name?: string | null
  business_id?: string | null
  business_name?: string | null
  system_user_token: string
  system_user_id?: string | null
  system_user_name?: string | null
  fb_page_id?: string | null
  fb_page_name?: string | null
  fb_page_token?: string | null
  ig_account_id?: string | null
  ig_username?: string | null
  ad_account_id?: string | null
  pixel_id?: string | null
}

export interface MetaValidationCheck {
  ok: boolean
  label: string
  detail: string | null
}

export interface MetaValidation {
  token_valid: boolean
  scopes: string[]
  app_id: string | null
  system_user_id: string | null
  system_user_name: string | null
  checks: MetaValidationCheck[]
  status: MetaStatus
}

/**
 * Entidades sincronizáveis hoje. As bloqueadas por App Review da Meta
 * (insights, comments, ads, leads) entrarão aqui quando a TI destravar.
 */
export type MetaSyncEntity =
  | 'ig_profile'
  | 'ig_media'
  | 'ig_post_insights'
  | 'ig_account_insights'
  | 'ig_comments'
  | 'fb_page'
  | 'fb_posts'
  | 'fb_post_insights'
  | 'fb_page_insights'
  | 'pixel'

export interface MetaSyncEntityResult {
  entity: MetaSyncEntity
  records: number
  job_id: number
  last_fired?: string | null
}

export interface MetaSyncAllResult {
  ok: Partial<Record<MetaSyncEntity, MetaSyncEntityResult>>
  errors: Partial<Record<MetaSyncEntity, string>>
}

// ─── Dashboard /marketing/visao-geral ─────────────────────────────
export interface MetaTopPost {
  post_external_id: string
  posted_at: string | null
  caption: string | null
  permalink: string | null
  media_url: string | null
  reach: number | null
  likes: number | null
  comments: number | null
  shares: number | null
  engagement_total: number | null
}

export interface MetaDashboardCard {
  available: boolean
  snapshot_date: string | null
  // IG / FB
  username: string | null
  display_name: string | null
  profile_picture_url: string | null
  followers: number | null
  follows: number | null
  total_posts: number | null
  fan_count: number | null
  category: string | null
  verification_status: string | null
  website: string | null
  biografia: string | null
  // Insights agregados (últimos 7d)
  reach_7d: number | null
  engagement_7d: number | null
  followers_gained_7d: number | null
  posts_7d: number | null
  // WoW (7d anteriores)
  reach_7d_prev: number | null
  engagement_7d_prev: number | null
  followers_gained_7d_prev: number | null
  posts_7d_prev: number | null
  top_posts: MetaTopPost[]
  // Pixel
  pixel_name: string | null
  pixel_last_fired_at: string | null
  pixel_days_idle: number | null
  pixel_is_unavailable: boolean | null
}

export interface MetaPendingItem {
  key: string
  label: string
  detail: string
  blocked_features: string[]
}

export interface MetaDashboard {
  has_connection: boolean
  token_validated_at: string | null
  business_name: string | null
  instagram: MetaDashboardCard
  facebook: MetaDashboardCard
  pixel: MetaDashboardCard
  pending: MetaPendingItem[]
}

// ─── Comentários IA (Sub-PR 21f) ──────────────────────────────────
export interface MetaComment {
  external_id: string
  autor: string | null
  texto: string
  commented_at: string | null
  post_external_id: string | null
  procedimento: string | null
  urgencia: 'alta' | 'media' | 'baixa' | null
}

export interface MetaCommentsInsights {
  period_days: number
  counts: {
    total: number
    leads_quentes: number
    duvidas_clinicas: number
    depoimentos: number
    reclamacoes: number
    objecoes: number
  }
  sentimento: Record<string, number>
  top_procedimentos: { procedimento: string; total: number }[]
  leads_quentes: MetaComment[]
  duvidas_clinicas: MetaComment[]
  reclamacoes: MetaComment[]
}
