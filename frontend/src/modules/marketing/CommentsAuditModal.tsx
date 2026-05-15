/**
 * Modal de auditoria dos comentários classificados — Sub-PR 21f.
 *
 * Full-screen com filtros (sentimento + flag + busca + período) e tabela
 * paginada. Permite ver TODOS os comentários classificados pra conferir
 * se a IA acertou — útil pra calibrar o classificador no início.
 */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronLeft, ChevronRight, Flame, Heart, HelpCircle, MessageSquare,
  Search, ThumbsDown, X,
} from 'lucide-react'

import { metaService } from '@/services/meta.service'

const fmtNum = (n: number): string => new Intl.NumberFormat('pt-BR').format(n)

const fmtDate = (iso: string | null): string => {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: '2-digit' })
}

const PAGE_SIZE = 25

interface Props {
  open: boolean
  onClose: () => void
  /** Filtro inicial: 'lead_quente' | 'depoimento' | etc. Vazio = todos. */
  initialFlag?: string
}

export function CommentsAuditModal({ open, onClose, initialFlag = '' }: Props) {
  const [page, setPage] = useState(0)
  const [sentimento, setSentimento] = useState<string>('')
  const [flag, setFlag] = useState<string>(initialFlag)
  const [days, setDays] = useState<number>(30)
  const [q, setQ] = useState<string>('')
  const [qDebounced, setQDebounced] = useState<string>('')

  const q1 = useQuery({
    queryKey: ['meta', 'comments', 'list', { page, sentimento, flag, days, q: qDebounced }],
    queryFn: () =>
      metaService.commentsList({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        sentimento: sentimento || undefined,
        flag: flag || undefined,
        days,
        q: qDebounced || undefined,
      }),
    enabled: open,
  })

  if (!open) return null

  const onChangeSentimento = (v: string) => { setSentimento(v); setPage(0) }
  const onChangeFlag = (v: string) => { setFlag(v); setPage(0) }
  const onChangeDays = (v: number) => { setDays(v); setPage(0) }
  const onSubmitSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setQDebounced(q)
    setPage(0)
  }

  const total = q1.data?.total ?? 0
  const items = q1.data?.items ?? []
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div
      className="fixed inset-0 z-[100] bg-black/60 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <header className="px-5 py-4 border-b flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-neutral-900">
              Auditoria de comentários classificados
            </h2>
            <p className="text-xs text-neutral-500">
              {q1.isLoading ? 'Carregando…' : `${fmtNum(total)} comentário${total === 1 ? '' : 's'} no filtro`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-900 p-1.5 rounded-lg hover:bg-neutral-100"
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </header>

        {/* Filtros */}
        <section className="px-5 py-3 border-b bg-neutral-50 flex flex-wrap items-center gap-2">
          <FilterChip label="Todos" active={sentimento === ''} onClick={() => onChangeSentimento('')} />
          <FilterChip
            label="Positivo"
            active={sentimento === 'positivo'}
            onClick={() => onChangeSentimento('positivo')}
            tone="emerald"
          />
          <FilterChip
            label="Neutro"
            active={sentimento === 'neutro'}
            onClick={() => onChangeSentimento('neutro')}
            tone="neutral"
          />
          <FilterChip
            label="Negativo"
            active={sentimento === 'negativo'}
            onClick={() => onChangeSentimento('negativo')}
            tone="rose"
          />

          <div className="w-px h-5 bg-neutral-300 mx-1" />

          <FilterChip
            label="Todas flags"
            active={flag === ''}
            onClick={() => onChangeFlag('')}
          />
          <FilterChip
            label="🔥 Leads quentes"
            active={flag === 'lead_quente'}
            onClick={() => onChangeFlag('lead_quente')}
            tone="rose"
          />
          <FilterChip
            label="❓ Dúvidas"
            active={flag === 'duvida'}
            onClick={() => onChangeFlag('duvida')}
            tone="amber"
          />
          <FilterChip
            label="❤ Depoimentos"
            active={flag === 'depoimento'}
            onClick={() => onChangeFlag('depoimento')}
            tone="emerald"
          />
          <FilterChip
            label="🚫 Objeções"
            active={flag === 'objecao'}
            onClick={() => onChangeFlag('objecao')}
          />
          <FilterChip
            label="⚠ Reclamações"
            active={flag === 'reclamacao'}
            onClick={() => onChangeFlag('reclamacao')}
            tone="red"
          />

          <div className="w-px h-5 bg-neutral-300 mx-1" />

          <select
            value={days}
            onChange={(e) => onChangeDays(Number(e.target.value))}
            className="text-xs border rounded-md px-2 py-1 bg-white"
          >
            <option value={7}>Últimos 7 dias</option>
            <option value={30}>Últimos 30 dias</option>
            <option value={90}>Últimos 90 dias</option>
            <option value={365}>Último ano</option>
          </select>

          <form onSubmit={onSubmitSearch} className="flex items-center gap-1 ml-auto">
            <div className="relative">
              <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Buscar texto ou autor…"
                className="text-xs border rounded-md pl-7 pr-2 py-1 w-56"
              />
            </div>
            <button
              type="submit"
              className="text-xs px-2 py-1 bg-neutral-800 text-white rounded-md"
            >
              Buscar
            </button>
          </form>
        </section>

        {/* Tabela */}
        <div className="flex-1 overflow-auto">
          {q1.isLoading ? (
            <div className="text-center text-neutral-400 text-sm py-12">Carregando…</div>
          ) : items.length === 0 ? (
            <div className="text-center text-neutral-400 text-sm py-12">
              Nenhum comentário com esse filtro.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-neutral-50 sticky top-0 z-10">
                <tr className="text-[10px] uppercase tracking-wider text-neutral-500">
                  <th className="text-left px-4 py-2 font-semibold">Autor</th>
                  <th className="text-left px-4 py-2 font-semibold">Texto</th>
                  <th className="text-center px-2 py-2 font-semibold">Sentimento</th>
                  <th className="text-left px-2 py-2 font-semibold">Flags</th>
                  <th className="text-left px-2 py-2 font-semibold">Procedimento</th>
                  <th className="text-center px-2 py-2 font-semibold">Urg.</th>
                  <th className="text-right px-2 py-2 font-semibold">Data</th>
                  <th className="text-center px-2 py-2 font-semibold">IA</th>
                </tr>
              </thead>
              <tbody>
                {items.map((c) => (
                  <tr key={c.external_id} className="border-t hover:bg-neutral-50">
                    <td className="px-4 py-2 align-top">
                      <div className="text-xs font-medium text-neutral-800 truncate max-w-[140px]">
                        @{c.autor || '—'}
                      </div>
                    </td>
                    <td className="px-4 py-2 align-top max-w-[360px]">
                      <p className="text-xs text-neutral-700 line-clamp-3">{c.texto}</p>
                    </td>
                    <td className="px-2 py-2 align-top text-center">
                      <SentimentBadge value={c.sentimento} />
                    </td>
                    <td className="px-2 py-2 align-top">
                      <FlagBadges flags={c.flags} />
                    </td>
                    <td className="px-2 py-2 align-top">
                      {c.procedimento ? (
                        <span className="inline-block text-[11px] bg-neutral-100 text-neutral-700 px-1.5 py-0.5 rounded capitalize">
                          {c.procedimento}
                        </span>
                      ) : (
                        <span className="text-neutral-300 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-2 py-2 align-top text-center">
                      <UrgenciaBadge value={c.urgencia} />
                    </td>
                    <td className="px-2 py-2 align-top text-right text-[11px] text-neutral-500 tabular-nums whitespace-nowrap">
                      {fmtDate(c.commented_at)}
                    </td>
                    <td className="px-2 py-2 align-top text-center">
                      <span
                        className="text-[10px] text-neutral-400"
                        title={c.modelo_ia || ''}
                      >
                        {c.modelo_ia?.startsWith('deepseek') ? 'IA' : 'fast'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Footer com paginação */}
        <footer className="px-5 py-3 border-t flex items-center justify-between text-xs text-neutral-600">
          <div>
            Página {page + 1} de {totalPages} · mostrando até {PAGE_SIZE} por página
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-2 py-1 border rounded-md disabled:opacity-40 disabled:cursor-not-allowed hover:bg-neutral-100 inline-flex items-center gap-1"
            >
              <ChevronLeft size={12} /> Anterior
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page + 1 >= totalPages}
              className="px-2 py-1 border rounded-md disabled:opacity-40 disabled:cursor-not-allowed hover:bg-neutral-100 inline-flex items-center gap-1"
            >
              Próxima <ChevronRight size={12} />
            </button>
          </div>
        </footer>
      </div>
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────

function FilterChip({
  label, active, onClick, tone,
}: {
  label: string
  active: boolean
  onClick: () => void
  tone?: 'emerald' | 'rose' | 'amber' | 'red' | 'neutral'
}) {
  const toneStyles = {
    emerald: 'bg-emerald-600 text-white',
    rose: 'bg-rose-600 text-white',
    amber: 'bg-amber-600 text-white',
    red: 'bg-red-600 text-white',
    neutral: 'bg-neutral-700 text-white',
  }
  const activeBg = tone ? toneStyles[tone] : 'bg-neutral-800 text-white'
  return (
    <button
      onClick={onClick}
      className={`text-[11px] px-2.5 py-1 rounded-full font-medium transition ${
        active ? activeBg : 'bg-white border text-neutral-700 hover:bg-neutral-100'
      }`}
    >
      {label}
    </button>
  )
}

function SentimentBadge({ value }: { value: 'positivo' | 'neutro' | 'negativo' | null }) {
  if (!value) return <span className="text-neutral-300">—</span>
  const styles = {
    positivo: 'bg-emerald-50 text-emerald-700',
    neutro: 'bg-neutral-100 text-neutral-700',
    negativo: 'bg-rose-50 text-rose-700',
  }[value]
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded ${styles}`}>
      {value === 'positivo' ? '+' : value === 'negativo' ? '−' : '○'} {value}
    </span>
  )
}

function FlagBadges({ flags }: { flags: {
  lead_quente: boolean
  depoimento: boolean
  duvida_clinica: boolean
  objecao: boolean
  reclamacao: boolean
} }) {
  const items = [
    { key: 'lead_quente', icon: <Flame size={10} />, label: 'Lead', cls: 'bg-rose-100 text-rose-700' },
    { key: 'duvida_clinica', icon: <HelpCircle size={10} />, label: 'Dúvida', cls: 'bg-amber-100 text-amber-700' },
    { key: 'depoimento', icon: <Heart size={10} />, label: 'Depo', cls: 'bg-emerald-100 text-emerald-700' },
    { key: 'objecao', icon: <MessageSquare size={10} />, label: 'Obj', cls: 'bg-neutral-200 text-neutral-700' },
    { key: 'reclamacao', icon: <ThumbsDown size={10} />, label: 'Reclam', cls: 'bg-red-100 text-red-700' },
  ] as const
  const active = items.filter((it) => (flags as any)[it.key])
  if (active.length === 0) return <span className="text-neutral-300 text-xs">—</span>
  return (
    <div className="flex flex-wrap gap-1">
      {active.map((it) => (
        <span
          key={it.key}
          className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded ${it.cls}`}
        >
          {it.icon} {it.label}
        </span>
      ))}
    </div>
  )
}

function UrgenciaBadge({ value }: { value: 'alta' | 'media' | 'baixa' | null }) {
  if (!value) return <span className="text-neutral-300">—</span>
  const styles = {
    alta: 'text-rose-700',
    media: 'text-amber-700',
    baixa: 'text-neutral-500',
  }[value]
  return <span className={`text-[10px] font-medium uppercase ${styles}`}>{value}</span>
}

