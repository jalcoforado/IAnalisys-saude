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
  AlertTriangle,
  Calendar,
  FileText,
  ListTodo,
  Phone,
  TrendingUp,
  Trophy,
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

export type WidgetCategory =
  | 'Agenda'
  | 'Pacientes'
  | 'Comercial'
  | 'Financeiro'
  | 'Operações'

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
