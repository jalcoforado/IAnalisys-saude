import api from '@/services/api'
import type {
  AnaliseComercialResponse,
  AnaliseFinanceiroResponse,
  PrazoAuditResponse,
} from '@/types/analise'

export type AIInsightsResponse = {
  narrative: string
  model: string
}

export const analiseService = {
  financeiro: (year: number, month: number) =>
    api
      .get<AnaliseFinanceiroResponse>('/analise/financeiro', {
        params: { year, month },
      })
      .then((r) => r.data),

  // Auditoria do prazo: lista de parcelas para conferência manual.
  // bucketMin/bucketMax (inclusivos) filtram por installments_count.
  financeiroPrazosDetalhe: (
    year: number,
    month: number,
    opts?: { bucketMin?: number; bucketMax?: number; limit?: number },
  ) =>
    api
      .get<PrazoAuditResponse>('/analise/financeiro/prazos-detalhe', {
        params: {
          year,
          month,
          bucket_min: opts?.bucketMin,
          bucket_max: opts?.bucketMax,
          limit: opts?.limit ?? 1000,
        },
      })
      .then((r) => r.data),

  // Insights via IA — chamada explícita por clique. NÃO chamar automaticamente.
  financeiroAIInsights: (year: number, month: number) =>
    api
      .post<AIInsightsResponse>(
        '/analise/financeiro/ai-insights',
        null,
        { params: { year, month } },
      )
      .then((r) => r.data),

  comercial: (year: number, month: number) =>
    api
      .get<AnaliseComercialResponse>('/analise/comercial', {
        params: { year, month },
      })
      .then((r) => r.data),

  comercialAIInsights: (year: number, month: number) =>
    api
      .post<AIInsightsResponse>(
        '/analise/comercial/ai-insights',
        null,
        { params: { year, month } },
      )
      .then((r) => r.data),
}
