/**
 * Painel Executivo — /marketing/visao-geral.
 *
 * 4 blocos: KPIs WoW · Post destaque · Status dos canais · Pendências TI.
 * SonIA via FAB (page_key /marketing/visao-geral, DeepSeek).
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Camera,
  CheckCircle2, ExternalLink, Heart, Image as ImageIcon, MessageCircle,
  MessageSquare, Minus, Share2, TrendingUp, Users, XCircle,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { metaService } from '@/services/meta.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import { useAuth } from '@/modules/auth/AuthContext'
import { useSonIA, type SonIAInsight } from '@/components/sonia/SonIAContext'
import type {
  MetaDashboard, MetaDashboardCard, MetaPendingItem, MetaTopPost,
} from '@/types/meta'
import { CommentsInsightsSection } from './CommentsInsightsSection'
import { StoriesSection } from './StoriesSection'

// ─── Formatadores ─────────────────────────────────────────────

const fmtNum = (n: number | null | undefined): string =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)

const fmtCompact = (n: number | null | undefined): string => {
  if (n == null) return '—'
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

const wowPct = (cur: number | null, prev: number | null): number | null => {
  if (cur == null || prev == null || prev === 0) return null
  return Number((((cur - prev) / prev) * 100).toFixed(1))
}

const saudacao = (now: Date, firstName?: string | null): string => {
  const h = now.getHours()
  const base = h < 6 ? 'Boa madrugada' : h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite'
  return firstName ? `${base}, ${firstName}` : base
}

const semanaLabel = (now: Date): string => {
  const fim = now.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
  const inicio = new Date(now.getTime() - 6 * 86400_000).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
  return `${inicio} – ${fim}`
}

// ─── Heurística SonIA (fallback do DeepSeek) ───────────────────

function buildMarketingInsight(d: MetaDashboard): SonIAInsight {
  const ig = d.instagram, fb = d.facebook
  const wow_ig = wowPct(ig.reach_7d, ig.reach_7d_prev)
  const wow_fb = wowPct(fb.reach_7d, fb.reach_7d_prev)
  const bullets: NonNullable<SonIAInsight['bullets']> = []

  if (ig.reach_7d != null) {
    const tone = wow_ig != null && wow_ig > 10 ? 'positive' : wow_ig != null && wow_ig < -10 ? 'warning' : 'neutral'
    const delta = wow_ig != null ? ` (${wow_ig >= 0 ? '+' : ''}${wow_ig}% WoW)` : ''
    bullets.push({ text: `Instagram alcançou ${fmtNum(ig.reach_7d)} contas nos últimos 7 dias${delta}.`, tone })
  }
  if (fb.reach_7d != null) {
    const tone = wow_fb != null && wow_fb > 10 ? 'positive' : wow_fb != null && wow_fb < -10 ? 'warning' : 'neutral'
    const delta = wow_fb != null ? ` (${wow_fb >= 0 ? '+' : ''}${wow_fb}% WoW)` : ''
    bullets.push({ text: `Facebook alcançou ${fmtNum(fb.reach_7d)} pessoas${delta}.`, tone })
  }
  if (ig.followers_gained_7d != null) {
    bullets.push({
      text: `${ig.followers_gained_7d >= 0 ? '+' : ''}${fmtNum(ig.followers_gained_7d)} novos seguidores no Instagram (total ${fmtNum(ig.followers)}).`,
      tone: ig.followers_gained_7d > 0 ? 'positive' : 'neutral',
    })
  }
  const top = ig.top_posts[0]
  if (top) {
    bullets.push({
      text: `Top post da semana: ${fmtNum(top.reach)} contas alcançadas — "${(top.caption || '').slice(0, 60)}…"`,
      tone: 'positive',
    })
  }
  return {
    mood: 'happy',
    headline: 'Olhei sua semana nas redes.',
    detail: 'Resumo executivo dos últimos 7 dias contra a semana anterior.',
    bullets,
  }
}

// ─── Página ───────────────────────────────────────────────────

export default function VisaoGeralPage() {
  usePageTitle('Painel Executivo', 'Redes Sociais · semana atual vs anterior', 'MARKETING')
  const q = useQuery({ queryKey: ['meta', 'dashboard'], queryFn: metaService.dashboard })
  const { user } = useAuth()
  const { publish, clear } = useSonIA()

  useEffect(() => {
    if (!q.data) return
    publish({
      pageKey: '/marketing/visao-geral',
      pageTitle: 'Painel Executivo · Redes Sociais',
      data: { insight: buildMarketingInsight(q.data) },
    })
    return () => clear('/marketing/visao-geral')
  }, [q.data, publish, clear])

  const firstName = (user?.full_name || user?.email || '').split(' ')[0] || ''
  const now = new Date()

  return (
    <PageContainer gap={6}>
      <PageHeader
        eyebrow="MARKETING"
        title="Painel Executivo"
        subtitle={`${saudacao(now, firstName)} · sua semana nas redes (${semanaLabel(now)})`}
        icon={<TrendingUp size={20} />}
      />

      {q.isLoading && (
        <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
          Carregando…
        </div>
      )}
      {q.isError && (
        <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
          Erro ao carregar painel.
        </div>
      )}

      {q.data && (
        <>
          {!q.data.has_connection && <ConnectionWarning />}
          <KpiGrid ig={q.data.instagram} fb={q.data.facebook} />
          {q.data.instagram.top_posts.length > 0 && (
            <HeroPost top={q.data.instagram.top_posts[0]} />
          )}
          <StoriesSection />
          <CommentsInsightsSection />
          <ChannelsCard ig={q.data.instagram} fb={q.data.facebook} pixel={q.data.pixel} />
          {q.data.pending.length > 0 && <PendingTI items={q.data.pending} />}
        </>
      )}
    </PageContainer>
  )
}

// ─── Connection warning ───────────────────────────────────────

function ConnectionWarning() {
  return (
    <div className="bg-warning-bg border border-warning-border rounded-xl p-4 flex items-start gap-3 text-sm">
      <AlertTriangle size={18} className="text-warning-text mt-0.5 shrink-0" />
      <div className="flex-1">
        <strong className="text-warning-text">Sem conexão Meta ativa.</strong>{' '}
        <span className="text-neutral-700">
          Configure o token em <Link to="/empresa/meta-config" className="underline">/empresa/meta-config</Link>.
        </span>
      </div>
    </div>
  )
}

// ─── Bloco 1: 4 KPIs primários com WoW ────────────────────────

function KpiGrid({ ig, fb }: { ig: MetaDashboardCard; fb: MetaDashboardCard }) {
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        label="Alcance Instagram"
        sublabel="contas únicas · 7d"
        value={fmtNum(ig.reach_7d)}
        cur={ig.reach_7d}
        prev={ig.reach_7d_prev}
        icon={<ImageIcon size={18} className="text-pink-600" />}
        iconBg="bg-pink-50"
      />
      <KpiCard
        label="Alcance Facebook"
        sublabel="pessoas únicas · 7d"
        value={fmtNum(fb.reach_7d)}
        cur={fb.reach_7d}
        prev={fb.reach_7d_prev}
        icon={<MessageSquare size={18} className="text-blue-600" />}
        iconBg="bg-blue-50"
      />
      <KpiCard
        label="+Seguidores Instagram"
        sublabel={`total ${fmtNum(ig.followers)} · 7d`}
        value={ig.followers_gained_7d != null ? `+${fmtNum(ig.followers_gained_7d)}` : '—'}
        cur={ig.followers_gained_7d}
        prev={ig.followers_gained_7d_prev}
        icon={<Users size={18} className="text-violet-600" />}
        iconBg="bg-violet-50"
      />
      <KpiCard
        label="Engajamento Facebook"
        sublabel="interações em posts · 7d"
        value={fmtNum(fb.engagement_7d)}
        cur={fb.engagement_7d}
        prev={fb.engagement_7d_prev}
        icon={<Heart size={18} className="text-rose-600" />}
        iconBg="bg-rose-50"
      />
    </section>
  )
}

function KpiCard({
  label, sublabel, value, cur, prev, icon, iconBg,
}: {
  label: string
  sublabel: string
  value: string
  cur: number | null
  prev: number | null
  icon: React.ReactNode
  iconBg: string
}) {
  const pct = wowPct(cur, prev)
  const tone = pct == null ? 'neutral' : pct >= 5 ? 'up' : pct <= -5 ? 'down' : 'flat'
  const toneStyles = {
    up: 'text-emerald-700 bg-emerald-50',
    down: 'text-rose-700 bg-rose-50',
    flat: 'text-neutral-600 bg-neutral-100',
    neutral: 'text-neutral-400 bg-neutral-50',
  }[tone]
  const ToneIcon = tone === 'up' ? ArrowUpRight : tone === 'down' ? ArrowDownRight : Minus

  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-neutral-500 font-medium">{label}</div>
          <div className="text-[11px] text-neutral-400 mt-0.5">{sublabel}</div>
        </div>
        <div className={`w-9 h-9 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
          {icon}
        </div>
      </div>
      <div className="text-3xl font-bold tabular-nums text-neutral-900 truncate" title={value}>
        {value}
      </div>
      <div className="flex items-center gap-2 mt-2">
        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full ${toneStyles}`}>
          <ToneIcon size={11} />
          {pct == null ? 'sem comparativo' : `${pct >= 0 ? '+' : ''}${pct}% WoW`}
        </span>
        {prev != null && (
          <span className="text-[11px] text-neutral-400 tabular-nums">
            vs {fmtCompact(prev)} 7d antes
          </span>
        )}
      </div>
    </div>
  )
}

// ─── Bloco 2: Post destaque (compacto, horizontal) ────────────

function HeroPost({ top }: { top: MetaTopPost }) {
  const caption = (top.caption || 'Sem legenda').replace(/\s+/g, ' ')
  return (
    <section className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <header className="px-5 py-3 border-b flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-neutral-800">Conteúdo destaque</h2>
          <p className="text-[11px] text-neutral-500">Post com maior alcance no período</p>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-pink-600 font-medium">Instagram</span>
      </header>
      <div className="p-4 flex gap-4">
        <div className="w-32 h-32 sm:w-40 sm:h-40 rounded-lg bg-neutral-100 overflow-hidden relative shrink-0">
          {top.media_url ? (
            <img
              src={top.media_url}
              alt=""
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-neutral-400">
              <ImageIcon size={32} />
            </div>
          )}
        </div>
        <div className="min-w-0 flex-1 flex flex-col">
          <p className="text-sm text-neutral-700 line-clamp-3 mb-3">{caption}</p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-auto">
            <BigStat label="Alcance" value={fmtCompact(top.reach)} icon={<Activity size={13} />} />
            <BigStat label="Curtidas" value={fmtCompact(top.likes)} icon={<Heart size={13} />} />
            <BigStat label="Comentários" value={fmtCompact(top.comments)} icon={<MessageCircle size={13} />} />
            <BigStat label="Compart." value={fmtCompact(top.shares)} icon={<Share2 size={13} />} />
          </div>
          {top.permalink && (
            <a
              href={top.permalink}
              target="_blank"
              rel="noreferrer"
              className="text-[11px] text-neutral-500 hover:text-neutral-900 inline-flex items-center gap-1 mt-3 self-start"
            >
              Abrir no Instagram <ExternalLink size={11} />
            </a>
          )}
        </div>
      </div>
    </section>
  )
}

function BigStat({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="bg-neutral-50 rounded-lg p-2.5">
      <div className="text-[10px] uppercase tracking-wider text-neutral-500 inline-flex items-center gap-1">
        {icon} {label}
      </div>
      <div className="text-base font-bold text-neutral-900 tabular-nums mt-0.5">{value}</div>
    </div>
  )
}

// ─── Bloco 3: Status dos canais (3 linhas compactas) ──────────

function ChannelsCard({
  ig, fb, pixel,
}: { ig: MetaDashboardCard; fb: MetaDashboardCard; pixel: MetaDashboardCard }) {
  return (
    <section className="bg-white border rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-3 border-b">
        <h2 className="text-sm font-semibold text-neutral-800">Status dos canais</h2>
        <p className="text-[11px] text-neutral-500">Snapshot mais recente</p>
      </header>
      <ul className="divide-y">
        <ChannelRow
          icon={<ImageIcon size={16} />}
          iconBg="bg-pink-50 text-pink-600"
          name="Instagram"
          handle={ig.username ? `@${ig.username}` : null}
          avatarUrl={ig.profile_picture_url}
          mainStat={{ label: 'Seguidores', value: fmtNum(ig.followers) }}
          secondaryStat={ig.total_posts != null ? { label: 'Publicações', value: fmtNum(ig.total_posts) } : null}
          status="ok"
        />
        <ChannelRow
          icon={<MessageSquare size={16} />}
          iconBg="bg-blue-50 text-blue-700"
          name="Facebook"
          handle={fb.username ? `@${fb.username}` : null}
          avatarUrl={fb.profile_picture_url}
          mainStat={{ label: 'Fãs', value: fmtNum(fb.fan_count ?? fb.followers) }}
          secondaryStat={fb.category ? { label: 'Categoria', value: fb.category } : null}
          status="ok"
          verified={fb.verification_status === 'verified'}
        />
        <ChannelRow
          icon={<Camera size={16} />}
          iconBg="bg-amber-50 text-amber-700"
          name={pixel.pixel_name || 'Pixel'}
          handle={pixel.pixel_last_fired_at ? `último disparo ${new Date(pixel.pixel_last_fired_at).toLocaleDateString('pt-BR')}` : null}
          avatarUrl={null}
          mainStat={{
            label: 'Dias sem disparar',
            value: pixel.pixel_days_idle != null ? fmtNum(pixel.pixel_days_idle) : '—',
          }}
          secondaryStat={null}
          status={(pixel.pixel_days_idle ?? 0) > 365 ? 'bad' : (pixel.pixel_days_idle ?? 0) > 30 ? 'warn' : 'ok'}
        />
      </ul>
    </section>
  )
}

function ChannelRow({
  icon, iconBg, name, handle, avatarUrl, mainStat, secondaryStat, status, verified,
}: {
  icon: React.ReactNode
  iconBg: string
  name: string
  handle: string | null
  avatarUrl: string | null
  mainStat: { label: string; value: string }
  secondaryStat: { label: string; value: string } | null
  status: 'ok' | 'warn' | 'bad'
  verified?: boolean
}) {
  const badge = {
    ok: 'bg-emerald-50 text-emerald-700',
    warn: 'bg-amber-50 text-amber-700',
    bad: 'bg-rose-50 text-rose-700',
  }[status]
  const badgeLabel = { ok: 'Ativo', warn: 'Atenção', bad: 'Parado' }[status]
  return (
    <li className="px-5 py-3 flex items-center gap-4">
      {avatarUrl ? (
        <img
          src={avatarUrl}
          alt=""
          className="w-10 h-10 rounded-full object-cover border shrink-0"
          referrerPolicy="no-referrer"
        />
      ) : (
        <div className={`w-10 h-10 rounded-full ${iconBg} flex items-center justify-center shrink-0`}>
          {icon}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5 text-sm font-semibold text-neutral-900 truncate">
          {name}
          {verified && <CheckCircle2 size={12} className="text-emerald-600" />}
        </div>
        {handle && <div className="text-[11px] text-neutral-500 truncate">{handle}</div>}
      </div>
      <div className="hidden sm:flex items-baseline gap-4 text-right shrink-0">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-neutral-500">{mainStat.label}</div>
          <div className="text-base font-semibold text-neutral-900 tabular-nums">{mainStat.value}</div>
        </div>
        {secondaryStat && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-neutral-500">{secondaryStat.label}</div>
            <div className="text-sm font-medium text-neutral-700 truncate max-w-[140px]">{secondaryStat.value}</div>
          </div>
        )}
      </div>
      <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full shrink-0 ${badge}`}>
        {badgeLabel}
      </span>
    </li>
  )
}

// ─── Bloco 4: Pendências TI (compacto) ────────────────────────

function PendingTI({ items }: { items: MetaPendingItem[] }) {
  return (
    <section className="bg-white border rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-3 border-b bg-amber-50/60 flex items-center gap-2">
        <AlertTriangle size={14} className="text-amber-700" />
        <h2 className="text-sm font-semibold text-amber-800">
          Pendências da TI da clínica ({items.length})
        </h2>
      </header>
      <ul className="divide-y">
        {items.map((p) => (
          <li key={p.key} className="px-5 py-3 flex items-start gap-3">
            <XCircle size={14} className="text-rose-500 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-neutral-800">{p.label}</div>
              <div className="text-xs text-neutral-600 mt-0.5 line-clamp-2">{p.detail}</div>
            </div>
            {p.blocked_features.length > 0 && (
              <div className="hidden sm:flex flex-wrap gap-1 max-w-[40%] justify-end">
                {p.blocked_features.slice(0, 3).map((f) => (
                  <span key={f} className="bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded text-[10px] truncate">{f}</span>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
