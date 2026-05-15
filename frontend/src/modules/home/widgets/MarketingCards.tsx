/**
 * Widgets Marketing (Meta) pro MY-Analisys.
 *
 * Consomem `GET /meta/dashboard` via `useMetaDashboard()` (TanStack dedupe).
 *  - MarketingResumoCard: KPIs 7d (reach IG/FB, ganho seguidores, engagement)
 *  - MarketingTopPostsCard: top 3 posts IG por reach + top 3 FB
 *  - MarketingStatusPixelCard: idle do pixel + checklist TI pendente
 */
import { Activity, AlertCircle, Camera, ExternalLink, Heart, Megaphone, MessageCircle, Share2, TrendingUp, Users } from 'lucide-react'
import type { MetaTopPost } from '@/types/meta'

import { useMetaDashboard, WidgetError, WidgetLoading, fmtNum } from './_shared'

function StatBlock({
  label,
  value,
  hint,
  icon,
  iconBg,
  iconColor,
}: {
  label: string
  value: string
  hint?: string
  icon: React.ReactNode
  iconBg: string
  iconColor: string
}) {
  return (
    <div className="flex items-center gap-3">
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconBg} ${iconColor} shrink-0`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-xs text-neutral-500 truncate">{label}</div>
        <div className="text-base font-semibold text-neutral-900 truncate">{value}</div>
        {hint && <div className="text-[11px] text-neutral-400 truncate">{hint}</div>}
      </div>
    </div>
  )
}

export function MarketingResumoCard() {
  const q = useMetaDashboard()
  if (q.isLoading) return <WidgetLoading label="Marketing — últimos 7 dias" />
  if (q.isError || !q.data) return <WidgetError label="Marketing — últimos 7 dias" />

  const { instagram: ig, facebook: fb } = q.data
  const reachTotal = (ig.reach_7d ?? 0) + (fb.reach_7d ?? 0)

  return (
    <section className="bg-white border border-neutral-200 rounded-xl p-4 h-full flex flex-col">
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">Marketing — últimos 7 dias</h3>
          <p className="text-[11px] text-neutral-500">Resumo orgânico Instagram + Facebook</p>
        </div>
        <div className="w-9 h-9 rounded-lg bg-pink-50 text-pink-600 flex items-center justify-center">
          <TrendingUp size={18} />
        </div>
      </header>
      <div className="grid grid-cols-2 gap-3 flex-1 content-start">
        <StatBlock
          label="Alcance total 7d"
          value={fmtNum(reachTotal)}
          hint={`IG ${fmtNum(ig.reach_7d ?? 0)} · FB ${fmtNum(fb.reach_7d ?? 0)}`}
          icon={<Activity size={18} />}
          iconBg="bg-blue-50"
          iconColor="text-blue-600"
        />
        <StatBlock
          label="Seguidores IG"
          value={fmtNum(ig.followers ?? 0)}
          hint={ig.followers_gained_7d != null ? `+${fmtNum(ig.followers_gained_7d)} em 7d` : undefined}
          icon={<Camera size={18} />}
          iconBg="bg-pink-50"
          iconColor="text-pink-600"
        />
        <StatBlock
          label="Fãs Facebook"
          value={fmtNum(fb.fan_count ?? fb.followers ?? 0)}
          hint={fb.engagement_7d != null ? `${fmtNum(fb.engagement_7d)} interações 7d` : undefined}
          icon={<Megaphone size={18} />}
          iconBg="bg-blue-50"
          iconColor="text-blue-700"
        />
        <StatBlock
          label="Posts IG (total)"
          value={fmtNum(ig.total_posts ?? 0)}
          hint={ig.username ? `@${ig.username}` : undefined}
          icon={<Users size={18} />}
          iconBg="bg-violet-50"
          iconColor="text-violet-600"
        />
      </div>
    </section>
  )
}

function PostRow({ post, channel }: { post: MetaTopPost; channel: 'ig' | 'fb' }) {
  const caption = (post.caption || 'Sem legenda').replace(/\s+/g, ' ').slice(0, 90)
  const dotColor = channel === 'ig' ? 'bg-pink-500' : 'bg-blue-600'
  return (
    <li className="flex items-start gap-3 py-2 border-b border-neutral-100 last:border-0">
      <span className={`w-2 h-2 rounded-full mt-2 ${dotColor} shrink-0`} aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-xs text-neutral-700 line-clamp-2">{caption}</p>
        <div className="flex items-center gap-3 mt-1 text-[11px] text-neutral-500">
          <span className="inline-flex items-center gap-1">
            <Activity size={11} /> {fmtNum(post.reach ?? 0)}
          </span>
          {post.likes != null && (
            <span className="inline-flex items-center gap-1">
              <Heart size={11} /> {fmtNum(post.likes)}
            </span>
          )}
          {post.comments != null && post.comments > 0 && (
            <span className="inline-flex items-center gap-1">
              <MessageCircle size={11} /> {fmtNum(post.comments)}
            </span>
          )}
          {post.shares != null && post.shares > 0 && (
            <span className="inline-flex items-center gap-1">
              <Share2 size={11} /> {fmtNum(post.shares)}
            </span>
          )}
        </div>
      </div>
      {post.permalink && (
        <a
          href={post.permalink}
          target="_blank"
          rel="noreferrer"
          className="text-neutral-400 hover:text-neutral-700 mt-1"
          aria-label="Abrir post"
        >
          <ExternalLink size={14} />
        </a>
      )}
    </li>
  )
}

export function MarketingTopPostsCard() {
  const q = useMetaDashboard()
  if (q.isLoading) return <WidgetLoading label="Top posts (Instagram + Facebook)" />
  if (q.isError || !q.data) return <WidgetError label="Top posts (Instagram + Facebook)" />

  const ig = q.data.instagram.top_posts || []
  const fb = q.data.facebook.top_posts || []

  return (
    <section className="bg-white border border-neutral-200 rounded-xl p-4 h-full flex flex-col">
      <header className="flex items-center justify-between mb-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">Top posts</h3>
          <p className="text-[11px] text-neutral-500">Top 3 IG + top 3 FB por alcance (lifetime)</p>
        </div>
        <div className="w-9 h-9 rounded-lg bg-pink-50 text-pink-600 flex items-center justify-center">
          <Heart size={18} />
        </div>
      </header>
      <div className="flex-1 overflow-y-auto">
        {ig.length === 0 && fb.length === 0 ? (
          <div className="h-full flex items-center justify-center text-xs text-neutral-400">
            Sem dados — rode os syncs Meta.
          </div>
        ) : (
          <>
            {ig.length > 0 && (
              <div className="mb-2">
                <div className="text-[10px] uppercase tracking-wide text-pink-600 font-medium mb-1">Instagram</div>
                <ul>
                  {ig.map((p) => (
                    <PostRow key={p.post_external_id} post={p} channel="ig" />
                  ))}
                </ul>
              </div>
            )}
            {fb.length > 0 && (
              <div>
                <div className="text-[10px] uppercase tracking-wide text-blue-600 font-medium mb-1">Facebook</div>
                <ul>
                  {fb.map((p) => (
                    <PostRow key={p.post_external_id} post={p} channel="fb" />
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  )
}

export function MarketingStatusPixelCard() {
  const q = useMetaDashboard()
  if (q.isLoading) return <WidgetLoading label="Status Meta / TI" />
  if (q.isError || !q.data) return <WidgetError label="Status Meta / TI" />

  const { pixel, pending } = q.data
  const idle = pixel.pixel_days_idle ?? null
  const status: 'ok' | 'warn' | 'bad' =
    idle == null ? 'warn' : idle <= 7 ? 'ok' : idle <= 30 ? 'warn' : 'bad'
  const statusStyles = {
    ok: { bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'Ativo' },
    warn: { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Atenção' },
    bad: { bg: 'bg-rose-50', text: 'text-rose-700', label: 'Parado' },
  }[status]

  return (
    <section className="bg-white border border-neutral-200 rounded-xl p-4 h-full flex flex-col">
      <header className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900">Pixel & pendências TI</h3>
          <p className="text-[11px] text-neutral-500">Status Meta · checklist</p>
        </div>
        <span className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${statusStyles.bg} ${statusStyles.text}`}>
          {statusStyles.label}
        </span>
      </header>
      <div className="mb-3">
        <div className="text-xs text-neutral-500">Pixel — último disparo</div>
        <div className="text-sm font-semibold text-neutral-900">
          {pixel.pixel_last_fired_at
            ? new Date(pixel.pixel_last_fired_at).toLocaleDateString('pt-BR')
            : '—'}
          {idle != null && (
            <span className={`ml-2 text-[11px] font-normal ${idle > 30 ? 'text-rose-600' : 'text-neutral-400'}`}>
              ({idle}d idle)
            </span>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {pending.length === 0 ? (
          <div className="text-xs text-emerald-700 bg-emerald-50 rounded-md px-3 py-2">
            Tudo verde — nenhuma pendência da TI 🎉
          </div>
        ) : (
          <ul className="space-y-2">
            {pending.map((item) => (
              <li key={item.key} className="flex items-start gap-2 text-xs">
                <AlertCircle size={13} className="text-amber-500 mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <div className="font-medium text-neutral-800">{item.label}</div>
                  <div className="text-neutral-500 line-clamp-2">{item.detail}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
