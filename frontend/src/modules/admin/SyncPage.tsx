import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { syncService } from '@/services/sync.service'
import {
  ENTITY_LABELS,
  STATIC_ENTITIES,
  TRANSACTIONAL_ENTITIES,
  type Checkpoint,
  type SyncEntity,
  type SyncJob,
} from '@/types/sync'

const MONTHS_SHORT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

const HEATMAP_ROWS: SyncEntity[] = [...TRANSACTIONAL_ENTITIES, 'kpis_monthly']

const fmtDate = (iso: string | null): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const fmtNum = (n: number | null | undefined): string =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)

export default function SyncPage() {
  const qc = useQueryClient()
  const today = new Date()
  const [year, setYear] = useState<number>(today.getFullYear())
  const yearOptions = useMemo(() => {
    const start = 2019
    const end = today.getFullYear()
    return Array.from({ length: end - start + 1 }, (_, i) => end - i)
  }, [today])

  const checkpointsQ = useQuery({
    queryKey: ['sync', 'checkpoints'],
    queryFn: syncService.checkpoints,
    refetchInterval: 5_000,
  })
  const jobsQ = useQuery({
    queryKey: ['sync', 'jobs'],
    queryFn: () => syncService.jobs(50),
    refetchInterval: 5_000,
  })

  const checkpointsByEntity = useMemo(() => {
    const map: Partial<Record<SyncEntity, Checkpoint>> = {}
    for (const c of checkpointsQ.data || []) map[c.entity] = c
    return map
  }, [checkpointsQ.data])

  // Map (entity, year, month) → último job, pra colorir o heatmap
  const jobsByCell = useMemo(() => {
    const map = new Map<string, SyncJob>()
    for (const j of jobsQ.data || []) {
      if (!j.period_from) continue
      const d = new Date(j.period_from + 'T00:00:00')
      const key = `${j.entity}-${d.getFullYear()}-${d.getMonth() + 1}`
      // só guarda o mais recente (jobs já vem ordenado desc por created_at)
      if (!map.has(key)) map.set(key, j)
    }
    return map
  }, [jobsQ.data])

  // Mutations -----
  const invalidateAll = () => {
    qc.invalidateQueries({ queryKey: ['sync'] })
  }

  const staticAllMut = useMutation({
    mutationFn: () => syncService.static(),
    onSuccess: invalidateAll,
  })
  const txEntityMut = useMutation({
    mutationFn: (vars: { entity: SyncEntity; year: number; month: number }) =>
      syncService.transactional(vars.entity, vars.year, vars.month),
    onSuccess: invalidateAll,
  })
  const txMonthMut = useMutation({
    mutationFn: (vars: { year: number; month: number }) =>
      syncService.transactionalBatch(vars.year, vars.month),
    onSuccess: invalidateAll,
  })
  const kpisMut = useMutation({
    mutationFn: (vars: { year: number; month: number }) =>
      syncService.kpisMonthly(vars.year, vars.month),
    onSuccess: invalidateAll,
  })

  const isAnyRunning = staticAllMut.isPending || txEntityMut.isPending || txMonthMut.isPending || kpisMut.isPending

  // Totais top
  const totalStatic = STATIC_ENTITIES.reduce(
    (acc, e) => acc + (checkpointsByEntity[e]?.total_records || 0),
    0,
  )
  const totalTransactional = TRANSACTIONAL_ENTITIES.reduce(
    (acc, e) => acc + (checkpointsByEntity[e]?.total_records || 0),
    0,
  )
  const lastSyncAt = (checkpointsQ.data || [])
    .map((c) => c.last_synced_at)
    .filter(Boolean)
    .sort()
    .pop() as string | undefined

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="border-b bg-white px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div>
          <Link to="/" className="text-xs text-neutral-500 hover:text-primary-700">← voltar</Link>
          <h1 className="text-lg font-semibold text-neutral-900">Sincronização Clinicorp</h1>
        </div>
        <div className="text-xs text-neutral-500">
          {checkpointsQ.isFetching ? 'atualizando…' : `Atualiza a cada 5s`}
        </div>
      </header>

      <main className="px-6 py-6 max-w-7xl mx-auto space-y-6">
        {/* Status overview */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <KpiCard label="Cadastros estáticos" value={fmtNum(totalStatic)} sub={`${STATIC_ENTITIES.length} entidades`} />
          <KpiCard label="Mensal · registros" value={fmtNum(totalTransactional)} sub={`${TRANSACTIONAL_ENTITIES.length} entidades`} />
          <KpiCard label="Último sync" value={fmtDate(lastSyncAt || null)} sub="qualquer entidade" />
          <KpiCard label="Em execução" value={isAnyRunning ? 'Sim' : 'Não'} sub={isAnyRunning ? 'aguarde…' : 'pronto'} accent={isAnyRunning ? 'warning' : 'success'} />
        </section>

        {/* Cadastros estáticos */}
        <section className="bg-white border rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <h2 className="text-sm font-semibold text-neutral-900">Cadastros estáticos</h2>
            <button
              onClick={() => staticAllMut.mutate()}
              disabled={isAnyRunning}
              className="text-xs px-3 py-1.5 rounded bg-primary-700 text-white hover:bg-primary-800 disabled:opacity-50"
            >
              {staticAllMut.isPending ? 'Sincronizando…' : 'Sincronizar todos'}
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-xs text-neutral-600">
              <tr>
                <th className="text-left px-4 py-2 font-medium">Entidade</th>
                <th className="text-right px-4 py-2 font-medium">Total</th>
                <th className="text-left px-4 py-2 font-medium">Último sync</th>
                <th className="text-left px-4 py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {STATIC_ENTITIES.map((e) => {
                const cp = checkpointsByEntity[e]
                return (
                  <tr key={e} className="border-t">
                    <td className="px-4 py-2 text-neutral-800">{ENTITY_LABELS[e]} <span className="text-xs text-neutral-400 ml-1">{e}</span></td>
                    <td className="px-4 py-2 text-right tabular-nums text-neutral-700">{fmtNum(cp?.total_records || 0)}</td>
                    <td className="px-4 py-2 text-neutral-500 text-xs">{fmtDate(cp?.last_synced_at || null)}</td>
                    <td className="px-4 py-2"><StatusBadge status={cp?.status || 'idle'} /></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </section>

        {/* Heatmap mensal */}
        <section className="bg-white border rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b">
            <h2 className="text-sm font-semibold text-neutral-900">Sincronização mensal</h2>
            <div className="flex items-center gap-2">
              <select
                value={year}
                onChange={(e) => setYear(parseInt(e.target.value, 10))}
                className="text-xs border rounded px-2 py-1"
              >
                {yearOptions.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-neutral-50 text-neutral-600">
                <tr>
                  <th className="text-left px-4 py-2 font-medium sticky left-0 bg-neutral-50 z-10">Entidade</th>
                  {MONTHS_SHORT.map((m, idx) => {
                    const monthNum = idx + 1
                    const isFuture = year === today.getFullYear() && monthNum > today.getMonth() + 1
                    return (
                      <th key={m} className="px-1 py-2 font-medium text-center">
                        <button
                          onClick={() => txMonthMut.mutate({ year, month: monthNum })}
                          disabled={isFuture || isAnyRunning}
                          title={isFuture ? 'mês futuro' : `Sincronizar ${m}/${year} (todas as entidades)`}
                          className="px-1 py-0.5 rounded hover:bg-primary-50 disabled:opacity-30 disabled:cursor-not-allowed"
                        >
                          {m}
                        </button>
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {HEATMAP_ROWS.map((entity) => (
                  <tr key={entity} className="border-t">
                    <td className="px-4 py-2 sticky left-0 bg-white z-10 whitespace-nowrap">
                      <div className="text-neutral-800">{ENTITY_LABELS[entity]}</div>
                      <div className="text-[10px] text-neutral-400">{entity}</div>
                    </td>
                    {MONTHS_SHORT.map((_, idx) => {
                      const month = idx + 1
                      const isFuture = year === today.getFullYear() && month > today.getMonth() + 1
                      const job = jobsByCell.get(`${entity}-${year}-${month}`)
                      return (
                        <td key={month} className="p-1">
                          <HeatmapCell
                            entity={entity}
                            year={year}
                            month={month}
                            job={job}
                            disabled={isFuture || isAnyRunning}
                            onClick={() => {
                              if (entity === 'kpis_monthly') kpisMut.mutate({ year, month })
                              else txEntityMut.mutate({ entity, year, month })
                            }}
                          />
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Log de execuções */}
        <section className="bg-white border rounded-lg overflow-hidden">
          <div className="px-4 py-3 border-b">
            <h2 className="text-sm font-semibold text-neutral-900">Últimas execuções</h2>
          </div>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="bg-neutral-50 text-neutral-600 sticky top-0">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">#</th>
                  <th className="text-left px-4 py-2 font-medium">Entidade</th>
                  <th className="text-left px-4 py-2 font-medium">Período</th>
                  <th className="text-left px-4 py-2 font-medium">Status</th>
                  <th className="text-right px-4 py-2 font-medium">Fetched</th>
                  <th className="text-right px-4 py-2 font-medium">Inserted</th>
                  <th className="text-right px-4 py-2 font-medium">Updated</th>
                  <th className="text-right px-4 py-2 font-medium">Duração</th>
                  <th className="text-left px-4 py-2 font-medium">Iniciado</th>
                  <th className="text-left px-4 py-2 font-medium">Erro</th>
                </tr>
              </thead>
              <tbody>
                {(jobsQ.data || []).map((j) => (
                  <tr key={j.id} className="border-t">
                    <td className="px-4 py-1.5 text-neutral-500 tabular-nums">#{j.id}</td>
                    <td className="px-4 py-1.5 text-neutral-800">{j.entity}</td>
                    <td className="px-4 py-1.5 text-neutral-600 tabular-nums">{j.period_from ? `${j.period_from} → ${j.period_to}` : '—'}</td>
                    <td className="px-4 py-1.5"><StatusBadge status={j.status} /></td>
                    <td className="px-4 py-1.5 text-right tabular-nums">{fmtNum(j.records_fetched)}</td>
                    <td className="px-4 py-1.5 text-right tabular-nums">{fmtNum(j.records_inserted)}</td>
                    <td className="px-4 py-1.5 text-right tabular-nums">{fmtNum(j.records_updated)}</td>
                    <td className="px-4 py-1.5 text-right tabular-nums">{j.duration_ms != null ? `${j.duration_ms}ms` : '—'}</td>
                    <td className="px-4 py-1.5 text-neutral-500">{fmtDate(j.started_at)}</td>
                    <td className="px-4 py-1.5 text-error-text max-w-xs truncate" title={j.error_message || ''}>{j.error_message || '—'}</td>
                  </tr>
                ))}
                {(jobsQ.data || []).length === 0 && (
                  <tr><td colSpan={10} className="px-4 py-6 text-center text-neutral-400">Nenhuma execução ainda.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  )
}

// ─── helpers visuais ─────────────────────────────────────────────

function KpiCard({ label, value, sub, accent = 'neutral' }: {
  label: string; value: string; sub?: string; accent?: 'neutral' | 'warning' | 'success'
}) {
  const accentClasses = {
    neutral: 'border-neutral-200',
    warning: 'border-warning-border bg-warning-bg',
    success: 'border-success-border',
  }[accent]
  return (
    <div className={`bg-white border ${accentClasses} rounded-lg p-3`}>
      <div className="text-[10px] uppercase tracking-wide text-neutral-500 font-medium">{label}</div>
      <div className="mt-1 text-base font-semibold text-neutral-900 tabular-nums">{value}</div>
      {sub && <div className="text-[11px] text-neutral-400 mt-0.5">{sub}</div>}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { bg: string; text: string; label: string }> = {
    idle:    { bg: 'bg-neutral-100',  text: 'text-neutral-600', label: 'idle' },
    pending: { bg: 'bg-info-bg',      text: 'text-info-text',    label: 'pendente' },
    running: { bg: 'bg-warning-bg',   text: 'text-warning-text', label: 'rodando' },
    success: { bg: 'bg-success-bg',   text: 'text-success-text', label: 'ok' },
    error:   { bg: 'bg-error-bg',     text: 'text-error-text',   label: 'erro' },
  }
  const s = map[status] || map.idle
  return <span className={`text-[10px] px-2 py-0.5 rounded ${s.bg} ${s.text} font-medium`}>{s.label}</span>
}

function HeatmapCell({
  job, disabled, onClick,
}: {
  entity: SyncEntity; year: number; month: number;
  job: SyncJob | undefined; disabled: boolean; onClick: () => void;
}) {
  const records = (job?.records_inserted || 0) + (job?.records_updated || 0)

  let bg = 'bg-neutral-100 hover:bg-neutral-200 text-neutral-400'
  let label = '·'
  if (disabled && !job) {
    bg = 'bg-transparent text-neutral-300 cursor-not-allowed'
    label = ''
  } else if (job?.status === 'success') {
    if (records === 0) {
      bg = 'bg-neutral-100 hover:bg-neutral-200 text-neutral-500'
      label = '0'
    } else {
      bg = 'bg-success-bg hover:bg-green-100 text-success-text border border-success-border'
      label = records >= 1000 ? `${(records / 1000).toFixed(1)}k` : String(records)
    }
  } else if (job?.status === 'error') {
    bg = 'bg-error-bg hover:bg-red-100 text-error-text border border-error-border'
    label = '!'
  } else if (job?.status === 'running') {
    bg = 'bg-warning-bg text-warning-text border border-warning-border animate-pulse'
    label = '⏳'
  }

  const tooltip = job
    ? `${job.entity} ${job.period_from} → ${job.period_to}\n${job.status} · ${fmtNum(job.records_fetched)} fetched · ${job.records_inserted}+ ${job.records_updated}~ · ${job.duration_ms}ms${job.error_message ? '\n' + job.error_message : ''}`
    : 'clique para sincronizar'

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={tooltip}
      className={`w-full min-w-[44px] h-7 rounded text-[11px] font-medium tabular-nums transition ${bg} ${disabled ? 'cursor-not-allowed' : 'cursor-pointer'}`}
    >
      {label}
    </button>
  )
}
