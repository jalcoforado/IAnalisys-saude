import api from '@/services/api'
import type { DashboardExecutivoResponse } from '@/types/dashboard'

export const dashboardService = {
  executivo: (year: number, month: number) =>
    api
      .get<DashboardExecutivoResponse>('/dashboard/executivo', {
        params: { year, month },
      })
      .then((r) => r.data),
}
