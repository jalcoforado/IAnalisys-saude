import type { LucideIcon } from 'lucide-react'
import {
  BarChart3,
  Calendar,
  DollarSign,
  Home,
  RefreshCw,
  Settings,
  Sparkles,
  Stethoscope,
  Users,
} from 'lucide-react'

export interface MenuItem {
  /** Visível no menu. */
  label: string
  /** Ícone lucide. */
  icon: LucideIcon
  /** Rota direta — se omitido, vira só agrupador (precisa children). */
  path?: string
  /** Submenu suspenso — se presente, item abre dropdown em vez de navegar. */
  children?: MenuItem[]
  /** Visual cinza, sem clique — usar para sinalizar features futuras. */
  comingSoon?: boolean
}

/**
 * Menu principal do sistema. Cada entrada vira um item na topbar/sidebar.
 * Ordem reflete a jornada de uso: visão → operação → admin.
 */
export const MAIN_MENU: MenuItem[] = [
  {
    label: 'Início',
    icon: Home,
    path: '/',
  },
  {
    label: 'Análise',
    icon: BarChart3,
    children: [
      { label: 'Dashboard Executivo', icon: BarChart3, path: '/dashboard' },
      { label: 'Operacional', icon: Calendar, comingSoon: true },
      { label: 'Comercial', icon: DollarSign, comingSoon: true },
    ],
  },
  {
    label: 'Pacientes',
    icon: Users,
    comingSoon: true,
  },
  {
    label: 'Agenda',
    icon: Calendar,
    comingSoon: true,
  },
  {
    label: 'Clínico',
    icon: Stethoscope,
    comingSoon: true,
  },
  {
    label: 'IA Assistente',
    icon: Sparkles,
    comingSoon: true,
  },
  {
    label: 'Admin',
    icon: Settings,
    children: [
      { label: 'Sincronização', icon: RefreshCw, path: '/admin/sync' },
      { label: 'Configurações', icon: Settings, path: '/configuracoes' },
    ],
  },
]
