import type { LucideIcon } from 'lucide-react'
import {
  BarChart3,
  Building2,
  Calendar,
  DollarSign,
  Home,
  RefreshCw,
  Settings,
  ShieldCheck,
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
  /** Permission necessária — se ausente do usuário, item some do menu. saas_admin é bypass. */
  permission?: string
  /** Permite quando tem QUALQUER uma. */
  permissionAny?: string[]
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
    permissionAny: ['dashboard.read', 'financeiro.read'],
    children: [
      { label: 'Financeiro', icon: DollarSign, path: '/analise/financeiro', permission: 'dashboard.read' },
      { label: 'Comercial', icon: BarChart3, path: '/analise/comercial', permission: 'dashboard.read' },
      { label: 'Pacientes', icon: Users, comingSoon: true, permission: 'dashboard.read' },
      { label: 'Fluxo de Caixa', icon: DollarSign, path: '/financeiro', permission: 'financeiro.read' },
      // Preservado temporariamente até os 3 dashs novos cobrirem 100%
      { label: 'Visão Consolidada (legado)', icon: BarChart3, path: '/dashboard', permission: 'dashboard.read' },
    ],
  },
  {
    label: 'Pacientes',
    icon: Users,
    comingSoon: true,
    permission: 'pacientes.read',
  },
  {
    label: 'Agenda',
    icon: Calendar,
    path: '/agenda',
    permission: 'agenda.read',
  },
  {
    label: 'Clínico',
    icon: Stethoscope,
    comingSoon: true,
    permission: 'clinico.read',
  },
  {
    label: 'IA Assistente',
    icon: Sparkles,
    comingSoon: true,
    permission: 'ia.use',
  },
  {
    label: 'Admin',
    icon: Settings,
    permissionAny: ['empresa.settings.read', 'sync.run', 'usuarios.read', 'empresa.permissions.manage'],
    children: [
      { label: 'Empresa', icon: Building2, path: '/empresa/configuracoes', permission: 'empresa.settings.read' },
      { label: 'Usuários', icon: Users, path: '/empresa/usuarios', permission: 'usuarios.read' },
      { label: 'Permissões', icon: ShieldCheck, path: '/empresa/permissoes', permission: 'empresa.permissions.manage' },
      { label: 'Sincronização', icon: RefreshCw, path: '/admin/sync', permission: 'sync.run' },
      { label: 'Preferências', icon: Settings, path: '/configuracoes' },
    ],
  },
]
