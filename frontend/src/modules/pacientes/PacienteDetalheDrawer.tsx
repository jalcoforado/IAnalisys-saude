/**
 * Drawer slide-in lateral com histórico do paciente.
 * Aciona-se passando `patientExternalId` (>0). Fecha em ESC ou click no X.
 */
import { useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity, Calendar, CheckCircle2, Clock, Crown, FileText, HeartPulse,
  Loader2, Mail, Phone, User, X, XCircle,
} from 'lucide-react'

import { analiseService } from '@/services/analise.service'
import type { PacienteHistoricoConsulta, PacienteHistoricoOrcamento } from '@/types/analise'

const fmtBRL = (n: number, compact = false) => {
  if (compact && Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(2)}M`
  if (compact && Math.abs(n) >= 1_000) return `R$ ${(n / 1_000).toFixed(0)}k`
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency', currency: 'BRL', maximumFractionDigits: 0,
  }).format(n)
}
const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtDate = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}
const fmtMonthYear = (iso: string) => {
  const d = new Date(iso)
  return d.toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' })
}

const BUCKET_META: Record<string, { label: string; bg: string; text: string }> = {
  ativo:      { label: 'Ativo',      bg: 'bg-emerald-100', text: 'text-emerald-700' },
  em_risco:   { label: 'Em risco',   bg: 'bg-amber-100',   text: 'text-amber-700' },
  inativo:    { label: 'Inativo',    bg: 'bg-orange-100',  text: 'text-orange-700' },
  perdido:    { label: 'Perdido',    bg: 'bg-rose-100',    text: 'text-rose-700' },
  sem_visita: { label: 'Sem visita', bg: 'bg-neutral-100', text: 'text-neutral-600' },
}

const STATUS_META: Record<string, { label: string; bg: string; text: string }> = {
  APPROVED: { label: 'APROVADO',   bg: 'bg-emerald-100', text: 'text-emerald-700' },
  FOLLOWUP: { label: 'EM DECISÃO', bg: 'bg-amber-100',   text: 'text-amber-700' },
  OPEN:     { label: 'ABERTO',     bg: 'bg-blue-100',    text: 'text-blue-700' },
  REJECTED: { label: 'REJEITADO',  bg: 'bg-rose-100',    text: 'text-rose-700' },
}

const DESF_META: Record<string, { label: string; bg: string; text: string; icon: React.ReactNode }> = {
  efetiva:    { label: 'Efetiva',     bg: 'bg-emerald-50',  text: 'text-emerald-700', icon: <CheckCircle2 size={11} /> },
  falta:      { label: 'Falta',       bg: 'bg-rose-50',     text: 'text-rose-700',    icon: <XCircle size={11} /> },
  cancelada:  { label: 'Cancelada',   bg: 'bg-orange-50',   text: 'text-orange-700',  icon: <XCircle size={11} /> },
  indefinida: { label: 'Sem status',  bg: 'bg-neutral-100', text: 'text-neutral-600', icon: <Clock size={11} /> },
  outro:      { label: 'Outro',       bg: 'bg-sky-50',      text: 'text-sky-700',     icon: <Activity size={11} /> },
}

export default function PacienteDetalheDrawer({
  patientExternalId, onClose,
}: { patientExternalId: number; onClose: () => void }) {
  const query = useQuery({
    queryKey: ['analise', 'paciente-historico', patientExternalId],
    queryFn: () => analiseService.pacienteHistorico(patientExternalId),
    staleTime: 30_000,
  })

  // ESC fecha
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onEsc)
    return () => window.removeEventListener('keydown', onEsc)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-3xl bg-white shadow-2xl flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="px-5 py-4 border-b border-neutral-200 flex items-start justify-between gap-3 bg-gradient-to-r from-neutral-50 to-white">
          <div className="min-w-0">
            <div className="text-[10px] uppercase tracking-wider font-bold text-neutral-500">
              Histórico do paciente
            </div>
            <h2 className="text-lg font-bold text-neutral-900 truncate" title={query.data?.paciente.name || ''}>
              {query.isLoading ? 'Carregando...' : (query.data?.paciente.name || '—')}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-md hover:bg-neutral-100 text-neutral-500"
            aria-label="Fechar"
          >
            <X size={18} />
          </button>
        </header>

        {/* Body */}
        <div className="flex-1 overflow-y-auto">
          {query.isLoading && (
            <div className="flex items-center justify-center py-16 text-neutral-500 gap-2">
              <Loader2 className="animate-spin" size={18} /> Carregando histórico...
            </div>
          )}
          {query.isError && (
            <div className="m-5 bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-800 text-sm">
              Erro ao carregar histórico do paciente.
            </div>
          )}
          {query.data && (
            <>
              <PacienteHeader data={query.data.paciente} metricas={query.data.metricas} />
              <ConsultasSection data={query.data.consultas} />
              <OrcamentosSection data={query.data.orcamentos} />
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Cabeçalho com identificação + métricas ───────────────────

function PacienteHeader({
  data, metricas,
}: {
  data: import('@/types/analise').PacienteDetalhe
  metricas: import('@/types/analise').PacienteMetricas
}) {
  const meta = BUCKET_META[data.bucket] || BUCKET_META.sem_visita
  const generoLabel = data.gender === 'F' ? 'Feminino' : data.gender === 'M' ? 'Masculino' : null
  const diasSemVisitaTxt = data.days_since_last_seen === null
    ? '—'
    : data.days_since_last_seen <= 0
      ? 'visita futura agendada'
      : `${data.days_since_last_seen}d sem visita`

  return (
    <section className="px-5 py-4 border-b border-neutral-200">
      {/* Linha 1: identificação */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[12px] text-neutral-700 mb-3">
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.bg} ${meta.text}`}>
          {meta.label}
        </span>
        {data.mobile_phone && (
          <span className="flex items-center gap-1 tabular-nums">
            <Phone size={12} className="text-neutral-500" /> {data.mobile_phone}
          </span>
        )}
        {data.email && (
          <span className="flex items-center gap-1 truncate max-w-[220px]" title={data.email}>
            <Mail size={12} className="text-neutral-500" /> {data.email}
          </span>
        )}
        {generoLabel && (
          <span className="flex items-center gap-1">
            <User size={12} className="text-neutral-500" /> {generoLabel}
          </span>
        )}
        {data.age !== null && (
          <span className="flex items-center gap-1 tabular-nums">
            <Calendar size={12} className="text-neutral-500" /> {data.age} anos
          </span>
        )}
      </div>

      {/* Linha 2: métricas-síntese em mini-cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <MiniMetric
          icon={<Crown size={13} className="text-amber-600" />}
          label="LTV"
          value={fmtBRL(metricas.ltv, true)}
          sub={`${metricas.qtd_pagamentos} pagamentos`}
        />
        <MiniMetric
          icon={<HeartPulse size={13} className="text-emerald-600" />}
          label="Consultas"
          value={fmtNum(metricas.qtd_consultas)}
          sub={`${metricas.qtd_consultas_efetivas} efetivas`}
        />
        <MiniMetric
          icon={<FileText size={13} className="text-blue-600" />}
          label="Orçamentos"
          value={fmtNum(metricas.qtd_orcamentos)}
          sub={`${metricas.qtd_orcamentos_aprovados} aprovados`}
        />
        <MiniMetric
          icon={<Clock size={13} className="text-rose-600" />}
          label="Pendente"
          value={metricas.valor_orcado_pendente > 0 ? fmtBRL(metricas.valor_orcado_pendente, true) : '—'}
          sub={diasSemVisitaTxt}
        />
      </div>

      {/* Linha 3: rastros temporais */}
      <div className="mt-3 pt-3 border-t border-neutral-100 flex flex-wrap gap-x-4 gap-y-1 text-[10.5px] text-neutral-500">
        {data.first_seen_at && (
          <span>1ª visita: <strong className="text-neutral-700">{fmtMonthYear(data.first_seen_at)}</strong></span>
        )}
        {data.last_seen_at && (
          <span>Última visita: <strong className="text-neutral-700">{fmtDate(data.last_seen_at)}</strong></span>
        )}
        {metricas.ticket_medio_orcamento > 0 && (
          <span>Ticket médio (aprovados): <strong className="text-neutral-700">{fmtBRL(metricas.ticket_medio_orcamento, true)}</strong></span>
        )}
      </div>
    </section>
  )
}

function MiniMetric({
  icon, label, value, sub,
}: { icon: React.ReactNode; label: string; value: string; sub?: string }) {
  return (
    <div className="bg-neutral-50 rounded-md px-3 py-2">
      <div className="flex items-center gap-1.5 mb-0.5">
        {icon}
        <span className="text-[10px] uppercase tracking-wider font-semibold text-neutral-500">
          {label}
        </span>
      </div>
      <div className="text-[15px] font-bold tabular-nums text-neutral-900">{value}</div>
      {sub && <div className="text-[10px] text-neutral-500 truncate" title={sub}>{sub}</div>}
    </div>
  )
}

// ── Histórico de consultas ────────────────────────────────────

function ConsultasSection({ data }: { data: PacienteHistoricoConsulta[] }) {
  return (
    <section className="px-5 py-4 border-b border-neutral-200">
      <div className="flex items-center gap-2 mb-2">
        <Calendar size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Histórico de consultas — top {data.length}
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-4 text-center">Sem consultas registradas.</div>
      ) : (
        <div className="bg-neutral-50 rounded-md overflow-hidden">
          <table className="w-full text-[11.5px]">
            <thead className="text-[10px] uppercase tracking-wider text-neutral-500 border-b border-neutral-200 bg-white">
              <tr>
                <th className="px-3 py-2 text-left">Data</th>
                <th className="px-3 py-2 text-left">Profissional</th>
                <th className="px-3 py-2 text-left">Categoria</th>
                <th className="px-3 py-2 text-center">Desfecho</th>
              </tr>
            </thead>
            <tbody>
              {data.map((c, i) => {
                const meta = DESF_META[c.desfecho] || DESF_META.outro
                return (
                  <tr key={c.appointment_external_id} className={i % 2 ? 'bg-white' : ''}>
                    <td className="px-3 py-1.5 tabular-nums text-neutral-600 whitespace-nowrap">
                      {fmtDate(c.date)}
                    </td>
                    <td className="px-3 py-1.5 truncate max-w-[140px] text-neutral-700" title={c.professional_name || ''}>
                      {c.professional_name || <span className="text-neutral-400">—</span>}
                    </td>
                    <td className="px-3 py-1.5 truncate max-w-[180px] text-neutral-700" title={c.category || ''}>
                      {c.category || <span className="text-neutral-400">—</span>}
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.bg} ${meta.text}`}>
                        {meta.icon} {meta.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

// ── Histórico de orçamentos ──────────────────────────────────

function OrcamentosSection({ data }: { data: PacienteHistoricoOrcamento[] }) {
  return (
    <section className="px-5 py-4">
      <div className="flex items-center gap-2 mb-2">
        <FileText size={14} className="text-neutral-600" />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          Histórico de orçamentos — top {data.length}
        </span>
      </div>
      {data.length === 0 ? (
        <div className="text-sm text-neutral-400 py-4 text-center">Sem orçamentos registrados.</div>
      ) : (
        <div className="bg-neutral-50 rounded-md overflow-hidden">
          <table className="w-full text-[11.5px]">
            <thead className="text-[10px] uppercase tracking-wider text-neutral-500 border-b border-neutral-200 bg-white">
              <tr>
                <th className="px-3 py-2 text-left">Data</th>
                <th className="px-3 py-2 text-left">Profissional</th>
                <th className="px-3 py-2 text-right">Valor</th>
                <th className="px-3 py-2 text-center">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.map((o, i) => {
                const meta = STATUS_META[o.status] || { label: o.status, bg: 'bg-neutral-100', text: 'text-neutral-600' }
                return (
                  <tr key={o.treatment_external_id} className={i % 2 ? 'bg-white' : ''}>
                    <td className="px-3 py-1.5 tabular-nums text-neutral-600 whitespace-nowrap">
                      {fmtDate(o.estimate_date)}
                    </td>
                    <td className="px-3 py-1.5 truncate max-w-[160px] text-neutral-700" title={o.professional_name || ''}>
                      {o.professional_name || <span className="text-neutral-400">—</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right font-bold tabular-nums text-neutral-900">
                      {fmtBRL(o.amount, true)}
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <span className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-bold ${meta.bg} ${meta.text}`}>
                        {meta.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
