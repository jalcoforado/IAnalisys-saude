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
  | 'fb_page'
  | 'fb_posts'
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
