/**
 * Painel Executivo — /marketing/visao-geral (Sub-PR 21e+).
 *
 * Estilo executivo inspirado no painel do Dr. Plutarco (PHP) — moderno,
 * com saudação contextual, KPIs grandes com delta WoW visual, post hero
 * com imagem, status multicanal compacto e análise narrativa SonIA.
 *
 * Dados: `/meta/dashboard` (snapshots + insights 7d/7d_prev + top_posts).
 * SonIA: page_key `/marketing/visao-geral` (DeepSeek).
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight,
  Camera, CheckCircle2, ExternalLink, FileEdit, Heart, Image as ImageIcon,
  MessageCircle, MessageSquare, Minus, Share2, Sparkles, TrendingUp,
  Users, XCircle,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { metaService } from '@/services/meta.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { useAuth } from '@/modules/auth/AuthContext'
import { useSonIA, type SonIAInsight } from '@/components/sonia/SonIAContext'
import type {
  MetaDashboard, MetaDashboardCard, MetaPendingItem, MetaTopPost,
} from '@/types/meta'

// ─────────────────────────────────────────────────────────────────
// Formatadores
// ─────────────────────────────────────────────────────────────────

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

// ─────────────────────────────────────────────────────────────────
// Heurística SonIA (fallback se DeepSeek estiver fora)
// ─────────────────────────────────────────────────────────────────

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
    detail: 'Resumo executivo dos últimos 7 dias contra a semana anterior — pra você ver tendência sem abrir cada canal.',
    bullets,
  }
}

// ─────────────────────────────────────────────────────────────────
// Página
// ─────────────────────────────────────────────────────────────────

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

  if (q.isLoading) {
    return (
      <PageContainer>
        <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
          Carregando…
        </div>
      </PageContainer>
    )
  }
  if (q.isError || !q.data) {
    return (
      <PageContainer>
        <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
          Erro ao carregar painel.
        </div>
      </PageContainer>
    )
  }

  const d = q.data
  const firstName = (user?.full_name || user?.email || '').split(' ')[0] || ''
  const now = new Date()

  return (
    <PageContainer gap={6}>
      {/* ─── Hero header executivo (gradient) ────────────────────── */}
      <header className="bg-gradient-to-br from-violet-600 via-fuchsia-600 to-pink-600 rounded-2xl p-6 md:p-8 text-white shadow-lg">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-[0.2em] opacity-80 mb-1">
              Painel Executivo · Redes Sociais
            </div>
            <h1 className="text-2xl md:text-3xl font-bold leading-tight">
              {saudacao(now, firstName)}.
            </h1>
            <p className="text-white/90 mt-1 text-sm md:text-base">
              Sua semana em uma olhada — <span className="opacity-90">{semanaLabel(now)}</span>
              {d.business_name && <> · {d.business_name}</>}
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="bg-white/15 backdrop-blur px-3 py-1 rounded-full inline-flex items-center gap-1">
              <Sparkles size={12} /> SonIA · análise viva
            </span>
          </div>
        </div>
      </header>

      {!d.has_connection && <ConnectionWarning />}

      {/* ─── 4 KPIs primários com WoW ─────────────────────────────── */}
      <KpiGrid ig={d.instagram} fb={d.facebook} />

      {/* ─── Top post hero + lista ────────────────────────────────── */}
      {d.instagram.top_posts.length > 0 && (
        <HeroPost top={d.instagram.top_posts[0]} igRest={d.instagram.top_posts.slice(1)} fb={d.facebook.top_posts} />
      )}

      {/* ─── Painéis IG + FB + Pixel (compactos, sem repetir KPIs) ─ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <ChannelCard
          icon={<ImageIcon size={18} className="text-pink-600" />}
          accent="bg-pink-50 text-pink-700 border-pink-200"
          channel="Instagram"
          card={d.instagram}
          followersLabel="Seguidores"
          postsLabel="Publicações"
        />
        <ChannelCard
          icon={<MessageSquare size={18} className="text-blue-700" />}
          accent="bg-blue-50 text-blue-700 border-blue-200"
          channel="Facebook"
          card={d.facebook}
          followersLabel="Fãs"
          postsLabel="Engajamento 7d"
        />
        <PixelMiniCard card={d.pixel} />
      </div>

      {/* ─── Pendências TI ────────────────────────────────────────── */}
      {d.pending.length > 0 && <PendingTI items={d.pending} />}

      {/* ─── Em construção ────────────────────────────────────────── */}
      <ComingSoon />
    </PageContainer>
  )
}

// ─────────────────────────────────────────────────────────────────
// Connection warning
// ─────────────────────────────────────────────────────────────────

function ConnectionWarning() {
  return (
    <div className="bg-warning-bg border border-warning-border rounded-xl p-4 flex items-start gap-3 text-sm">
      <AlertTriangle size={18} className="text-warning-text mt-0.5 shrink-0" />
      <div className="flex-1">
        <strong className="text-warning-text">Sem conexão Meta ativa.</strong>{' '}
        <span className="text-neutral-700">
          Configure o token e valide em <Link to="/empresa/meta-config" className="underline">/empresa/meta-config</Link>.
        </span>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Grid de 4 KPIs primários grandes com delta WoW
// ─────────────────────────────────────────────────────────────────

function KpiGrid({ ig, fb }: { ig: MetaDashboardCard; fb: MetaDashboardCard }) {
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        label="Alcance Instagram"
        sublabel="contas únicas · 7d"
        value={fmtNum(ig.reach_7d)}
        valueCompact={fmtCompact(ig.reach_7d)}
        prev={ig.reach_7d_prev}
        cur={ig.reach_7d}
        icon={<ImageIcon size={20} />}
        accent="from-pink-500 to-fuchsia-500"
      />
      <KpiCard
        label="Alcance Facebook"
        sublabel="pessoas únicas · 7d"
        value={fmtNum(fb.reach_7d)}
        valueCompact={fmtCompact(fb.reach_7d)}
        prev={fb.reach_7d_prev}
        cur={fb.reach_7d}
        icon={<MessageSquare size={20} />}
        accent="from-blue-500 to-blue-700"
      />
      <KpiCard
        label="+Seguidores Instagram"
        sublabel={`total ${fmtNum(ig.followers)} · 7d`}
        value={ig.followers_gained_7d != null ? `+${fmtNum(ig.followers_gained_7d)}` : '—'}
        valueCompact={ig.followers_gained_7d != null ? `+${fmtCompact(ig.followers_gained_7d)}` : '—'}
        prev={ig.followers_gained_7d_prev}
        cur={ig.followers_gained_7d}
        icon={<Users size={20} />}
        accent="from-violet-500 to-purple-600"
      />
      <KpiCard
        label="Engajamento Facebook"
        sublabel="interações em posts · 7d"
        value={fmtNum(fb.engagement_7d)}
        valueCompact={fmtCompact(fb.engagement_7d)}
        prev={fb.engagement_7d_prev}
        cur={fb.engagement_7d}
        icon={<Heart size={20} />}
        accent="from-rose-500 to-pink-600"
      />
    </section>
  )
}

function KpiCard({
  label, sublabel, value, valueCompact, cur, prev, icon, accent,
}: {
  label: string
  sublabel: string
  value: string
  valueCompact: string
  cur: number | null
  prev: number | null
  icon: React.ReactNode
  accent: string
}) {
  const pct = wowPct(cur, prev)
  const tone = pct == null ? 'neutral' : pct >= 5 ? 'up' : pct <= -5 ? 'down' : 'flat'
  const toneStyles = {
    up: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    down: 'text-rose-700 bg-rose-50 border-rose-200',
    flat: 'text-neutral-600 bg-neutral-50 border-neutral-200',
    neutral: 'text-neutral-400 bg-neutral-50 border-neutral-200',
  }[tone]
  const ToneIcon = tone === 'up' ? ArrowUpRight : tone === 'down' ? ArrowDownRight : Minus

  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm relative overflow-hidden">
      <div className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${accent}`} aria-hidden />
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-neutral-500 font-medium">{label}</div>
          <div className="text-[11px] text-neutral-400 mt-0.5">{sublabel}</div>
        </div>
        <div className={`w-9 h-9 rounded-lg bg-gradient-to-br ${accent} text-white flex items-center justify-center shrink-0 shadow-sm`}>
          {icon}
        </div>
      </div>
      <div
        className="text-3xl md:text-4xl font-bold tabular-nums text-neutral-900 truncate"
        title={value}
      >
        {/* Mostra forma compacta em larguras pequenas via title fallback */}
        <span className="lg:hidden">{valueCompact}</span>
        <span className="hidden lg:inline">{value}</span>
      </div>
      <div className="flex items-center gap-2 mt-3">
        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full border ${toneStyles}`}>
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

// ─────────────────────────────────────────────────────────────────
// Hero post + listas
// ─────────────────────────────────────────────────────────────────

function HeroPost({ top, igRest, fb }: { top: MetaTopPost; igRest: MetaTopPost[]; fb: MetaTopPost[] }) {
  const caption = (top.caption || 'Sem legenda').replace(/\s+/g, ' ').slice(0, 220)
  return (
    <section className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <div className="px-5 py-3 border-b flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-neutral-800">Conteúdo destaque</h2>
          <p className="text-[11px] text-neutral-500">Post com maior alcance no período</p>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-pink-600 font-medium">@ Instagram</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-0">
        {/* Imagem hero */}
        <div className="md:col-span-2 aspect-square md:aspect-auto bg-neutral-100 relative">
          {top.media_url ? (
            <img
              src={top.media_url}
              alt=""
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-neutral-400">
              <ImageIcon size={40} />
            </div>
          )}
          {top.permalink && (
            <a
              href={top.permalink}
              target="_blank"
              rel="noreferrer"
              className="absolute bottom-3 right-3 bg-white/95 hover:bg-white text-neutral-700 text-[11px] px-2.5 py-1.5 rounded-full shadow inline-flex items-center gap-1 backdrop-blur"
            >
              Ver post <ExternalLink size={11} />
            </a>
          )}
        </div>
        {/* Texto + métricas + sidebar com outros tops */}
        <div className="md:col-span-3 p-5 flex flex-col">
          <p className="text-sm text-neutral-700 line-clamp-5 mb-4">{caption}</p>
          <div className="grid grid-cols-4 gap-3 mb-4">
            <BigStat label="Alcance" value={fmtCompact(top.reach)} icon={<Activity size={14} />} />
            <BigStat label="Curtidas" value={fmtCompact(top.likes)} icon={<Heart size={14} />} />
            <BigStat label="Comentários" value={fmtCompact(top.comments)} icon={<MessageCircle size={14} />} />
            <BigStat label="Compart." value={fmtCompact(top.shares)} icon={<Share2 size={14} />} />
          </div>

          {/* Mini ranking */}
          <div className="mt-auto grid grid-cols-1 md:grid-cols-2 gap-3 pt-3 border-t">
            <MiniRanking title="Outros tops Instagram" channel="ig" posts={igRest} />
            <MiniRanking title="Top Facebook" channel="fb" posts={fb} />
          </div>
        </div>
      </div>
    </section>
  )
}

function BigStat({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="bg-neutral-50 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-neutral-500 inline-flex items-center gap-1">
        {icon} {label}
      </div>
      <div className="text-lg font-bold text-neutral-900 tabular-nums mt-0.5">{value}</div>
    </div>
  )
}

function MiniRanking({ title, channel, posts }: { title: string; channel: 'ig' | 'fb'; posts: MetaTopPost[] }) {
  if (posts.length === 0) return null
  const dot = channel === 'ig' ? 'bg-pink-500' : 'bg-blue-600'
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-neutral-500 font-medium mb-1.5">{title}</div>
      <ul className="space-y-1.5">
        {posts.slice(0, 2).map((p) => (
          <li key={p.post_external_id} className="flex items-center gap-2 text-xs">
            <span className={`w-1.5 h-1.5 rounded-full ${dot} shrink-0`} aria-hidden />
            <span className="text-neutral-600 truncate flex-1">
              {(p.caption || 'Sem legenda').replace(/\s+/g, ' ').slice(0, 38)}
            </span>
            <span className="text-neutral-500 tabular-nums shrink-0">{fmtCompact(p.reach)}</span>
            {p.permalink && (
              <a href={p.permalink} target="_blank" rel="noreferrer" className="text-neutral-400 hover:text-neutral-700">
                <ExternalLink size={11} />
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Canal compacto (IG/FB)
// ─────────────────────────────────────────────────────────────────

function ChannelCard({
  icon, accent, channel, card, followersLabel, postsLabel,
}: {
  icon: React.ReactNode
  accent: string
  channel: string
  card: MetaDashboardCard
  followersLabel: string
  postsLabel: string
}) {
  if (!card.available) {
    return (
      <div className="bg-neutral-50 border border-dashed rounded-xl p-5 flex flex-col items-center text-center text-neutral-400">
        {icon}
        <div className="text-sm font-medium text-neutral-600 mt-2">{channel}</div>
        <div className="text-xs mt-1">Sem snapshot — rode os syncs</div>
      </div>
    )
  }
  const followers = card.fan_count ?? card.followers
  const postsValue = channel === 'Facebook' ? card.engagement_7d : card.posts_7d
  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className={`inline-flex items-center gap-2 text-[11px] uppercase tracking-wider font-medium px-2 py-1 rounded-full border ${accent}`}>
          {icon} {channel}
        </span>
        {card.verification_status === 'verified' && (
          <CheckCircle2 size={14} className="text-emerald-600" />
        )}
      </div>
      <div className="flex items-start gap-3 mb-3">
        {card.profile_picture_url ? (
          <img
            src={card.profile_picture_url}
            alt=""
            className="w-12 h-12 rounded-full object-cover border shrink-0"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-12 h-12 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-400 shrink-0">
            {icon}
          </div>
        )}
        <div className="min-w-0">
          <div className="text-sm font-semibold text-neutral-900 truncate">
            {card.display_name || card.username || '—'}
          </div>
          {card.username && <div className="text-xs text-neutral-500 truncate">@{card.username}</div>}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 pt-3 border-t">
        <CompactStat label={followersLabel} value={fmtNum(followers)} />
        <CompactStat label={postsLabel} value={fmtNum(postsValue)} />
      </div>
      {card.biografia && (
        <p className="text-[11px] text-neutral-500 line-clamp-2 mt-3">{card.biografia}</p>
      )}
    </div>
  )
}

function CompactStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-neutral-500">{label}</div>
      <div className="text-base font-semibold text-neutral-900 tabular-nums">{value}</div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Pixel card mini
// ─────────────────────────────────────────────────────────────────

function PixelMiniCard({ card }: { card: MetaDashboardCard }) {
  if (!card.available) {
    return (
      <div className="bg-neutral-50 border border-dashed rounded-xl p-5 flex flex-col items-center text-center text-neutral-400">
        <Camera size={20} />
        <div className="text-sm font-medium text-neutral-600 mt-2">Pixel</div>
        <div className="text-xs mt-1">Sem snapshot</div>
      </div>
    )
  }
  const idle = card.pixel_days_idle ?? 0
  const isDead = idle > 365
  const isStale = idle > 30 && !isDead
  const tone = isDead ? 'rose' : isStale ? 'amber' : 'emerald'
  const toneStyles = {
    rose: { border: 'border-rose-200', bg: 'bg-rose-50', text: 'text-rose-700', label: 'Parado' },
    amber: { border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700', label: 'Atenção' },
    emerald: { border: 'border-emerald-200', bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'Ativo' },
  }[tone]

  return (
    <div className={`bg-white border rounded-xl p-5 shadow-sm ${toneStyles.border}`}>
      <div className="flex items-center justify-between mb-3">
        <span className={`inline-flex items-center gap-2 text-[11px] uppercase tracking-wider font-medium px-2 py-1 rounded-full ${toneStyles.bg} ${toneStyles.text}`}>
          <Camera size={14} /> Pixel · {toneStyles.label}
        </span>
      </div>
      <div className="text-sm font-semibold text-neutral-900 truncate mb-1">{card.pixel_name || '—'}</div>
      <div className="text-[11px] text-neutral-500">
        Último disparo: <span className="text-neutral-700">
          {card.pixel_last_fired_at ? new Date(card.pixel_last_fired_at).toLocaleDateString('pt-BR') : '—'}
        </span>
      </div>
      <div className="mt-3 pt-3 border-t flex items-baseline gap-2">
        <span className={`text-3xl font-bold tabular-nums ${isDead ? 'text-rose-700' : isStale ? 'text-amber-700' : 'text-emerald-700'}`}>
          {fmtNum(card.pixel_days_idle)}
        </span>
        <span className="text-xs text-neutral-500">dias sem disparar</span>
      </div>
      {isDead && (
        <div className="text-[11px] text-rose-700 mt-3 inline-flex items-start gap-1">
          <XCircle size={12} className="mt-0.5 shrink-0" />
          <span>Pedir reinstalação à TI</span>
        </div>
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Pendências TI (compacto)
// ─────────────────────────────────────────────────────────────────

function PendingTI({ items }: { items: MetaPendingItem[] }) {
  return (
    <section className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <div className="px-5 py-3 border-b bg-amber-50 flex items-center gap-2">
        <FileEdit size={15} className="text-amber-700" />
        <h2 className="text-sm font-semibold text-amber-800">
          Pendências da TI da clínica ({items.length})
        </h2>
        <span className="text-[10px] text-amber-700 ml-auto">conforme TI destrava, blocos novos aparecem aqui</span>
      </div>
      <ul className="divide-y">
        {items.map((p) => (
          <li key={p.key} className="px-5 py-3 flex items-start gap-3">
            <div className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-semibold">
              !
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-neutral-800">{p.label}</div>
              <div className="text-xs text-neutral-600 mt-0.5">{p.detail}</div>
              {p.blocked_features.length > 0 && (
                <div className="text-[11px] mt-1.5 flex flex-wrap gap-1">
                  {p.blocked_features.map((f) => (
                    <span key={f} className="bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded text-[10px]">{f}</span>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────
// Coming soon
// ─────────────────────────────────────────────────────────────────

function ComingSoon() {
  return (
    <section className="bg-white border rounded-xl p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-neutral-700 mb-3 inline-flex items-center gap-2">
        <ArrowRight size={14} /> Próximas seções
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <ComingItem
          icon={<MessageCircle size={16} />}
          title="Comentários & IA"
          desc="Leads quentes, depoimentos, dúvidas clínicas — classificação automática."
          status="Permissão liberada · 21f"
          statusTone="ok"
        />
        <ComingItem
          icon={<TrendingUp size={16} />}
          title="Funil Ads → Consulta"
          desc="Anúncios → leads → WhatsApp → agenda → realizada."
          status="Aguarda Ad Account autorizada"
          statusTone="warn"
        />
        <ComingItem
          icon={<Camera size={16} />}
          title="Pixel Funil de Conversão"
          desc="ViewContent · Lead · Schedule · Purchase."
          status="Aguarda reinstalação do Pixel"
          statusTone="warn"
        />
      </div>
    </section>
  )
}

function ComingItem({
  icon, title, desc, status, statusTone,
}: {
  icon: React.ReactNode
  title: string
  desc: string
  status: string
  statusTone: 'ok' | 'warn'
}) {
  const toneStyle = statusTone === 'ok'
    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
    : 'bg-amber-50 text-amber-700 border-amber-200'
  return (
    <div className="border border-dashed rounded-lg p-3 bg-neutral-50/40">
      <div className="flex items-center gap-2 text-neutral-700 mb-1">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-wider">{title}</span>
      </div>
      <p className="text-xs text-neutral-600 mb-2">{desc}</p>
      <span className={`inline-block text-[10px] font-medium px-2 py-0.5 rounded-full border ${toneStyle}`}>
        {status}
      </span>
    </div>
  )
}
