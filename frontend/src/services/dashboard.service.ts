import api from '@/services/api'
import type {
  DashboardExecutivoResponse,
  DrillDownResponse,
  KpiId,
} from '@/types/dashboard'

export const dashboardService = {
  executivo: (year: number, month: number) =>
    api
      .get<DashboardExecutivoResponse>('/dashboard/executivo', {
        params: { year, month },
      })
      .then((r) => r.data),

  itens: (kpi: KpiId, year: number, month: number, limit = 200, offset = 0) =>
    api
      .get<DrillDownResponse>('/dashboard/executivo/itens', {
        params: { kpi, year, month, limit, offset },
      })
      .then((r) => r.data),
}
