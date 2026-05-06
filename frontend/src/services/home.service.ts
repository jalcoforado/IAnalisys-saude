import api from '@/services/api'
import type {
  AgendaSection,
  HomeDashboardResponse,
  StrategicOverview,
} from '@/types/home'

export interface AgendaAISummaryResponse {
  narrative: string
  model: string
}

export const homeService = {
  dashboard: () =>
    api.get<HomeDashboardResponse>('/home/dashboard').then((r) => r.data),

  /** Agenda de um dia específico (default: hoje). `date` é YYYY-MM-DD.
   * Backend bloqueia datas fora da janela [hoje, hoje+2]. */
  agenda: (date?: string) =>
    api
      .get<AgendaSection>('/home/agenda', { params: date ? { date } : {} })
      .then((r) => r.data),

  /** Visão estratégica consolidada (Hoje + Amanhã + Depois) com KPIs
   * agregados, top pacientes a confirmar e profs ociosos. Pra HomePage. */
  agendaStrategic: () =>
    api.get<StrategicOverview>('/home/agenda-strategic').then((r) => r.data),

  /** Sub-PR 17b — Prosa narrativa da agenda gerada pelo Claude.
   * POST porque chama API paga; cache 5min em Redis no backend. */
  agendaAISummary: () =>
    api
      .post<AgendaAISummaryResponse>('/home/agenda/ai-summary')
      .then((r) => r.data),
}
