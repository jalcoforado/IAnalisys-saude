/**
 * Bloco "Stories da semana" — Sub-PR 21f.1.
 *
 * Lê `/meta/stories?days=7` e mostra:
 *  - 3 contadores: total · alcance médio · navegações totais
 *  - Carrossel horizontal de thumbnails (até 12) com badges de tipo
 *
 * Suprime o bloco se não há stories no período — evita estado vazio.
 */
import { useQuery } from '@tanstack/react-query'
import { Activity, Camera, ChevronsRight, Eye, MessageCircle, Play } from 'lucide-react'

import { metaService } from '@/services/meta.service'

const fmtNum = (n: number | null | undefined): string =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)

const fmtDate = (iso: string | null): string => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

export function StoriesSection() {
  const q = useQuery({
    queryKey: ['meta', 'stories', 7],
    queryFn: () => metaService.stories(7),
  })

  if (q.isLoading || q.isError || !q.data) return null
  const d = q.data
  if (d.totals.stories === 0) return null

  return (
    <section className="bg-white border rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-3 border-b flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-neutral-800">Stories da semana</h2>
          <p className="text-[11px] text-neutral-500">
            {fmtNum(d.totals.stories)} stories capturados nos últimos {d.period_days} dias
          </p>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-pink-600 font-medium">Instagram</span>
      </header>

      <div className="p-5">
        {/* Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          <StoryStat
            label="Alcance total"
            value={fmtNum(d.totals.reach_total)}
            icon={<Activity size={14} className="text-blue-600" />}
          />
          <StoryStat
            label="Alcance médio"
            value={fmtNum(d.totals.avg_reach)}
            hint="por story"
            icon={<Eye size={14} className="text-violet-600" />}
          />
          <StoryStat
            label="Navegações"
            value={fmtNum(d.totals.navigation_total)}
            hint="taps + swipes"
            icon={<ChevronsRight size={14} className="text-emerald-600" />}
          />
          <StoryStat
            label="Replies"
            value={fmtNum(d.totals.replies_total)}
            hint={d.totals.replies_total > 0 ? 'DMs recebidos' : 'nenhuma DM'}
            icon={<MessageCircle size={14} className="text-rose-600" />}
            emphasis={d.totals.replies_total > 0}
          />
        </div>

        {/* Carrossel de stories */}
        <div className="flex gap-2 overflow-x-auto pb-1 -mx-1 px-1">
          {d.items.map((s) => (
            <StoryThumb key={s.external_id} story={s} />
          ))}
        </div>

        <p className="text-[11px] text-neutral-400 mt-3">
          {d.totals.n_video} vídeo{d.totals.n_video === 1 ? '' : 's'}
          {' · '}
          {d.totals.n_image} imagem{d.totals.n_image === 1 ? '' : 'ns'}
          {' · stories expiram em 24h — sync diário no scheduler 04:05'}
        </p>
      </div>
    </section>
  )
}

function StoryStat({
  label, value, hint, icon, emphasis,
}: {
  label: string
  value: string
  hint?: string
  icon: React.ReactNode
  emphasis?: boolean
}) {
  return (
    <div className="bg-neutral-50 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-neutral-500 inline-flex items-center gap-1">
        {icon} {label}
      </div>
      <div className={`text-xl font-bold tabular-nums mt-0.5 ${emphasis ? 'text-rose-600' : 'text-neutral-900'}`}>
        {value}
      </div>
      {hint && <div className="text-[11px] text-neutral-400 mt-0.5">{hint}</div>}
    </div>
  )
}

function StoryThumb({ story }: { story: {
  external_id: string
  posted_at: string | null
  media_type: string | null
  thumbnail_url: string | null
  permalink: string | null
  reach: number
  navigation: number
} }) {
  const content = (
    <>
      <div className="aspect-[9/16] bg-neutral-900 rounded-md overflow-hidden relative">
        {story.thumbnail_url ? (
          <img
            src={story.thumbnail_url}
            alt=""
            className="w-full h-full object-cover"
            referrerPolicy="no-referrer"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-neutral-500">
            <Camera size={20} />
          </div>
        )}
        {story.media_type === 'VIDEO' && (
          <div className="absolute top-1.5 right-1.5 bg-black/60 rounded-full p-1 text-white">
            <Play size={9} fill="currentColor" />
          </div>
        )}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent p-1.5 text-white text-[10px] tabular-nums leading-tight">
          <div className="flex items-center gap-1">
            <Eye size={9} /> {fmtNum(story.reach)}
          </div>
        </div>
      </div>
      <div className="text-[10px] text-neutral-500 text-center mt-1 tabular-nums">
        {fmtDate(story.posted_at)}
      </div>
    </>
  )
  const className = "w-20 sm:w-24 shrink-0"
  if (story.permalink) {
    return (
      <a
        href={story.permalink}
        target="_blank"
        rel="noreferrer"
        className={`${className} cursor-pointer hover:opacity-80 transition`}
        title="Abrir story no Instagram"
      >
        {content}
      </a>
    )
  }
  return <div className={className}>{content}</div>
}
