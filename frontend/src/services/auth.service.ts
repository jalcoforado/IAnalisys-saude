import api from '@/services/api'
import type { LoginRequest, TokenResponse, UserMe } from '@/types/auth'

export const authService = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  me: () =>
    api.get<UserMe>('/auth/me').then((r) => r.data),
}
