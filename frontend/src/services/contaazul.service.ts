import api from '@/services/api'
import type { ContaAzulStatus } from '@/types/contaazul'

export const contaAzulService = {
  status: () =>
    api.get<ContaAzulStatus>('/contaazul/status').then((r) => r.data),

  authUrl: () =>
    api.get<{ auth_url: string }>('/contaazul/auth').then((r) => r.data),

  refresh: () =>
    api.post<ContaAzulStatus>('/contaazul/refresh').then((r) => r.data),

  disconnect: () =>
    api.delete('/contaazul/disconnect').then(() => undefined),
}
