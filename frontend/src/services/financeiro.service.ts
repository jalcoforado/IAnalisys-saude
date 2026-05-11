import api from '@/services/api'
import type { DreResponse, FinanceiroOverviewResponse } from '@/types/financeiro'

export const financeiroService = {
  overview: (year: number, month: number) =>
    api
      .get<FinanceiroOverviewResponse>('/financeiro/overview', {
        params: { year, month },
      })
      .then((r) => r.data),

  /** DRE estruturada com 3 níveis de drill (grupo → subgrupo → categoria
   * plana). Mais leve que overview — usado pela página /financeiro/dre. */
  dre: (year: number, month: number) =>
    api
      .get<DreResponse>('/financeiro/dre', { params: { year, month } })
      .then((r) => r.data),
}
