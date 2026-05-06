import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { syncService } from '@/services/sync.service'
import { pipelineService, type RebuildPipelineResult } from '@/services/pipeline.service'
import {
  ENTITY_LABELS,
  type BatchResponse,
  type Checkpoint,
  type SyncEntity,
  type SyncJob,
  type SyncSource,
} from '@/types/sync'

const MONTHS_SHORT = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

const fmtDate = (iso: string | null): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const fmtNum = (n: number | null | undefined): string =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)


export interface SyncProviderConfig {
  source: SyncSource
  staticEntities: SyncEntity[]        // tabela "Cadastros estáticos"
  heatmapRows: SyncEntity[]           // linhas do heatmap mensal
  syncAllStatic: () => Promise<BatchResponse>
  syncMonth: (year: number, month: number) => Promise<BatchResponse>
  /** Sync individual de UMA entidade transacional. Opcional — Conta Azul não suporta. */
  syncEntityMonth?: (entity: SyncEntity, year: number, month: number) => Promise<SyncJob>
  /** Sync KPIs mensais (Clinicorp). Opcional. */
  syncKpisMonth?: (year: number, month: number) => Promise<SyncJob>
  /** Delta sync — atualiza alterações recentes em todas transacionais. Opcional (só CA). */
  syncAlteracoes?: (hoursBack: number) => Promise<BatchResponse>
  /** Enriquece pacientes via /patient/get (BirthDate, Email, CPF, Status). Só Clinicorp. */
  syncPatientsDetails?: () => Promise<SyncJob>
  /** Mostrar botão de rebuild CORE+ANALYTICS (só Clinicorp por enquanto). */
  showRebuildPipeline?: boolean
}


export function SyncProviderPanel({ config }: { config: SyncProviderConfig }) {
  const qc = useQueryClient()
  const today = new Date()
  const [year, setYear] = useState<number>(today.getFullYear())
  const yearOptions = useMemo(() => {
    const start = 2019
    const end = today.getFullYear()
    return Array.from({ length: end - start + 1 }, (_, i) => end - i)
  }, [today])

  const queryRoot = ['sync', config.source] as const

  const checkpointsQ = useQuery({
    queryKey: [...queryRoot, 'checkpoints'],
    queryFn: () => syncService.checkpoints(config.source),
    refetchInterval: 5_000,
  })
  const jobsQ = useQuery({
    queryKey: [...queryRoot, 'jobs', 'log'],
    queryFn: () => syncService.jobs(50, undefined, undefined, config.source),
    refetchInterval: 5_000,
  })
  const yearJobsQ = useQuery({
    queryKey: [...queryRoot, 'jobs', 'year', year],
    queryFn: () => syncService.jobs(500, undefined, year, config.source),
    refetchInterval: 5_000,
  })

  const checkpointsByEntity = useMemo(() => {
    const map: Partial<Record<SyncEntity, Checkpoint>> = {}
    for (const c of checkpointsQ.data || []) map[c.entity] = c
    return map
  }, [checkpointsQ.data])

  const jobsByCell = useMemo(() => {
    const map = new Map<string, SyncJob>()
    for (const j of yearJobsQ.data || []) {
      if (!j.period_from) continue
      const d = new Date(j.period_from + 'T00:00:00')
      const key = `${j.entity}-${d.getFullYear()}-${d.getMonth() + 1}`
      if (!map.has(key)) map.set(key, j)
    }
    return map
  }, [yearJobsQ.data])

  const invalidateAll = () => qc.invalidateQueries({ queryKey: queryRoot })

  const staticAllMut = useMutation({
    mutationFn: () => config.syncAllStatic(),
    onSuccess: invalidateAll,
  })
  const txMonthMut = useMutation({
    mutationFn: (vars: { year: number; month: number }) =>
      config.syncMonth(vars.year, vars.month),
    onSuccess: invalidateAll,
  })
  const txEntityMut = useMutation({
    mutationFn: (vars: { entity: SyncEntity; year: number; month: number }) =>
      config.syncEntityMonth!(vars.entity, vars.year, vars.month),
    onSuccess: invalidateAll,
  })
  const kpisMut = useMutation({
    mutationFn: (vars: { year: number; month: number }) =>
      config.syncKpisMonth!(vars.year, vars.month),
    onSuccess: invalidateAll,
  })
  const [alteracoesHours, setAlteracoesHours] = useState(24)
  const [lastAlteracoes, setLastAlteracoes] = useState<BatchResponse | null>(null)
  const alteracoesMut = useMutation({
    mutationFn: () => config.syncAlteracoes!(alteracoesHours),
    onSuccess: (data) => {
      setLastAlteracoes(data)
      invalidateAll()
    },
  })

  const [lastRebuild, setLastRebuild] = useState<RebuildPipelineResult | null>(null)
  const rebuildMut = useMutation({
    mutationFn: () => pipelineService.rebuildAll(),
    onSuccess: (data) => {
      setLastRebuild(data)
      invalidateAll()
    },
  })

  const [lastPatientsDetails, setLastPatientsDetails] = useState<SyncJob | null>(null)
  const patientsDetailsMut = useMutation({
    mutationFn: () => config.syncPatientsDetails!(),
    onSuccess: (data) => {
      setLastPatientsDetails(data)
      invalidateAll()
    },
  })

  const isAnyRunning =
    staticAllMut.isPending || txEntityMut.isPending || txMonthMut.isPending ||
    kpisMut.isPending || rebuildMut.isPending || alteracoesMut.isPending ||
    patientsDetailsMut.isPending

  const totalStatic = config.staticEntities.reduce(
    (acc, e) => acc + (checkpointsByEntity[e]?.total_records || 0), 0)
  const totalTx = config.heatmapRows.reduce(
    (acc, e) => acc + (checkpointsByEntity[e]?.total_records || 0), 0)
  const lastSyncAt = (checkpointsQ.data || [])
    .map((c) => c.last_synced_at).filter(Boolean).sort().pop() as string | undefined

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <div className="text-xs text-neutral-500">
          {checkpointsQ.isFetching ? 'atualizando…' : 'atualiza a cada 5s'}
        </div>
      </div>

      {/* Status overview */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <KpiCard label="Cadastros estáticos" value={fmtNum(totalStatic)} sub={`${config.staticEntities.length} entidades`} />
        <KpiCard label="Mensal · registros" value={fmtNum(totalTx)} sub={`${config.heatmapRows.length} entidades`} />
        <KpiCard label="Último sync" value={fmtDate(lastSyncAt || null)} sub="qualquer entidade" />
        <KpiCard label="Em execução" value={isAnyRunning ? 'Sim' : 'Não'} sub={isAnyRunning ? 'aguarde…' : 'pronto'} accent={isAnyRunning ? 'warning' : 'success'} />
      </section>

      {/* Delta sync (só CA por hora) */}
      {config.syncAlteracoes && (
        <section className="bg-gradient-to-r from-info-bg to-white border border-info-border rounded-lg p-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-[260px]">
              <h2 className="text-sm font-semibold text-neutral-900">Atualizar mudanças (delta sync)</h2>
              <p className="text-xs text-neutral-600 mt-0.5">
                Busca contas a receber/pagar alteradas no Conta Azul desde o intervalo selecionado.
                Pega lançamentos novos, baixas, edições — em qualquer mês de vencimento — com apenas
                2 chamadas à API. Use durante o dia em vez de re-sincronizar meses inteiros.
              </p>
              {lastAlteracoes && (
                <div className="mt-2 text-[11px] text-neutral-700 flex flex-wrap gap-3">
                  <span><strong className="text-success-text">✓ Último delta:</strong></span>
                  <span><strong>{fmtNum(lastAlteracoes.total_inserted)}</strong> inseridos</span>
                  <span><strong>{fmtNum(lastAlteracoes.total_updated)}</strong> atualizados</span>
                  {lastAlteracoes.total_errors > 0 && (
                    <span className="text-error-text"><strong>{lastAlteracoes.total_errors}</strong> erros</span>
                  )}
                </div>
              )}
              {alteracoesMut.isError && (
                <div className="mt-2 text-xs text-error-text">Erro ao rodar delta sync. Verifique os logs do backend.</div>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <select
                value={alteracoesHours}
                onChange={(e) => setAlteracoesHours(parseInt(e.target.value, 10))}
                disabled={isAnyRunning}
                className="text-xs border rounded px-2 py-2 bg-white"
              >
                <option value={1}>última 1h</option>
                <option value={6}>últimas 6h</option>
                <option value={24}>últimas 24h</option>
                <option value={72}>últimos 3 dias</option>
                <option value={168}>últimos 7 dias</option>
                <option value={720}>últimos 30 dias</option>
              </select>
              <button
                onClick={() => alteracoesMut.mutate()}
                disabled={isAnyRunning}
                className="text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm"
              >
                {alteracoesMut.isPending ? 'Atualizando…' : 'Atualizar mudanças'}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Detalhes dos pacientes (Clinicorp /patient/get) — sub-PR 18. Sync
           iterativa: 1 call por paciente. Pode demorar minutos. */}
      {config.syncPatientsDetails && (
        <section className="bg-gradient-to-r from-amber-50 to-white border border-amber-200 rounded-lg p-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-[260px]">
              <h2 className="text-sm font-semibold text-neutral-900">
                Detalhes dos pacientes
                <span className="ml-2 text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 align-middle">
                  Enriquecimento
                </span>
              </h2>
              <p className="text-xs text-neutral-600 mt-0.5">
                Busca dados completos de cada paciente via <code className="text-[11px] bg-neutral-100 px-1 rounded">/patient/get</code>:
                data de nascimento, e-mail, CPF e status. A Clinicorp não tem listagem em massa —
                é 1 chamada por paciente. Em bases grandes pode demorar alguns minutos.
                Idempotente — pode rodar quantas vezes quiser.
              </p>
              {lastPatientsDetails && (
                <div className="mt-2 text-[11px] text-neutral-700 flex flex-wrap gap-3">
                  <span>
                    <strong className={lastPatientsDetails.status === 'success' ? 'text-success-text' : lastPatientsDetails.status === 'error' ? 'text-error-text' : 'text-warning-text'}>
                      {lastPatientsDetails.status === 'success' ? '✓' : lastPatientsDetails.status === 'error' ? '✗' : '⚠'} Última execução:
                    </strong>
                    {' '}
                    {lastPatientsDetails.duration_ms != null ? `${(lastPatientsDetails.duration_ms / 1000).toFixed(1)}s` : '—'}
                  </span>
                  <span><strong>{fmtNum(lastPatientsDetails.records_fetched)}</strong> pacientes processados</span>
                  {(lastPatientsDetails.errors_count ?? 0) > 0 && (
                    <span className="text-error-text"><strong>{fmtNum(lastPatientsDetails.errors_count)}</strong> erros</span>
                  )}
                </div>
              )}
              {patientsDetailsMut.isError && (
                <div className="mt-2 text-xs text-error-text">Erro ao sincronizar. Verifique os logs do backend.</div>
              )}
              {patientsDetailsMut.isPending && (
                <div className="mt-2 text-xs text-warning-text italic">
                  ⏳ Sincronizando — não feche esta página até concluir.
                </div>
              )}
            </div>
            <button
              onClick={() => patientsDetailsMut.mutate()}
              disabled={isAnyRunning}
              className="text-xs px-4 py-2 rounded bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm shrink-0"
            >
              {patientsDetailsMut.isPending ? 'Sincronizando…' : 'Sincronizar pacientes'}
            </button>
          </div>
        </section>
      )}

      {/* Pipeline rebuild — global (cobre Clinicorp + Conta Azul). Aparece
           em ambas as abas pra quem entra direto numa fonte específica. */}
      {config.showRebuildPipeline && (
        <section className="bg-gradient-to-r from-primary-50 to-white border border-primary-100 rounded-lg p-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-[260px]">
              <h2 className="text-sm font-semibold text-neutral-900">Pipeline CORE + ANALYTICS</h2>
              <p className="text-xs text-neutral-600 mt-0.5">
                Após sincronizar dados novos no STAGING (Clinicorp e/ou Conta Azul), rode esse passo
                para atualizar as tabelas relacionais (CORE) e o star schema (ANALYTICS) que
                alimentam o dashboard. Cobre as duas fontes numa única execução, sequencial.
                Idempotente — pode rodar quantas vezes quiser.
              </p>
              {lastRebuild && (
                <div className="mt-2 text-[11px] text-neutral-700 flex flex-wrap gap-3">
                  <span><strong className="text-success-text">✓ Último rebuild:</strong> {(lastRebuild.duration_ms / 1000).toFixed(2)}s</span>
                  <span>Transform: <strong>{fmtNum(lastRebuild.transform.total_inserted)}</strong> inseridos · <strong>{fmtNum(lastRebuild.transform.total_updated)}</strong> atualizados</span>
                  <span>Analytics: <strong>{fmtNum(lastRebuild.analytics.total_inserted)}</strong> inseridos · <strong>{fmtNum(lastRebuild.analytics.total_updated)}</strong> atualizados</span>
                </div>
              )}
              {rebuildMut.isError && (
                <div className="mt-2 text-xs text-error-text">Erro ao reconstruir. Verifique os logs do backend.</div>
              )}
            </div>
            <button
              onClick={() => rebuildMut.mutate()}
              disabled={isAnyRunning}
              className="text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800 disabled:opacity-50 disabled:cursor-not-allowed font-medium shadow-sm shrink-0"
            >
              {rebuildMut.isPending ? 'Reconstruindo…' : 'Reconstruir CORE + ANALYTICS'}
            </button>
          </div>
        </section>
      )}

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
            {config.staticEntities.map((e) => {
              const cp = checkpointsByEntity[e]
              return (
                <tr key={e} className="border-t">
                  <td className="px-4 py-2 text-neutral-800">
                    {ENTITY_LABELS[e]}{' '}
                    <span className="text-xs text-neutral-400 ml-1">{e}</span>
                  </td>
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
          <select
            value={year}
            onChange={(e) => setYear(parseInt(e.target.value, 10))}
            className="text-xs border rounded px-2 py-1"
          >
            {yearOptions.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
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
              {config.heatmapRows.map((entity) => (
                <tr key={entity} className="border-t">
                  <td className="px-4 py-2 sticky left-0 bg-white z-10 whitespace-nowrap">
                    <div className="text-neutral-800">{ENTITY_LABELS[entity]}</div>
                    <div className="text-[10px] text-neutral-400">{entity}</div>
                  </td>
                  {MONTHS_SHORT.map((_, idx) => {
                    const month = idx + 1
                    const isFuture = year === today.getFullYear() && month > today.getMonth() + 1
                    const job = jobsByCell.get(`${entity}-${year}-${month}`)
                    // Conta Azul: só batch (clica no header do mês)
                    const canClickCell =
                      entity === 'kpis_monthly' ? !!config.syncKpisMonth :
                      !!config.syncEntityMonth
                    return (
                      <td key={month} className="p-1">
                        <HeatmapCell
                          job={job}
                          disabled={isFuture || isAnyRunning || !canClickCell}
                          onClick={() => {
                            if (entity === 'kpis_monthly' && config.syncKpisMonth) {
                              kpisMut.mutate({ year, month })
                            } else if (config.syncEntityMonth) {
                              txEntityMut.mutate({ entity, year, month })
                            }
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
        {!config.syncEntityMonth && (
          <div className="text-[11px] text-neutral-500 px-4 py-2 border-t">
            Para sincronizar, clique no <strong>mês</strong> no cabeçalho — vai disparar todas as entidades transacionais juntas.
          </div>
        )}
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

function HeatmapCell({ job, disabled, onClick }: {
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
