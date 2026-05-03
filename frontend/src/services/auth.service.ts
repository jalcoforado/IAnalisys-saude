import api from '@/services/api'
import type { LoginRequest, TokenResponse, UserMe } from '@/types/auth'

interface GenericMessage {
  message: string
}

export const authService = {
  login: (data: LoginRequest) =>
    api.post<TokenResponse>('/auth/login', data).then((r) => r.data),

  me: () =>
    api.get<UserMe>('/auth/me').then((r) => r.data),

  requestPasswordReset: (email: string) =>
    api
      .post<GenericMessage>('/auth/password-reset/request', { email })
      .then((r) => r.data),

  confirmPasswordReset: (token: string, newPassword: string) =>
    api
      .post<GenericMessage>('/auth/password-reset/confirm', {
        token,
        new_password: newPassword,
      })
      .then((r) => r.data),
}
