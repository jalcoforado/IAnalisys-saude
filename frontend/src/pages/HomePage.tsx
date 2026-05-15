import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Loader2, Sparkles } from 'lucide-react'

import { useAuth } from '@/modules/auth/AuthContext'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { homeService } from '@/services/home.service'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { useSonIA } from '@/components/sonia/SonIAContext'
import { CustomizableGrid } from '@/modules/home/CustomizableGrid'
import { buildHomeInsight } from '@/modules/home/sonia-home-insight'
import { useHomeLayout } from '@/modules/home/useHomeLayout'
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
  usePageTitle('Início', 'MY-Analisys · seu painel personalizado', 'INÍCIO')
  const { user } = useAuth()
  const firstName = (user?.full_name || user?.email || '').split(/[\s.@]+/)[0]

  const q = useQuery({
    queryKey: ['home', 'dashboard'],
    queryFn: () => homeService.dashboard(),
    staleTime: 60_000,
  })

  const layoutQuery = useHomeLayout()
  const widgetIds = (layoutQuery.data?.layout ?? []).map((i) => i.widget_id)

  const { publish, clear, setOpen } = useSonIA()

  useEffect(() => {
    if (!q.data) return
    publish({
      pageKey: '/',
      pageTitle: 'Início',
      data: { insight: buildHomeInsight(q.data, widgetIds) },
    })
    return () => clear('/')
    // widgetIds é derivado de layoutQuery.data — usamos a versão como sinal de mudança
    // pra evitar re-publicar a cada render (array novo a cada vez).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data, layoutQuery.data?.version, publish, clear])

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

        {q.isLoading && (
          <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm flex items-center justify-center gap-2">
            <Loader2 size={16} className="animate-spin" /> Carregando seu painel…
          </div>
        )}
        {q.isError && (
          <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
            Erro ao carregar o painel. Tente atualizar a página.
          </div>
        )}
        {q.data && user && (
          <CustomizableGrid
            homeData={q.data}
            userPermissions={user.permissions}
            firstName={firstName}
          />
        )}
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
