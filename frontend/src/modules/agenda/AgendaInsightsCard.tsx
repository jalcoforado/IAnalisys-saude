/**
 * Insights da agenda do dia. Três blocos:
 *  1. KPIs gerais   — volume, profissionais, janela, tempo total/médio
 *  2. Status agora  — Confirmado / Chegou / Em atendimento / Atendido / Faltou
 *  3. Categorias    — distribuição por bucket semântico (consulta/retorno/...)
 *
 * Tudo computado no front a partir do AgendaSection. Quando o Sub-PR 17b
 * (IA Anthropic) estiver pronto, este card vira a "view" e a IA gera prosa
 * narrativa por cima destes números.
 */
import { Sparkles, Clock, Users, Loader2, RefreshCw, AlertTriangle } from 'lucide-react'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { AgendaSection } from '@/types/home'
import {
  STATUS_LABEL,
  STATUS_DOT,
  CATEGORY_GROUP_LABEL,
} from './helpers'
import type { CategoryGroup, StatusType } from '@/types/home'
import { homeService, type AgendaAISummaryResponse } from '@/services/home.service'

const fmtMin = (m: number) => {
  if (m >= 60) {
    const h = Math.floor(m / 60)
    const rest = m % 60
    return rest === 0 ? `${h}h` : `${h}h${rest.toString().padStart(2, '0')}`
  }
  return `${m}min`
}

// Ordem fixa pra apresentação consistente (não alfabética).
const STATUS_ORDER: StatusType[] = [
  'CONFIRMED', 'ARRIVED', 'IN_SESSION', 'CHECKOUT', 'LATE', 'MISSED', 'CALL', 'PENDING_MATERIAL',
]
const CATEGORY_ORDER: CategoryGroup[] = [
  'consulta', 'retorno', 'manutencao', 'procedimento', 'reabilitacao', 'ortodontia', 'bloqueio', 'outro',
]
const CATEGORY_DOT: Record<CategoryGroup, string> = {
  consulta: 'bg-blue-500',
  retorno: 'bg-emerald-500',
  manutencao: 'bg-cyan-500',
  procedimento: 'bg-purple-500',
  reabilitacao: 'bg-amber-500',
  ortodontia: 'bg-pink-500',
  bloqueio: 'bg-red-500',
  outro: 'bg-neutral-400',
}

function AINarrative() {
  const [generated, setGenerated] = useState<AgendaAISummaryResponse | null>(null)
  const mut = useMutation({
    mutationFn: () => homeService.agendaAISummary(),
    onSuccess: (data) => setGenerated(data),
  })

  const errMsg = mut.error
    ? (mut.error as { response?: { data?: { detail?: string } } }).response?.data?.detail
        ?? (mut.error as Error).message
    : null

  return (
    <div className="border-t border-neutral-200 px-4 py-3 bg-gradient-to-br from-purple-50/40 to-pink-50/30">
      <div className="flex items-center gap-2 mb-2">
        <Sparkles size={14} className="text-purple-600" />
        <span className="text-[10px] uppercase tracking-wide font-semibold text-neutral-500">
          Análise da agenda
        </span>
        {generated && (
          <button
            onClick={() => mut.mutate()}
            disabled={mut.isPending}
            className="ml-auto text-[10px] inline-flex items-center gap-1 text-purple-700 hover:text-purple-900 font-medium"
          >
            {mut.isPending ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
            Atualizar
          </button>
        )}
      </div>

      {!generated && !mut.isPending && !errMsg && (
        <button
          onClick={() => mut.mutate()}
          className="w-full text-left px-3 py-2.5 rounded-lg border border-dashed border-purple-300 bg-white/70 hover:bg-white hover:border-purple-400 transition-all text-[12px] text-neutral-600 flex items-center gap-2"
        >
          <Sparkles size={14} className="text-purple-600 shrink-0" />
          <span>Gerar análise IA dos próximos 3 dias (Claude)</span>
        </button>
      )}

      {mut.isPending && (
        <div className="flex items-center gap-2 text-[12px] text-neutral-600 px-3 py-2.5">
          <Loader2 size={14} className="animate-spin text-purple-600" />
          Gerando análise…
        </div>
      )}

      {errMsg && !mut.isPending && (
        <div className="px-3 py-2.5 rounded-lg border border-amber-300 bg-amber-50 text-[12px] text-amber-800 flex items-start gap-2">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold mb-0.5">Não consegui gerar agora</div>
            <div className="text-amber-700">{errMsg}</div>
            <button
              onClick={() => mut.mutate()}
              className="mt-1.5 text-amber-900 hover:text-amber-950 font-medium underline"
            >
              Tentar de novo
            </button>
          </div>
        </div>
      )}

      {generated && !mut.isPending && (
        <div className="px-3 py-2.5 rounded-lg bg-white/80 border border-purple-200 text-[12.5px] text-neutral-800 leading-relaxed whitespace-pre-line">
          {generated.narrative}
          <div className="mt-1.5 text-[9px] uppercase tracking-wider text-neutral-400">
            via {generated.model}
          </div>
        </div>
      )}
    </div>
  )
}

export function AgendaInsightsCard({ data }: { data: AgendaSection }) {
  const items = data.items
  const total = items.length

  // ── Tempo de atendimento ─────────────────────────────────────
  const durations = items.map(i => i.duration_minutes ?? 0).filter(d => d > 0)
  const totalMin = durations.reduce((s, d) => s + d, 0)
  const avgMin = durations.length > 0 ? Math.round(totalMin / durations.length) : 0

  // Profissionais distintos
  const profsCount = new Set(items.map(i => i.profissional_external_id).filter(id => id != null)).size

  // Janela do dia
  const horarios = items.map(i => i.horario).filter(Boolean) as string[]
  const sorted = horarios.slice().sort()
  const primeira = sorted[0] ?? '—'
  const ultima = sorted[sorted.length - 1] ?? '—'

  // ── Status counts ────────────────────────────────────────────
  const statusCounts = new Map<StatusType | 'AGENDADO', number>()
  for (const it of items) {
    const key = it.status_type ?? 'AGENDADO'
    statusCounts.set(key, (statusCounts.get(key) ?? 0) + 1)
  }
  const agendadoQty = statusCounts.get('AGENDADO') ?? 0

  // ── Categoria counts ─────────────────────────────────────────
  const categoryCounts = new Map<CategoryGroup, number>()
  for (const it of items) {
    const key = it.category_group ?? 'outro'
    categoryCounts.set(key, (categoryCounts.get(key) ?? 0) + 1)
  }

  return (
    <div className="rounded-xl border border-neutral-200 bg-gradient-to-br from-white to-neutral-50 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center">
          <Sparkles size={16} className="text-white" />
        </div>
        <div>
          <div className="text-sm font-semibold text-neutral-800">Insights da agenda</div>
          <div className="text-[11px] text-neutral-500">Análise automática · {total} consultas</div>
        </div>
      </div>

      {/* Bloco IA: prosa narrativa gerada sob demanda (Sub-PR 17b) */}
      <AINarrative />

      {/* Bloco 1: KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-0 divide-y sm:divide-y-0 sm:divide-x divide-neutral-100">
        <Kpi label="Janela" value={`${primeira} → ${ultima}`} />
        <Kpi label="Profissionais" value={String(profsCount)} icon={<Users size={12} />} />
        <Kpi label="Tempo total" value={totalMin > 0 ? fmtMin(totalMin) : '—'} icon={<Clock size={12} />} />
        <Kpi label="Tempo médio" value={avgMin > 0 ? fmtMin(avgMin) : '—'} />
      </div>

      {/* Bloco 2: Status agora */}
      <div className="border-t border-neutral-200 px-4 py-3">
        <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2">
          Status agora
        </div>
        <div className="flex flex-wrap gap-2">
          {agendadoQty > 0 && (
            <StatusPill label="Agendado" count={agendadoQty} dotClass="bg-neutral-300" total={total} />
          )}
          {STATUS_ORDER.map((s) => {
            const c = statusCounts.get(s) ?? 0
            if (c === 0) return null
            return <StatusPill key={s} label={STATUS_LABEL[s]} count={c} dotClass={STATUS_DOT[s]} total={total} />
          })}
        </div>
      </div>

      {/* Bloco 3: Categorias */}
      <div className="border-t border-neutral-200 px-4 py-3">
        <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400 mb-2">
          Razão da consulta
        </div>
        <div className="space-y-1.5">
          {CATEGORY_ORDER.map((g) => {
            const c = categoryCounts.get(g) ?? 0
            if (c === 0) return null
            const pct = total > 0 ? (c / total) * 100 : 0
            return (
              <div key={g} className="flex items-center gap-2 text-[11px]">
                <span className={`w-2 h-2 rounded-full ${CATEGORY_DOT[g]} shrink-0`} />
                <span className="text-neutral-700 font-medium w-24 shrink-0">{CATEGORY_GROUP_LABEL[g]}</span>
                <div className="flex-1 h-1.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full ${CATEGORY_DOT[g]} opacity-80 transition-all`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-neutral-500 tabular-nums w-14 text-right">
                  {c} · {Math.round(pct)}%
                </span>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function Kpi({
  label, value, icon,
}: {
  label: string; value: string; icon?: React.ReactNode
}) {
  return (
    <div className="px-4 py-3 text-center">
      <div className="text-[10px] uppercase tracking-wide font-semibold text-neutral-400">{label}</div>
      <div className="text-base font-bold text-neutral-800 mt-1 flex items-center gap-1 justify-center">
        {icon && <span className="text-neutral-400">{icon}</span>}
        <span>{value}</span>
      </div>
    </div>
  )
}

function StatusPill({
  label, count, dotClass, total,
}: {
  label: string; count: number; dotClass: string; total: number
}) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0
  return (
    <div className="inline-flex items-center gap-1.5 bg-white border border-neutral-200 rounded-full pl-2 pr-2.5 py-1 text-[11px]">
      <span className={`w-2 h-2 rounded-full ${dotClass}`} />
      <span className="font-medium text-neutral-700">{label}</span>
      <span className="font-bold text-neutral-900 tabular-nums">{count}</span>
      <span className="text-neutral-400">·</span>
      <span className="text-neutral-500 tabular-nums">{pct}%</span>
    </div>
  )
}
