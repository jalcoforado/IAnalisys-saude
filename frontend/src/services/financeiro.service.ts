import api from '@/services/api'
import type { FinanceiroOverviewResponse } from '@/types/financeiro'

export const financeiroService = {
  overview: (year: number, month: number) =>
    api
      .get<FinanceiroOverviewResponse>('/financeiro/overview', {
        params: { year, month },
      })
      .then((r) => r.data),
}
