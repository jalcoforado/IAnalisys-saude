import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle,
  CalendarClock,
  Clock,
  Crown,
  FileText,
  Loader2,
  Phone,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
} from 'lucide-react'

import { useAuth } from '@/modules/auth/AuthContext'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { homeService } from '@/services/home.service'
import type {
  AgendaItem,
  AgendaSection,
  HomeDashboardResponse,
  InadimplenciaCriticaSection,
  OrcamentosParadosSection,
  RecallItem,
  RecallSection,
  TopProfsSemanaSection,
} from '@/types/home'

// ── helpers ───────────────────────────────────────────────────

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000) {
    if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
    return `R$ ${(n / 1_000).toFixed(0)}k`
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
  }).format(n)
}
const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtDateLong = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })
}
const fmtDateShort = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}
const fmtWeekday = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { weekday: 'long' })
}
const initials = (name: string): string => {
  const parts = name.replace(/\*/g, '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0][0].toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

// ── página ────────────────────────────────────────────────────

export default function HomePage() {
  usePageTitle('Início', 'Cockpit operacional', 'INÍCIO')
  const { user } = useAuth()
  const firstName = (user?.full_name || user?.email || '').split(/[\s.@]+/)[0]

  const q = useQuery({
    queryKey: ['home', 'dashboard'],
    queryFn: () => homeService.dashboard(),
    staleTime: 60_000,
  })

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
      <div className="px-6 py-6 max-w-7xl mx-auto space-y-6 relative">
        <Greeting name={firstName} data={q.data} />

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
      </div>
    </main>
  )
}

// ── Greeting / Header ─────────────────────────────────────────

function Greeting({ name, data }: { name: string; data: HomeDashboardResponse | undefined }) {
  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Bom dia' : hour < 18 ? 'Boa tarde' : 'Boa noite'
  const todayLong = data ? fmtDateLong(data.today_iso) : ''
  const weekday = data ? fmtWeekday(data.today_iso) : ''

  return (
    <section className="bg-gradient-to-br from-primary-700 via-primary-800 to-primary-900 text-white rounded-2xl p-6 shadow-xl relative overflow-hidden">
      <div className="absolute -right-10 -top-10 w-48 h-48 bg-white/5 rounded-full" />
      <div className="absolute right-20 bottom-0 w-32 h-32 bg-white/5 rounded-full" />
      <div className="relative flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="text-primary-200 text-xs uppercase tracking-wide font-semibold flex items-center gap-1.5">
            <Sparkles size={12} /> {greeting}
          </div>
          <h1 className="text-2xl md:text-3xl font-bold mt-1">
            {name ? `${name}` : 'Bem-vindo'} <span className="opacity-80">·</span> <span className="capitalize text-primary-100">{weekday}</span>
          </h1>
          <p className="text-primary-100/80 text-sm mt-1">{todayLong}</p>
        </div>
        {data && (
          <div className="bg-white/10 backdrop-blur-sm rounded-lg px-4 py-2.5 border border-white/15">
            <div className="text-[10px] uppercase tracking-wide text-primary-200 font-bold">Perfil</div>
            <div className="text-base font-bold mt-0.5">{data.role_label}</div>
          </div>
        )}
      </div>
    </section>
  )
}

// ── Grid layout ───────────────────────────────────────────────

function CockpitGrid({ data }: { data: HomeDashboardResponse }) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {/* Agenda: full width, sempre topo da grade quando presente */}
      {data.agenda && <AgendaCard data={data.agenda} />}
      {data.recall && <RecallCard data={data.recall} />}
      {data.top_profs_semana && <TopProfsCard data={data.top_profs_semana} />}
      {data.orcamentos_parados && <OrcamentosParadosCard data={data.orcamentos_parados} />}
      {data.inadimplencia_critica && <InadimplenciaCriticaCard data={data.inadimplencia_critica} />}
    </div>
  )
}

// ── Card primitives ───────────────────────────────────────────

function CardBase({
  children, span = 1, className = '',
}: { children: React.ReactNode; span?: 1 | 2 | 3; className?: string }) {
  const colClass = span === 3 ? 'lg:col-span-3' : span === 2 ? 'lg:col-span-2' : 'lg:col-span-1'
  return (
    <div className={`bg-white border border-neutral-200 rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden flex flex-col ${colClass} ${className}`}>
      {children}
    </div>
  )
}

function CardHeader({
  icon, iconBg, title, subtitle, badge, badgeColor,
}: {
  icon: React.ReactNode
  iconBg: string
  title: string
  subtitle?: string
  badge?: string
  badgeColor?: string
}) {
  return (
    <div className="px-5 py-4 border-b border-neutral-100 flex items-center gap-3">
      <span className={`w-10 h-10 rounded-lg ${iconBg} flex items-center justify-center shrink-0 shadow-sm`}>
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="text-sm font-bold text-neutral-900 truncate">{title}</h3>
          {badge && (
            <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded font-bold ${badgeColor || 'bg-primary-50 text-primary-700'}`}>
              {badge}
            </span>
          )}
        </div>
        {subtitle && <div className="text-xs text-neutral-500 mt-0.5 truncate">{subtitle}</div>}
      </div>
    </div>
  )
}

function EmptyState({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-10 px-4 text-center">
      <div className="w-12 h-12 rounded-full bg-neutral-100 text-neutral-400 flex items-center justify-center mb-3">
        {icon}
      </div>
      <div className="text-sm text-neutral-500">{label}</div>
    </div>
  )
}

function Avatar({ name, color = 'bg-primary-50 text-primary-700' }: { name: string; color?: string }) {
  return (
    <span className={`w-9 h-9 rounded-full ${color} flex items-center justify-center text-xs font-bold shrink-0 ring-2 ring-white shadow-sm`}>
      {initials(name)}
    </span>
  )
}

// ── Agenda do dia (matriz hora × profissional) ────────────────

const PROF_COLORS = [
  { header: 'bg-blue-50 text-blue-700 ring-blue-200', avatar: 'bg-blue-100 text-blue-700', accent: 'border-blue-300' },
  { header: 'bg-emerald-50 text-emerald-700 ring-emerald-200', avatar: 'bg-emerald-100 text-emerald-700', accent: 'border-emerald-300' },
  { header: 'bg-amber-50 text-amber-700 ring-amber-200', avatar: 'bg-amber-100 text-amber-700', accent: 'border-amber-300' },
  { header: 'bg-purple-50 text-purple-700 ring-purple-200', avatar: 'bg-purple-100 text-purple-700', accent: 'border-purple-300' },
  { header: 'bg-rose-50 text-rose-700 ring-rose-200', avatar: 'bg-rose-100 text-rose-700', accent: 'border-rose-300' },
  { header: 'bg-cyan-50 text-cyan-700 ring-cyan-200', avatar: 'bg-cyan-100 text-cyan-700', accent: 'border-cyan-300' },
  { header: 'bg-indigo-50 text-indigo-700 ring-indigo-200', avatar: 'bg-indigo-100 text-indigo-700', accent: 'border-indigo-300' },
  { header: 'bg-orange-50 text-orange-700 ring-orange-200', avatar: 'bg-orange-100 text-orange-700', accent: 'border-orange-300' },
]

function buildSlots(items: AgendaItem[]): string[] {
  const horarios = items.filter((it) => it.horario).map((it) => it.horario!)
  if (horarios.length === 0) return []
  const minutes = horarios.map((h) => {
    const [hh, mm] = h.split(':').map(Number)
    return hh * 60 + mm
  })
  const mn = Math.floor(Math.min(...minutes) / 30) * 30
  const maxDuration = Math.max(...items.map((it) => it.duration_minutes ?? 30), 30)
  const mx = Math.ceil((Math.max(...minutes) + maxDuration) / 30) * 30
  const slots: string[] = []
  for (let m = mn; m < mx; m += 30) {
    slots.push(`${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`)
  }
  return slots
}

function slotMinutes(slot: string): number {
  const [h, m] = slot.split(':').map(Number)
  return h * 60 + m
}

function AgendaCard({ data }: { data: AgendaSection }) {
  // Coleta profissionais distintos com consulta no dia
  const profsMap = new Map<number, string>()
  for (const it of data.items) {
    if (it.profissional_external_id != null) {
      profsMap.set(
        it.profissional_external_id,
        it.profissional_nome || `Prof. #${it.profissional_external_id}`,
      )
    }
  }
  const profs = Array.from(profsMap.entries()).map(([id, nome], idx) => ({
    id, nome, color: PROF_COLORS[idx % PROF_COLORS.length],
  }))

  const slots = buildSlots(data.items)
  const subtitle = data.is_today
    ? `${fmtNum(data.total)} ${data.total === 1 ? 'consulta' : 'consultas'} · ${profs.length} ${profs.length === 1 ? 'profissional' : 'profissionais'}`
    : `Hoje sem consultas — exibindo ${fmtDateShort(data.date_iso)}`

  // "agora" pra opacidade de slots passados
  const now = new Date()
  const nowMin = data.is_today ? now.getHours() * 60 + now.getMinutes() : -1

  return (
    <CardBase span={3}>
      <CardHeader
        icon={<CalendarClock size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-info-DEFAULT to-blue-700"
        title="Agenda do dia"
        subtitle={subtitle}
        badge={data.is_today ? 'Hoje' : 'Próximo dia'}
        badgeColor={data.is_today ? 'bg-info-bg text-info-text' : 'bg-warning-bg text-warning-text'}
      />
      <div className="flex-1 overflow-hidden">
        {data.items.length === 0 || profs.length === 0 ? (
          <EmptyState icon={<CalendarClock size={20} />} label="Sem consultas agendadas." />
        ) : (
          <div className="overflow-auto max-h-[480px]">
            <table className="border-separate border-spacing-0 text-xs w-full">
              {/* Header: profissionais */}
              <thead className="sticky top-0 z-20 bg-white">
                <tr>
                  <th className="sticky left-0 z-30 bg-white border-b border-r border-neutral-200 w-[68px] py-2 text-[10px] uppercase tracking-wide text-neutral-400 font-bold">
                    Hora
                  </th>
                  {profs.map((p) => (
                    <th
                      key={p.id}
                      className={`border-b border-r border-neutral-100 px-2 py-2 min-w-[110px] ${p.color.header}`}
                      title={p.nome}
                    >
                      <div className="flex items-center gap-1.5 justify-center">
                        <span className={`w-7 h-7 rounded-full ${p.color.avatar} flex items-center justify-center text-[10px] font-bold ring-2 ring-white shadow-sm`}>
                          {initials(p.nome)}
                        </span>
                        <span className="text-[11px] font-semibold truncate max-w-[80px]">{p.nome.split(' ')[0]}</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {slots.map((slot, sIdx) => {
                  const slotMin = slotMinutes(slot)
                  const isPastSlot = nowMin >= 0 && nowMin >= slotMin + 30
                  const isCurrentSlot = nowMin >= 0 && nowMin >= slotMin && nowMin < slotMin + 30
                  return (
                    <tr key={slot} className={sIdx % 2 === 0 ? 'bg-neutral-50/30' : ''}>
                      <td
                        className={`sticky left-0 z-10 border-r border-neutral-100 px-2 py-1.5 text-center font-mono tabular-nums text-[11px] font-semibold ${
                          isCurrentSlot ? 'bg-info-bg text-info-text' : sIdx % 2 === 0 ? 'bg-neutral-50/80 text-neutral-500' : 'bg-white text-neutral-500'
                        }`}
                      >
                        {slot}
                      </td>
                      {profs.map((p) => {
                        const cellItems = data.items.filter((it) => {
                          if (it.profissional_external_id !== p.id || !it.horario) return false
                          const [h, m] = it.horario.split(':').map(Number)
                          const itMin = h * 60 + m
                          return itMin >= slotMin && itMin < slotMin + 30
                        })
                        return (
                          <td
                            key={p.id}
                            className="border-r border-b border-neutral-100 align-top p-0.5"
                          >
                            {cellItems.length === 0 ? (
                              <div className={`h-9 ${isPastSlot ? '' : ''}`} />
                            ) : (
                              <div className="flex flex-col gap-0.5">
                                {cellItems.map((it) => (
                                  <AgendaChip
                                    key={it.external_id}
                                    item={it}
                                    profColor={p.color}
                                    isPast={isPastSlot}
                                  />
                                ))}
                              </div>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </CardBase>
  )
}

function AgendaChip({
  item, profColor, isPast,
}: {
  item: AgendaItem
  profColor: typeof PROF_COLORS[number]
  isPast: boolean
}) {
  const tooltip = [
    `${item.horario || '—'}${item.duration_minutes ? ` · ${item.duration_minutes} min` : ''}`,
    item.paciente_nome,
    item.profissional_nome || '',
    item.categoria,
  ].filter(Boolean).join(' · ')

  const borderStyle = item.category_color
    ? { borderLeftColor: item.category_color, borderLeftWidth: '3px' }
    : undefined

  return (
    <div
      title={tooltip}
      className={`group relative rounded-md ${profColor.avatar} px-1.5 py-1 flex items-center gap-1.5 cursor-default hover:shadow-md hover:scale-[1.02] transition-all ${
        isPast ? 'opacity-50' : ''
      }`}
      style={borderStyle}
    >
      <span className="text-[11px] font-bold tabular-nums tracking-tight">
        {initials(item.paciente_nome)}
      </span>
      <span className="text-[10px] truncate flex-1 opacity-70">
        {item.paciente_nome.split(' ')[0]}
      </span>
    </div>
  )
}

// ── Top profissionais semana ──────────────────────────────────

function TopProfsCard({ data }: { data: TopProfsSemanaSection }) {
  const max = Math.max(...data.items.map((i) => i.valor_aprovado), 1)
  return (
    <CardBase>
      <CardHeader
        icon={<Trophy size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-amber-500 to-orange-600"
        title="Top profissionais"
        subtitle={`Semana atual · ${fmtDateShort(data.inicio_iso)} → ${fmtDateShort(data.fim_iso)}`}
      />
      <div className="flex-1">
        {data.items.length === 0 ? (
          <EmptyState icon={<Trophy size={20} />} label="Sem orçamentos aprovados ainda nesta semana." />
        ) : (
          <div className="divide-y divide-neutral-100">
            {data.items.map((p, i) => {
              const widthPct = (p.valor_aprovado / max) * 100
              return (
                <div key={p.external_id} className="px-5 py-3">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    {i === 0 ? (
                      <span className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
                        <Crown size={12} />
                      </span>
                    ) : (
                      <span className="w-6 h-6 rounded-full bg-neutral-100 text-neutral-500 flex items-center justify-center text-[11px] font-bold shrink-0">
                        {i + 1}
                      </span>
                    )}
                    <span className="text-sm font-medium text-neutral-900 truncate flex-1" title={p.nome}>
                      {p.nome}
                    </span>
                    <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtBRL(p.valor_aprovado, true)}
                    </span>
                  </div>
                  <div className="h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${i === 0 ? 'bg-amber-500' : 'bg-primary-500'}`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                  <div className="text-[10px] text-neutral-500 mt-1 text-right">
                    {p.qtd_aprovados} aprovados
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </CardBase>
  )
}

// ── Recall (oportunidades) ────────────────────────────────────

function RecallCard({ data }: { data: RecallSection }) {
  return (
    <CardBase span={2}>
      <CardHeader
        icon={<Phone size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-amber-500 to-amber-700"
        title="Pacientes pra ligar"
        subtitle={`${fmtNum(data.items.length)} de ${fmtNum(data.total_elegiveis)} candidatos · vinham regularmente e estão atrasados`}
        badge="Oportunidades"
        badgeColor="bg-amber-100 text-amber-800"
      />
      <div className="flex-1 overflow-hidden">
        {data.items.length === 0 ? (
          <EmptyState icon={<Sparkles size={20} />} label="Nenhum paciente elegível a recall agora." />
        ) : (
          <div className="divide-y divide-neutral-100 max-h-[420px] overflow-y-auto">
            {data.items.map((item) => (
              <RecallRow key={item.paciente_external_id} item={item} />
            ))}
          </div>
        )}
      </div>
    </CardBase>
  )
}

function RecallRow({ item }: { item: RecallItem }) {
  // urgência visual baseada em atraso relativo
  const urgent = item.atraso_relativo >= 3
  const moderate = item.atraso_relativo >= 2 && !urgent
  const urgencyColor = urgent
    ? 'bg-error-bg text-error-text'
    : moderate
    ? 'bg-warning-bg text-warning-text'
    : 'bg-info-bg text-info-text'

  return (
    <div className="px-5 py-3 flex items-center gap-3 hover:bg-neutral-50/60 transition-colors">
      <Avatar name={item.paciente_nome} color="bg-amber-50 text-amber-700" />
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline justify-between gap-2 mb-0.5">
          <span className="text-sm font-medium text-neutral-900 truncate" title={item.paciente_nome}>
            {item.paciente_nome}
          </span>
          <span className={`text-[10px] uppercase tracking-wide font-bold px-1.5 py-0.5 rounded shrink-0 ${urgencyColor}`}>
            {item.atraso_relativo.toFixed(1)}× atrasado
          </span>
        </div>
        <div className="flex items-center gap-2 text-[11px] text-neutral-500">
          <span className="flex items-center gap-1">
            <Clock size={10} /> {item.dias_desde_ultima}d sem visita
          </span>
          <span className="text-neutral-300">·</span>
          <span>vinha a cada {item.intervalo_medio_dias}d</span>
          <span className="text-neutral-300">·</span>
          <span>{item.qtd_consultas} consultas</span>
        </div>
      </div>
    </div>
  )
}

// ── Orçamentos parados ────────────────────────────────────────

function OrcamentosParadosCard({ data }: { data: OrcamentosParadosSection }) {
  return (
    <CardBase span={2}>
      <CardHeader
        icon={<FileText size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-purple-600 to-indigo-700"
        title="Orçamentos parados"
        subtitle={
          data.total > 0
            ? `${fmtNum(data.total)} aprovados sem retorno · total ${fmtBRL(data.valor_total)}`
            : 'Aprovados há 30-90 dias sem nova consulta'
        }
        badge={data.total > 0 ? 'Atenção' : undefined}
        badgeColor="bg-purple-100 text-purple-800"
      />
      <div className="flex-1 overflow-hidden">
        {data.items.length === 0 ? (
          <EmptyState icon={<Target size={20} />} label="Nenhum orçamento parado. Pipeline em dia." />
        ) : (
          <div className="divide-y divide-neutral-100 max-h-[360px] overflow-y-auto">
            {data.items.map((item) => (
              <div
                key={item.external_id}
                className="px-5 py-3 flex items-center gap-3 hover:bg-neutral-50/60"
              >
                <Avatar name={item.paciente_nome} color="bg-purple-50 text-purple-700" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline justify-between gap-2 mb-0.5">
                    <span className="text-sm font-medium text-neutral-900 truncate" title={item.paciente_nome}>
                      {item.paciente_nome}
                    </span>
                    <span className="text-sm font-bold tabular-nums text-neutral-900 shrink-0">
                      {fmtBRL(item.amount, true)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-neutral-500">
                    <span className="truncate">{item.profissional_nome || 'Sem profissional'}</span>
                    <span className="text-neutral-300">·</span>
                    <span className="text-warning-text font-medium">{item.dias_aprovado}d sem retorno</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </CardBase>
  )
}

// ── Inadimplência crítica ─────────────────────────────────────

function InadimplenciaCriticaCard({ data }: { data: InadimplenciaCriticaSection }) {
  return (
    <CardBase>
      <CardHeader
        icon={<AlertTriangle size={18} className="text-white" />}
        iconBg="bg-gradient-to-br from-error-DEFAULT to-red-800"
        title="Inadimplência crítica"
        subtitle={
          data.total > 0
            ? `${fmtNum(data.total)} parcelas · ${fmtBRL(data.valor_total)}`
            : 'Vencidas há +60d e valor +R$ 500'
        }
        badge={data.total > 5 ? 'Alta' : data.total > 0 ? 'Atenção' : undefined}
        badgeColor={data.total > 5 ? 'bg-error-bg text-error-text' : 'bg-warning-bg text-warning-text'}
      />
      <div className="flex-1">
        {data.items.length === 0 ? (
          <EmptyState icon={<TrendingUp size={20} />} label="Sem inadimplência crítica. 🎯" />
        ) : (
          <div className="divide-y divide-neutral-100 max-h-[360px] overflow-y-auto">
            {data.items.map((item) => (
              <div key={item.parcela_external_id} className="px-5 py-3">
                <div className="flex items-baseline justify-between gap-2 mb-0.5">
                  <span className="text-sm font-medium text-neutral-900 truncate" title={item.pessoa_nome}>
                    {item.pessoa_nome}
                  </span>
                  <span className="text-sm font-bold tabular-nums text-error-text shrink-0">
                    {fmtBRL(item.valor_em_aberto, true)}
                  </span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-neutral-500">
                  <span className="text-error-text font-semibold">{item.dias_atraso}d atraso</span>
                  <span className="text-neutral-300">·</span>
                  <span className="truncate">{item.categoria || 'Sem categoria'}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </CardBase>
  )
}
