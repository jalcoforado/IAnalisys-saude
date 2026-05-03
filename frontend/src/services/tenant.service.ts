import api from '@/services/api'
import type {
  TenantSettings,
  TenantSettingsUpdate,
  UploadKind,
  UploadResponse,
} from '@/types/tenant'

export const tenantService = {
  getSettings: () => api.get<TenantSettings>('/tenant/settings').then((r) => r.data),

  updateSettings: (payload: TenantSettingsUpdate) =>
    api.put<TenantSettings>('/tenant/settings', payload).then((r) => r.data),

  uploadAsset: async (kind: UploadKind, file: File): Promise<UploadResponse> => {
    // Usa fetch nativo em vez de axios pra upload — o axios estava
    // tentando serializar FormData como JSON por causa do Content-Type
    // default do interceptor. fetch + FormData = browser preenche o
    // boundary automaticamente.
    const formData = new FormData()
    formData.append('file', file)
    const token = localStorage.getItem('access_token') || ''
    const res = await fetch(`/api/v1/tenant/uploads/${kind}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })
    if (!res.ok) {
      let detail = `HTTP ${res.status}`
      try {
        const body = await res.json()
        if (body?.detail) detail = body.detail
      } catch { /* ignore */ }
      throw new Error(detail)
    }
    return res.json()
  },

  deleteAsset: (kind: UploadKind) =>
    api.delete(`/tenant/uploads/${kind}`).then(() => undefined),
}
