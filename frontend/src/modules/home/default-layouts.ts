/**
 * Layout default do "Meu IAnalisys" por role.
 *
 * Aplicado quando o usuário acessa pela primeira vez (GET /home/layout
 * retorna `layout: null`) ou quando clica em "Resetar pro padrão".
 *
 * Grid de 12 colunas, rowHeight ~60px. Coordenadas {x, y, w, h}.
 */
import type { HomeLayoutItem } from '@/services/home.service'

const DONO: HomeLayoutItem[] = [
  { widget_id: 'agenda_strategic',     x: 0, y: 0,  w: 12, h: 5 },
  { widget_id: 'pendencias',           x: 0, y: 5,  w: 12, h: 4 },
  { widget_id: 'recall',               x: 0, y: 9,  w: 8,  h: 5 },
  { widget_id: 'top_profs',            x: 8, y: 9,  w: 4,  h: 5 },
  { widget_id: 'orcamentos_parados',   x: 0, y: 14, w: 8,  h: 5 },
  { widget_id: 'inadimplencia_critica',x: 8, y: 14, w: 4,  h: 5 },
]

const FINANCIAL: HomeLayoutItem[] = [
  { widget_id: 'agenda_summary',       x: 0, y: 0, w: 4,  h: 4 },
  { widget_id: 'inadimplencia_critica',x: 4, y: 0, w: 4,  h: 4 },
  { widget_id: 'top_profs',            x: 8, y: 0, w: 4,  h: 4 },
  { widget_id: 'orcamentos_parados',   x: 0, y: 4, w: 12, h: 5 },
]

const COMMERCIAL: HomeLayoutItem[] = [
  { widget_id: 'agenda_summary', x: 0, y: 0, w: 4,  h: 4 },
  { widget_id: 'recall',         x: 4, y: 0, w: 8,  h: 4 },
  { widget_id: 'top_profs',      x: 0, y: 4, w: 4,  h: 5 },
  { widget_id: 'pendencias',     x: 0, y: 9, w: 12, h: 3 },
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
