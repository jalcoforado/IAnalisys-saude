import { useEffect, useState } from 'react'
import { ChevronRight, Loader2, RefreshCw, Sparkles, X } from 'lucide-react'
import SonIAAvatar from './SonIAAvatar'
import SonIABrand from './SonIABrand'
import { useSonIA, type SonIAInsight } from './SonIAContext'
import { analyze } from './SonIAAnalyzers'

/**
 * FAB da SonIA — ao abrir, faz "varredura" da página atual (700ms com avatar
 * em thinking) e mostra o insight gerado pelo analyzer central. Botão de
 * refazer força nova análise. Sem LLM ainda — heurística.
 */
export default function SonIAFab() {
  const [analyzing, setAnalyzing] = useState(false)
  const [insight, setInsight] = useState<SonIAInsight | null>(null)

  const { publication, bumpToken, bump, open, setOpen } = useSonIA()

  useEffect(() => {
    if (!open) return
    setAnalyzing(true)
    setInsight(null)
    const t = setTimeout(() => {
      setInsight(analyze(publication))
      setAnalyzing(false)
    }, 700)
    return () => clearTimeout(t)
  }, [open, publication, bumpToken])

  const subtitle = publication?.pageTitle
    ? `Analisando "${publication.pageTitle}"`
    : 'Sempre por perto, com carinho'

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3 print:hidden">
      {open && (
        <div className="relative w-96 max-w-[calc(100vw-3rem)] mt-20">
          {/* Painel — overflow visible pra avatar transbordar */}
          <div className="bg-white border border-neutral-200 rounded-2xl shadow-xl">
            {/* Header — padding-left grande pra acomodar avatar que sai pra cima/esquerda */}
            <div className="pl-40 pr-12 py-4 bg-gradient-to-r from-primary-50 to-white border-b border-neutral-100 min-h-[96px] flex flex-col justify-center rounded-t-2xl">
              <div className="leading-tight">
                <SonIABrand size="xl" />
              </div>
              <div className="text-xs text-neutral-500 truncate mt-0.5">{subtitle}</div>
            </div>

            <div className="px-4 py-4 text-sm text-neutral-700">
              {analyzing && (
                <div className="flex items-center gap-2 text-neutral-500 text-sm py-2">
                  <Loader2 size={14} className="animate-spin" />
                  Dando uma olhadinha por aqui…
                </div>
              )}

              {!analyzing && insight && <InsightView insight={insight} />}
            </div>

            {!analyzing && insight && (
              <div className="px-4 py-2 border-t border-neutral-100 bg-neutral-50/60 flex items-center justify-between text-xs text-neutral-500 rounded-b-2xl">
                <span className="inline-flex items-center gap-1">
                  <Sparkles size={11} /> {insight.source || 'Análise'}
                </span>
                <button
                  type="button"
                  onClick={() => bump()}
                  className="inline-flex items-center gap-1 text-neutral-600 hover:text-primary-700 transition font-medium"
                >
                  <RefreshCw size={11} /> Refazer
                </button>
              </div>
            )}
          </div>

          {/* Avatar grande "se debruçando" — transborda pra cima e esquerda */}
          <div className="absolute -top-16 left-2 z-10 pointer-events-none">
            <SonIAAvatar
              mood={analyzing ? 'thinking' : insight?.mood ?? 'default'}
              size="2xl"
              ring
              pulse={analyzing}
              className="shadow-2xl"
            />
          </div>

          {/* Close — absoluto no canto superior direito do painel */}
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="absolute top-3 right-3 z-10 w-7 h-7 rounded-full bg-white/80 hover:bg-white border border-neutral-200 text-neutral-500 hover:text-neutral-800 transition flex items-center justify-center shadow-sm"
            aria-label="Fechar"
          >
            <X size={14} />
          </button>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="group relative w-14 h-14 rounded-full bg-white border-2 border-primary-200 shadow-lg hover:shadow-xl hover:border-primary-400 transition overflow-hidden"
        aria-label={open ? 'Fechar SonIA' : 'Abrir SonIA'}
        title="SonIA — sua assistente de IA"
      >
        <SonIAAvatar
          mood="default"
          size="lg"
          className="w-full h-full border-0 rounded-full group-hover:scale-105 transition-transform"
        />
        <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-emerald-500 rounded-full border-2 border-white" />
      </button>
    </div>
  )
}

function InsightView({ insight }: { insight: SonIAInsight }) {
  return (
    <div className="space-y-2">
      <div className="font-semibold text-neutral-900 leading-snug">{insight.headline}</div>
      <p className="text-neutral-700 leading-snug">{insight.detail}</p>

      {insight.bullets && insight.bullets.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {insight.bullets.map((b, i) => (
            <li key={i} className="flex items-start gap-2 text-[13px]">
              <span className={`mt-1.5 w-1.5 h-1.5 rounded-full shrink-0 ${bulletColor(b.tone)}`} />
              <span className="text-neutral-700 leading-snug">{b.text}</span>
            </li>
          ))}
        </ul>
      )}

      {insight.ctaHref && insight.ctaLabel && (
        <a
          href={insight.ctaHref}
          className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-primary-700 hover:text-primary-900 transition"
        >
          {insight.ctaLabel}
          <ChevronRight size={14} />
        </a>
      )}
    </div>
  )
}

function bulletColor(tone?: 'neutral' | 'positive' | 'negative' | 'warning') {
  switch (tone) {
    case 'positive': return 'bg-emerald-500'
    case 'negative': return 'bg-rose-500'
    case 'warning': return 'bg-amber-500'
    default: return 'bg-primary-500'
  }
}
