export interface TenantSettings {
  id: string
  slug: string
  name: string

  // Identidade Visual
  logo_url: string | null
  favicon_url: string | null
  login_background_url: string | null
  primary_color: string | null
  secondary_color: string | null

  // Dados da Empresa
  legal_name: string | null
  tax_id: string | null
  email: string | null
  phone: string | null
  whatsapp: string | null
  website: string | null

  // Endereço
  address_zip: string | null
  address_street: string | null
  address_number: string | null
  address_complement: string | null
  address_district: string | null
  address_city: string | null
  address_state: string | null
}

export interface TenantSettingsUpdate {
  name?: string
  legal_name?: string | null
  tax_id?: string | null
  email?: string | null
  phone?: string | null
  whatsapp?: string | null
  website?: string | null
  primary_color?: string | null
  secondary_color?: string | null
  address_zip?: string | null
  address_street?: string | null
  address_number?: string | null
  address_complement?: string | null
  address_district?: string | null
  address_city?: string | null
  address_state?: string | null
}

export type UploadKind = 'logo' | 'favicon' | 'login_background'

export interface UploadResponse {
  kind: UploadKind
  url: string
  size_bytes: number
}
