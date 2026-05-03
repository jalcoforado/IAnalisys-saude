import { Link } from 'react-router-dom'
import {
  ArrowRight,
  BarChart3,
  Calendar,
  DollarSign,
  RefreshCw,
  Settings,
  Sparkles,
  Stethoscope,
  Users,
} from 'lucide-react'

import { useAuth } from '@/modules/auth/AuthContext'
import { usePageTitle } from '@/contexts/PageTitleContext'

const QUICK_LINKS = [
  {
    title: 'Dashboard Executivo',
    description: 'KPIs estratégicos, funil comercial, análise de pacientes (ABC, churn, LTV)',
    to: '/dashboard',
    icon: BarChart3,
    accent: 'from-primary-600 to-primary-800',
    iconBg: 'bg-white/15 text-white',
    badge: 'Disponível',
    available: true,
  },
  {
    title: 'Sincronização',
    description: 'Importar dados do Clinicorp · status por entidade · pipeline CORE+ANALYTICS',
    to: '/admin/sync',
    icon: RefreshCw,
    accent: 'from-neutral-100 to-white border-neutral-200 border',
    iconBg: 'bg-primary-50 text-primary-700',
    badge: 'Disponível',
    available: true,
    light: true,
  },
  {
    title: 'Configurações',
    description: 'Personalizar layout, cores e preferências de visualização',
    to: '/configuracoes',
    icon: Settings,
    accent: 'from-neutral-100 to-white border-neutral-200 border',
    iconBg: 'bg-primary-50 text-primary-700',
    badge: 'Disponível',
    available: true,
    light: true,
  },
]

const COMING_SOON = [
  { title: 'Pacientes', description: 'Cadastro, histórico e segmentação', icon: Users },
  { title: 'Agenda', description: 'Visão de agendamentos e ocupação', icon: Calendar },
  { title: 'Clínico', description: 'Tratamentos, evolução e prontuário', icon: Stethoscope },
  { title: 'Financeiro', description: 'Contas a pagar/receber e DRE', icon: DollarSign },
  { title: 'IA Assistente', description: 'Chat com sua base via Claude + DeepSeek', icon: Sparkles },
]

export default function HomePage() {
  usePageTitle('Início', 'Visão geral da plataforma', 'INÍCIO')
  const { user } = useAuth()
  const firstName = (user?.full_name || user?.email || '').split(/[\s.@]+/)[0]
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'

  return (
    <main className="px-6 py-8 max-w-7xl mx-auto space-y-8">
      {/* Saudação + visão rápida */}
      <section>
        <div className="text-sm text-neutral-500">{greeting},</div>
        <h1 className="text-2xl md:text-3xl font-bold text-neutral-900 mt-0.5">
          {firstName ? `${firstName} 👋` : 'Bem-vindo'}
        </h1>
        <p className="text-sm text-neutral-600 mt-2 max-w-2xl">
          Plataforma de inteligência analítica para clínicas odontológicas. Explore os módulos
          disponíveis abaixo ou acesse diretamente o dashboard executivo.
        </p>
      </section>

      {/* Quick links destacados */}
      <section>
        <div className="text-xs uppercase tracking-wide text-neutral-500 font-semibold mb-3">Acesso rápido</div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {QUICK_LINKS.map((link) => {
            const Icon = link.icon
            const isLight = (link as any).light
            return (
              <Link
                key={link.title}
                to={link.to}
                className={`relative overflow-hidden rounded-xl shadow-md hover:shadow-lg transition-all hover:-translate-y-0.5 group ${
                  isLight
                    ? 'bg-white border border-neutral-200'
                    : `bg-gradient-to-br ${link.accent} text-white`
                }`}
              >
                {!isLight && (
                  <>
                    <div className="absolute -right-6 -top-6 w-24 h-24 bg-white/10 rounded-full" />
                    <div className="absolute -right-12 top-12 w-32 h-32 bg-white/5 rounded-full" />
                  </>
                )}
                <div className="relative p-5">
                  <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${link.iconBg}`}>
                    <Icon size={20} />
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-2">
                    <h3 className={`text-base font-bold ${isLight ? 'text-neutral-900' : 'text-white'}`}>{link.title}</h3>
                    <ArrowRight size={16} className={`${isLight ? 'text-neutral-400' : 'text-white/70'} group-hover:translate-x-1 transition-transform`} />
                  </div>
                  <p className={`text-xs mt-1 ${isLight ? 'text-neutral-500' : 'text-white/80'}`}>{link.description}</p>
                </div>
              </Link>
            )
          })}
        </div>
      </section>

      {/* Em breve */}
      <section>
        <div className="text-xs uppercase tracking-wide text-neutral-500 font-semibold mb-3">Próximos módulos</div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {COMING_SOON.map((m) => {
            const Icon = m.icon
            return (
              <div key={m.title} className="bg-white border border-dashed border-neutral-300 rounded-xl p-4 opacity-70">
                <div className="w-9 h-9 rounded-lg bg-neutral-100 text-neutral-500 flex items-center justify-center">
                  <Icon size={16} />
                </div>
                <div className="mt-3 flex items-center gap-1.5">
                  <h3 className="text-sm font-semibold text-neutral-700">{m.title}</h3>
                  <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-warning-bg text-warning-text font-medium">soon</span>
                </div>
                <p className="text-[11px] text-neutral-500 mt-0.5">{m.description}</p>
              </div>
            )
          })}
        </div>
      </section>
    </main>
  )
}
