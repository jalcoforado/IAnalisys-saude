/**
 * Layout default do "Meu IAnalisys" por role.
 *
 * Aplicado quando o usuário acessa pela primeira vez (GET /home/layout
 * retorna `layout: null`) ou quando clica em "Resetar pro padrão".
 *
 * Grid de 12 colunas, rowHeight ~60px. Coordenadas {x, y, w, h}.
 */
import type { HomeLayoutItem } from '@/services/home.service'

// Padrão de alturas:
//   h=4 → cards compactos (KPIs, Agenda summary, Saldo)
//   h=5 → blocos com listas/gráficos médios
//   h=6 → listas longas (Top LTV, Top procedimentos)
const DONO: HomeLayoutItem[] = [
  // Strategic Agenda renderiza 3 dias × KPIs + 2 listas internas → precisa de h alto.
  { widget_id: 'agenda_strategic',     x: 0, y: 0,  w: 12, h: 12 },
  { widget_id: 'pendencias',           x: 0, y: 12, w: 12, h: 5 },
  { widget_id: 'recall',               x: 0, y: 17, w: 8,  h: 6 },
  { widget_id: 'top_profs',            x: 8, y: 17, w: 4,  h: 6 },
  { widget_id: 'orcamentos_parados',   x: 0, y: 23, w: 8,  h: 6 },
  { widget_id: 'inadimplencia_critica',x: 8, y: 23, w: 4,  h: 6 },
]

const FINANCIAL: HomeLayoutItem[] = [
  { widget_id: 'kpi_fin_faturamento',  x: 0, y: 0, w: 3,  h: 4 },
  { widget_id: 'kpi_fin_recebido',     x: 3, y: 0, w: 3,  h: 4 },
  { widget_id: 'saldo_bancario',       x: 6, y: 0, w: 3,  h: 4 },
  { widget_id: 'inadimplencia_critica',x: 9, y: 0, w: 3,  h: 4 },
  { widget_id: 'orcamentos_parados',   x: 0, y: 4, w: 12, h: 5 },
]

const COMMERCIAL: HomeLayoutItem[] = [
  { widget_id: 'agenda_summary',      x: 0, y: 0, w: 4,  h: 4 },
  { widget_id: 'kpi_com_consultas',   x: 4, y: 0, w: 4,  h: 4 },
  { widget_id: 'kpi_com_conversao',   x: 8, y: 0, w: 4,  h: 4 },
  { widget_id: 'recall',              x: 0, y: 4, w: 8,  h: 5 },
  { widget_id: 'top_profs',           x: 8, y: 4, w: 4,  h: 5 },
]

const OPERATIONS: HomeLayoutItem[] = [
  { widget_id: 'agenda_summary', x: 0, y: 0, w: 4, h: 4 },
  { widget_id: 'pendencias',     x: 4, y: 0, w: 8, h: 4 },
]

export const DEFAULT_LAYOUTS: Record<string, HomeLayoutItem[]> = {
  saas_admin:   DONO,
  tenant_admin: DONO,
  manager:      DONO,
  financial:    FINANCIAL,
  commercial:   COMMERCIAL,
  operations:   OPERATIONS,
}

export const getDefaultLayoutForRole = (role: string): HomeLayoutItem[] => {
  return DEFAULT_LAYOUTS[role] ?? OPERATIONS
}
