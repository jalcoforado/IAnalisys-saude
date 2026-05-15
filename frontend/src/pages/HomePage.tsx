import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Sparkles } from 'lucide-react'

import { useAuth } from '@/modules/auth/AuthContext'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { homeService } from '@/services/home.service'
import { AgendaSummaryCard } from '@/modules/agenda/AgendaSummaryCard'
import { StrategicAgendaSection } from '@/modules/agenda/StrategicAgendaCard'
import { PendenciasCard } from '@/modules/agenda/PendenciasCard'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import SonIAInsightBanner from '@/components/sonia/SonIAInsightBanner'
import { useSonIA } from '@/components/sonia/SonIAContext'
import { InadimplenciaCriticaCard } from '@/modules/home/cards/InadimplenciaCriticaCard'
import { OrcamentosParadosCard } from '@/modules/home/cards/OrcamentosParadosCard'
import { RecallCard } from '@/modules/home/cards/RecallCard'
import { TopProfsCard } from '@/modules/home/cards/TopProfsCard'
import type { HomeDashboardResponse } from '@/types/home'

const fmtDateLong = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })
}
const fmtWeekday = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { weekday: 'long' })
}

const WELCOME_KEY = 'sonia.welcome.shown'

export default function HomePage() {
  usePageTitle('Início', 'Cockpit operacional', 'INÍCIO')
  const { user } = useAuth()
  const firstName = (user?.full_name || user?.email || '').split(/[\s.@]+/)[0]

  const q = useQuery({
    queryKey: ['home', 'dashboard'],
    queryFn: () => homeService.dashboard(),
    staleTime: 60_000,
  })

  const { publish, clear, setOpen } = useSonIA()

  useEffect(() => {
    if (!q.data) return
    const hour = new Date().getHours()
    const periodo = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'
    const nome = firstName || ''
    const headline = nome ? `${periodo}, ${nome}.` : `${periodo}.`

    publish({
      pageKey: '/',
      pageTitle: 'Início',
      data: {
        insight: {
          mood: 'default',
          headline: `${headline} Que bom te ver por aqui.`,
          detail:
            'Estou aqui no canto, sempre por perto. Pode me chamar quando quiser uma observação sobre alguma página — vou olhar com calma e te trazer o que achar relevante.',
        },
      },
    })

    return () => clear('/')
  }, [q.data, firstName, publish, clear])

  useEffect(() => {
    if (!q.data) return
    if (sessionStorage.getItem(WELCOME_KEY)) return
    const timers: number[] = []
    timers.push(window.setTimeout(() => {
      setOpen(true)
      sessionStorage.setItem(WELCOME_KEY, '1')
      // Auto-fecha 6s depois (tempo de leitura). Só na saudação automática —
      // se o usuário clica pra abrir, fica aberto até ele fechar.
      timers.push(window.setTimeout(() => setOpen(false), 6000))
    }, 1500))
    return () => timers.forEach((id) => clearTimeout(id))
  }, [q.data, setOpen])

  return (
    <main className="relative">
      <div
        aria-hidden
        className="absolute inset-0 pointer-events-none opacity-[0.4]"
        style={{
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(29, 78, 216, 0.08) 1px, transparent 0)',
          backgroundSize: '32px 32px',
        }}
      />
      <PageContainer as="div" gap={6} className="relative">
        <Greeting name={firstName} data={q.data} />

        {q.data && <SonIAInsightBanner data={q.data} firstName={firstName} />}

        {q.isLoading && (
          <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm flex items-center justify-center gap-2">
            <Loader2 size={16} className="animate-spin" /> Carregando seu cockpit…
          </div>
        )}
        {q.isError && (
          <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
            Erro ao carregar o cockpit. Tente atualizar a página.
          </div>
        )}
        {q.data && <CockpitGrid data={q.data} />}
      </PageContainer>
    </main>
  )
}

function Greeting({ name, data }: { name: string; data: HomeDashboardResponse | undefined }) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'
  const todayLong = data ? fmtDateLong(data.today_iso) : ''
  const weekday = data ? fmtWeekday(data.today_iso) : ''
  const wdCap = weekday ? weekday.charAt(0).toUpperCase() + weekday.slice(1) : ''

  return (
    <PageHeader
      eyebrow={greeting}
      title={`${name || 'Bem-vindo'}${wdCap ? ` · ${wdCap}` : ''}`}
      subtitle={todayLong}
      icon={<Sparkles size={20} />}
      actions={data && (
        <div className="bg-white/15 rounded-lg px-3 py-2 ring-1 ring-white/20">
          <div className="text-[10px] uppercase tracking-wide text-white/70 font-bold">Perfil</div>
          <div className="text-sm font-bold">{data.role_label}</div>
        </div>
      )}
    />
  )
}

function CockpitGrid({ data }: { data: HomeDashboardResponse }) {
  // Donos/gestores veem a visão estratégica (3 dias agregados + top riscos +
  // profs ociosos). Outros roles continuam com o resumo compacto de hoje.
  const isManager = ['manager', 'tenant_admin', 'saas_admin'].includes(data.role)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {isManager
        ? <StrategicAgendaSection />
        : data.agenda && <AgendaSummaryCard data={data.agenda} />}
      {data.pendencias && <PendenciasCard data={data.pendencias} />}
      {data.recall && <RecallCard data={data.recall} />}
      {data.top_profs_semana && <TopProfsCard data={data.top_profs_semana} />}
      {data.orcamentos_parados && <OrcamentosParadosCard data={data.orcamentos_parados} />}
      {data.inadimplencia_critica && <InadimplenciaCriticaCard data={data.inadimplencia_critica} />}
    </div>
  )
}
