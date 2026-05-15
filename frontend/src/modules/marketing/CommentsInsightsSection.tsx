/**
 * Bloco "Comentários da semana" — Sub-PR 21f.
 *
 * Lê `/meta/comments/insights?days=30` e mostra:
 *  - Contadores: total · leads quentes · dúvidas · depoimentos · reclamações
 *  - Sentimento (barra horizontal)
 *  - Top procedimentos mencionados (badges)
 *  - Listas: leads quentes (até 5) · dúvidas clínicas (até 5) · reclamações (até 3)
 *
 * Quando o sentimento ou as listas estiverem vazias, suprime o bloco —
 * evita estado "tudo zero" parecendo erro.
 */
import { useQuery } from '@tanstack/react-query'
import {
  AlertCircle, Flame, HelpCircle, Heart, MessageSquare, Smile,
  ThumbsDown,
} from 'lucide-react'

import { metaService } from '@/services/meta.service'
import type { MetaComment } from '@/types/meta'

const fmtNum = (n: number | null | undefined): string =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)

const fmtDate = (iso: string | null): string => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' })
}

export function CommentsInsightsSection() {
  const q = useQuery({
    queryKey: ['meta', 'comments-insights', 30],
    queryFn: () => metaService.commentsInsights(30),
  })

  if (q.isLoading) {
    return (
      <section className="bg-white border rounded-xl p-5 shadow-sm text-sm text-neutral-400 text-center">
        Analisando comentários…
      </section>
    )
  }
  if (q.isError || !q.data) return null
  const d = q.data
  // Não mostra o bloco se ainda não há comentários classificados
  if (d.counts.total === 0) return null

  const c = d.counts
  const pos = d.sentimento.positivo || 0
  const neg = d.sentimento.negativo || 0
  const neu = d.sentimento.neutro || 0
  const sentTotal = pos + neg + neu
  const pctPos = sentTotal ? Math.round((pos / sentTotal) * 100) : 0
  const pctNeu = sentTotal ? Math.round((neu / sentTotal) * 100) : 0
  const pctNeg = sentTotal ? Math.max(0, 100 - pctPos - pctNeu) : 0

  return (
    <section className="bg-white border rounded-xl shadow-sm overflow-hidden">
      <header className="px-5 py-3 border-b flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-neutral-800">Comentários da semana</h2>
          <p className="text-[11px] text-neutral-500">
            {fmtNum(c.total)} comentários classificados pela SonIA · últimos {d.period_days} dias
          </p>
        </div>
        <span className="text-[10px] uppercase tracking-wider text-fuchsia-600 font-medium">IA · DeepSeek</span>
      </header>

      <div className="p-5">
        {/* Contadores */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
          <CountStat
            label="Leads quentes"
            value={fmtNum(c.leads_quentes)}
            icon={<Flame size={14} />}
            tone="rose"
            emphasis={c.leads_quentes > 0}
          />
          <CountStat
            label="Dúvidas clínicas"
            value={fmtNum(c.duvidas_clinicas)}
            icon={<HelpCircle size={14} />}
            tone="amber"
          />
          <CountStat
            label="Depoimentos"
            value={fmtNum(c.depoimentos)}
            icon={<Heart size={14} />}
            tone="emerald"
          />
          <CountStat
            label="Objeções"
            value={fmtNum(c.objecoes)}
            icon={<MessageSquare size={14} />}
            tone="neutral"
          />
          <CountStat
            label="Reclamações"
            value={fmtNum(c.reclamacoes)}
            icon={<ThumbsDown size={14} />}
            tone="red"
            emphasis={c.reclamacoes > 0}
          />
        </div>

        {/* Sentimento + procedimentos */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-neutral-500 font-medium mb-2 inline-flex items-center gap-1">
              <Smile size={12} /> Sentimento geral
            </div>
            <div className="flex h-2 rounded-full overflow-hidden bg-neutral-100">
              {pctPos > 0 && (
                <div className="bg-emerald-500" style={{ width: `${pctPos}%` }} title={`Positivo ${pctPos}%`} />
              )}
              {pctNeu > 0 && (
                <div className="bg-neutral-400" style={{ width: `${pctNeu}%` }} title={`Neutro ${pctNeu}%`} />
              )}
              {pctNeg > 0 && (
                <div className="bg-rose-500" style={{ width: `${pctNeg}%` }} title={`Negativo ${pctNeg}%`} />
              )}
            </div>
            <div className="flex items-center gap-3 mt-2 text-[11px] tabular-nums">
              <span className="text-emerald-700">● {pctPos}% positivo</span>
              <span className="text-neutral-600">● {pctNeu}% neutro</span>
              <span className="text-rose-700">● {pctNeg}% negativo</span>
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-wider text-neutral-500 font-medium mb-2">
              Procedimentos mais mencionados
            </div>
            {d.top_procedimentos.length === 0 ? (
              <p className="text-xs text-neutral-400 italic">Nenhum procedimento específico mencionado.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {d.top_procedimentos.map((p) => (
                  <span
                    key={p.procedimento}
                    className="inline-flex items-center gap-1.5 bg-neutral-100 text-neutral-700 text-xs px-2 py-1 rounded-md"
                  >
                    <span className="capitalize">{p.procedimento}</span>
                    <span className="text-neutral-500 tabular-nums">{p.total}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Listas */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <CommentList
            title="Leads quentes — responder primeiro"
            tone="rose"
            icon={<Flame size={13} />}
            items={d.leads_quentes.slice(0, 5)}
            empty="Sem leads quentes na semana."
          />
          <CommentList
            title="Dúvidas clínicas"
            tone="amber"
            icon={<HelpCircle size={13} />}
            items={d.duvidas_clinicas.slice(0, 5)}
            empty="Sem dúvidas clínicas pendentes."
          />
        </div>
        {d.reclamacoes.length > 0 && (
          <div className="mt-4">
            <CommentList
              title="Reclamações"
              tone="red"
              icon={<AlertCircle size={13} />}
              items={d.reclamacoes.slice(0, 3)}
              empty=""
            />
          </div>
        )}
      </div>
    </section>
  )
}

// ─── Helpers ──────────────────────────────────────────────────

function CountStat({
  label, value, icon, tone, emphasis,
}: {
  label: string
  value: string
  icon: React.ReactNode
  tone: 'rose' | 'amber' | 'emerald' | 'red' | 'neutral'
  emphasis?: boolean
}) {
  const toneStyles = {
    rose: 'text-rose-700 bg-rose-50',
    amber: 'text-amber-700 bg-amber-50',
    emerald: 'text-emerald-700 bg-emerald-50',
    red: 'text-red-700 bg-red-50',
    neutral: 'text-neutral-700 bg-neutral-100',
  }[tone]
  return (
    <div className="bg-white border rounded-lg p-3">
      <div className={`inline-flex items-center gap-1 text-[10px] uppercase tracking-wider font-medium px-1.5 py-0.5 rounded ${toneStyles}`}>
        {icon} {label}
      </div>
      <div className={`text-2xl font-bold tabular-nums mt-2 ${emphasis ? 'text-neutral-900' : 'text-neutral-700'}`}>
        {value}
      </div>
    </div>
  )
}

function CommentList({
  title, tone, icon, items, empty,
}: {
  title: string
  tone: 'rose' | 'amber' | 'red'
  icon: React.ReactNode
  items: MetaComment[]
  empty: string
}) {
  const toneStyles = {
    rose: { dot: 'bg-rose-500', label: 'text-rose-700' },
    amber: { dot: 'bg-amber-500', label: 'text-amber-700' },
    red: { dot: 'bg-red-600', label: 'text-red-700' },
  }[tone]
  return (
    <div>
      <div className={`text-[10px] uppercase tracking-wider font-medium mb-2 inline-flex items-center gap-1 ${toneStyles.label}`}>
        {icon} {title}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-neutral-400 italic">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((c) => (
            <li key={c.external_id} className="flex items-start gap-2.5 p-2 rounded-md hover:bg-neutral-50 transition">
              <span className={`w-1.5 h-1.5 rounded-full mt-2 ${toneStyles.dot} shrink-0`} aria-hidden />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5 text-[11px] text-neutral-500">
                  <span className="font-medium text-neutral-700">@{c.autor || '—'}</span>
                  {c.procedimento && (
                    <span className="bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded text-[10px] capitalize">
                      {c.procedimento}
                    </span>
                  )}
                  <span className="ml-auto tabular-nums">{fmtDate(c.commented_at)}</span>
                </div>
                <p className="text-xs text-neutral-700 mt-0.5 line-clamp-2">{c.texto}</p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
