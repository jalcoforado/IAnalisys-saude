import api from '@/services/api'
import type {
  AnaliseComercialResponse,
  AnaliseFinanceiroResponse,
  AnalisePacientesResponse,
  CaptacaoOrigemResponse,
  OrcamentoStatusResponse,
  PacienteHistoricoResponse,
  PrazoAuditResponse,
} from '@/types/analise'
import type { InteligenciaPacientesResponse } from '@/types/pacientes-inteligencia'

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

  // Auditoria por orçamento: 1 linha por orçamento APROVADO no mês com
  // contratado / lançado / pago + status financeiro + parcelas embutidas.
  // Usado pelo modal "Auditar" do card "Prazo de Recebimento".
  financeiroOrcamentosStatus: (year: number, month: number) =>
    api
      .get<OrcamentoStatusResponse>('/analise/financeiro/orcamentos-status', {
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

  pacientes: (year: number, month: number) =>
    api
      .get<AnalisePacientesResponse>('/analise/pacientes', {
        params: { year, month },
      })
      .then((r) => r.data),

  pacienteHistorico: (patientExternalId: number) =>
    api
      .get<PacienteHistoricoResponse>(
        `/analise/pacientes/${patientExternalId}/historico`,
      )
      .then((r) => r.data),

  pacientesCaptacao: () =>
    api
      .get<CaptacaoOrigemResponse>('/analise/pacientes/captacao')
      .then((r) => r.data),

  pacientesInteligencia: (days = 90) =>
    api
      .get<InteligenciaPacientesResponse>('/analise/pacientes/inteligencia', {
        params: { days },
      })
      .then((r) => r.data),
}
