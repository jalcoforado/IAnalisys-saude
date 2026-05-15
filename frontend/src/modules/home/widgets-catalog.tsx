/**
 * Catálogo de widgets do "Meu IAnalisys" (MY-Analisys).
 *
 * Toda feature/widget novo entra aqui — esta é a única fonte da verdade pra
 * o `CustomizableGrid` e pro `WidgetPicker`. Cada entrada declara:
 *   - id          : chave persistida no banco
 *   - name        : rótulo visível na gaveta
 *   - description : texto explicativo no picker
 *   - category    : agrupador na gaveta
 *   - permission  : chave do RBAC; o front filtra widgets por user.permissions
 *   - defaultSize : tamanho ao adicionar
 *   - minSize     : limite de redimensionamento
 *   - icon        : Lucide pra ilustrar na gaveta
 *   - render      : como pintar com os dados atuais (HomeDashboardResponse)
 */
import {
  AlertCircle,
  AlertTriangle,
  Banknote,
  Calendar,
  CalendarCheck,
  DollarSign,
  FileText,
  Heart,
  ListTodo,
  Percent,
  Phone,
  Receipt,
  Repeat,
  TrendingUp,
  Trophy,
  UserMinus,
  Users,
  Wallet,
  type LucideIcon,
} from 'lucide-react'

import { AgendaSummaryCard } from '@/modules/agenda/AgendaSummaryCard'
import { StrategicAgendaSection } from '@/modules/agenda/StrategicAgendaCard'
import { PendenciasCard } from '@/modules/agenda/PendenciasCard'
import type { HomeDashboardResponse } from '@/types/home'

import { InadimplenciaCriticaCard } from './cards/InadimplenciaCriticaCard'
import { OrcamentosParadosCard } from './cards/OrcamentosParadosCard'
import { RecallCard } from './cards/RecallCard'
import { TopProfsCard } from './cards/TopProfsCard'
import { SaldoBancarioCard } from './widgets/SaldoBancarioCard'
import {
  KpiConversaoFinanceira,
  KpiFaturamento,
  KpiRecebido,
  KpiTicketMedio,
} from './widgets/kpis-financeiros'
import {
  KpiAbsenteismo,
  KpiConsultas,
  KpiConversaoComercial,
  KpiPacientesUnicos,
} from './widgets/kpis-comerciais'
import {
  KpiEmRisco,
  KpiLtvMedio,
  KpiPacientesAtivos,
  KpiRecorrencia,
} from './widgets/kpis-pacientes'

export type WidgetCategory =
  | 'Agenda'
  | 'Pacientes'
  | 'Comercial'
  | 'Financeiro'
  | 'Operações'
  | 'KPIs Financeiros'
  | 'KPIs Comerciais'
  | 'KPIs Pacientes'

export interface WidgetMeta {
  id: string
  name: string
  description: string
  category: WidgetCategory
  permission: string
  defaultSize: { w: number; h: number }
  minSize: { w: number; h: number }
  icon: LucideIcon
  /** null = sem dados disponíveis no fetch atual (front mostra placeholder). */
  render: (homeData: HomeDashboardResponse) => React.ReactElement | null
}

export const WIDGET_CATALOG: WidgetMeta[] = [
  {
    id: 'agenda_strategic',
    name: 'Agenda estratégica (3 dias)',
    description:
      'Visão consolidada Hoje + Amanhã + Depois com KPIs, riscos e profissionais ociosos.',
    category: 'Agenda',
    permission: 'dashboard.read',
    defaultSize: { w: 12, h: 5 },
    minSize: { w: 6, h: 4 },
    icon: TrendingUp,
    render: () => <StrategicAgendaSection />,
  },
  {
    id: 'agenda_summary',
    name: 'Resumo da agenda',
    description: 'KPIs do dia + próxima consulta + breakdown de status.',
    category: 'Agenda',
    permission: 'agenda.read',
    defaultSize: { w: 4, h: 4 },
    minSize: { w: 3, h: 3 },
    icon: Calendar,
    render: (d) => (d.agenda ? <AgendaSummaryCard data={d.agenda} /> : null),
  },
  {
    id: 'pendencias',
    name: 'Pendências operacionais',
    description:
      'Tags do Clinicorp agregadas: orçamentos pendentes, retornos, remarcações.',
    category: 'Operações',
    permission: 'agenda.read',
    defaultSize: { w: 12, h: 4 },
    minSize: { w: 6, h: 3 },
    icon: ListTodo,
    render: (d) => (d.pendencias ? <PendenciasCard data={d.pendencias} /> : null),
  },
  {
    id: 'recall',
    name: 'Pacientes pra ligar',
    description:
      'Pacientes que vinham regularmente e estão atrasados — oportunidade de recall.',
    category: 'Pacientes',
    permission: 'pacientes.read',
    defaultSize: { w: 8, h: 5 },
    minSize: { w: 4, h: 3 },
    icon: Phone,
    render: (d) => (d.recall ? <RecallCard data={d.recall} /> : null),
  },
  {
    id: 'top_profs',
    name: 'Top profissionais (semana)',
    description: 'Ranking semanal por orçamento aprovado.',
    category: 'Comercial',
    permission: 'dashboard.read',
    defaultSize: { w: 4, h: 5 },
    minSize: { w: 3, h: 3 },
    icon: Trophy,
    render: (d) =>
      d.top_profs_semana ? <TopProfsCard data={d.top_profs_semana} /> : null,
  },
  {
    id: 'orcamentos_parados',
    name: 'Orçamentos parados',
    description: 'Aprovados há 30-90 dias sem nova consulta — pipeline parado.',
    category: 'Comercial',
    permission: 'financeiro.read',
    defaultSize: { w: 8, h: 5 },
    minSize: { w: 4, h: 3 },
    icon: FileText,
    render: (d) =>
      d.orcamentos_parados ? (
        <OrcamentosParadosCard data={d.orcamentos_parados} />
      ) : null,
  },
  {
    id: 'inadimplencia_critica',
    name: 'Inadimplência crítica',
    description: 'Parcelas vencidas há +60d com valor +R$ 500.',
    category: 'Financeiro',
    permission: 'financeiro.read',
    defaultSize: { w: 4, h: 5 },
    minSize: { w: 3, h: 3 },
    icon: AlertTriangle,
    render: (d) =>
      d.inadimplencia_critica ? (
        <InadimplenciaCriticaCard data={d.inadimplencia_critica} />
      ) : null,
  },

  // ── KPIs Financeiros (mês atual — /analise/financeiro) ──────
  {
    id: 'kpi_fin_faturamento',
    name: 'Faturamento (mês atual)',
    description: 'Total aprovado no mês + variação MoM/YoY + sparkline 12m.',
    category: 'KPIs Financeiros',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: DollarSign,
    render: () => <KpiFaturamento />,
  },
  {
    id: 'kpi_fin_recebido',
    name: 'Recebido (mês atual)',
    description: 'Valor efetivamente recebido no mês.',
    category: 'KPIs Financeiros',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Wallet,
    render: () => <KpiRecebido />,
  },
  {
    id: 'kpi_fin_ticket',
    name: 'Ticket médio',
    description: 'Faturamento dividido pela quantidade de orçamentos aprovados.',
    category: 'KPIs Financeiros',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Receipt,
    render: () => <KpiTicketMedio />,
  },
  {
    id: 'kpi_fin_conversao',
    name: 'Conversão financeira (R$)',
    description: 'R$ aprovado / R$ gerado no mês.',
    category: 'KPIs Financeiros',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Percent,
    render: () => <KpiConversaoFinanceira />,
  },

  // ── KPIs Comerciais (mês atual — /analise/comercial) ───────
  {
    id: 'kpi_com_consultas',
    name: 'Consultas (mês atual)',
    description: 'Total de consultas efetivas no mês.',
    category: 'KPIs Comerciais',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: CalendarCheck,
    render: () => <KpiConsultas />,
  },
  {
    id: 'kpi_com_absenteismo',
    name: 'Absenteísmo',
    description: 'Faltas / (efetivas + faltas). Quanto menor, melhor.',
    category: 'KPIs Comerciais',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: UserMinus,
    render: () => <KpiAbsenteismo />,
  },
  {
    id: 'kpi_com_conversao',
    name: 'Consulta → orçamento',
    description: 'Taxa de orçamentos gerados a partir das consultas efetivas.',
    category: 'KPIs Comerciais',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Percent,
    render: () => <KpiConversaoComercial />,
  },
  {
    id: 'kpi_com_pacientes_unicos',
    name: 'Pacientes únicos',
    description: 'Pacientes distintos atendidos no mês.',
    category: 'KPIs Comerciais',
    permission: 'dashboard.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Users,
    render: () => <KpiPacientesUnicos />,
  },

  // ── KPIs Pacientes (mês atual — /analise/pacientes) ────────
  {
    id: 'kpi_pac_ativos',
    name: 'Pacientes ativos',
    description: 'Pacientes com visita há menos de 90 dias.',
    category: 'KPIs Pacientes',
    permission: 'pacientes.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Heart,
    render: () => <KpiPacientesAtivos />,
  },
  {
    id: 'kpi_pac_recorrencia',
    name: 'Recorrência',
    description: '% de atendidos no mês que já eram da base.',
    category: 'KPIs Pacientes',
    permission: 'pacientes.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Repeat,
    render: () => <KpiRecorrencia />,
  },
  {
    id: 'kpi_pac_ltv',
    name: 'LTV médio',
    description: 'Faturamento histórico dividido pela base ativa.',
    category: 'KPIs Pacientes',
    permission: 'pacientes.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: TrendingUp,
    render: () => <KpiLtvMedio />,
  },
  {
    id: 'kpi_pac_em_risco',
    name: 'Em risco',
    description: 'Pacientes no bucket 90-180d sem visita.',
    category: 'KPIs Pacientes',
    permission: 'pacientes.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: AlertCircle,
    render: () => <KpiEmRisco />,
  },

  // ── Caixa / Bancos ─────────────────────────────────────────
  {
    id: 'saldo_bancario',
    name: 'Saldo bancário consolidado',
    description: 'Saldo total das contas + breakdown bancos/caixinhas.',
    category: 'Financeiro',
    permission: 'financeiro.read',
    defaultSize: { w: 3, h: 5 },
    minSize: { w: 3, h: 4 },
    icon: Banknote,
    render: () => <SaldoBancarioCard />,
  },
]

export const findWidget = (id: string): WidgetMeta | undefined =>
  WIDGET_CATALOG.find((w) => w.id === id)

/** Filtra o catálogo pelas permissions do user logado. */
export const filterByPermissions = (
  permissions: string[],
): WidgetMeta[] => {
  const set = new Set(permissions)
  return WIDGET_CATALOG.filter((w) => set.has(w.permission))
}
