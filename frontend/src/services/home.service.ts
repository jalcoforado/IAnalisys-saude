import api from '@/services/api'
import type { HomeDashboardResponse } from '@/types/home'

export const homeService = {
  dashboard: () =>
    api.get<HomeDashboardResponse>('/home/dashboard').then((r) => r.data),
}
