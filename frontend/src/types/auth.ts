export interface UserMe {
  id: string
  email: string
  full_name: string
  is_active: boolean
  is_saas_admin: boolean
  tenant_id: string
  role: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export interface LoginRequest {
  email: string
  password: string
  tenant_id: string
}
