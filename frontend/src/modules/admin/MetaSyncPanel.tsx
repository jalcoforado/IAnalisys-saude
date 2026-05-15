/**
 * Painel de sincronização Meta — aba "Meta" da página /admin/sync.
 *
 * Mesmo visual dos outros painéis (Clinicorp/Conta Azul):
 *   - sections brancas com border + header em cinza claro
 *   - tabela "Últimas execuções" idêntica (reusa /sync/jobs?source=meta)
 *
 * Diferença estrutural vs CC/CA: Meta não tem heatmap mensal (são snapshots
 * diários ou listas paginadas). Em vez do grid mês-x-entidade, o painel
 * mostra 5 cards (1 por entidade) com botão "Sincronizar agora".
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Calendar, Sparkles, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'

import { metaService } from '@/services/meta.service'
import { syncService } from '@/services/sync.service'
import type {
  MetaSyncEntity,
  MetaSyncEntityResult,
  MetaSyncAllResult,
} from '@/types/meta'
import type { SyncJob } from '@/types/sync'

const fmtDate = (iso: string | null): string => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}
const fmtNum = (n: number | null | undefined): string =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)


interface EntityDef {
  key: MetaSyncEntity
  label: string
  description: string
  pending?: boolean
  pendingReason?: string
}

const ENTITIES: EntityDef[] = [
  { key: 'ig_profile', label: 'Instagram — Perfil',
    description: 'Snapshot diário · seguidores, posts, bio' },
  { key: 'ig_media', label: 'Instagram — Posts',
    description: 'Lista de mídias · header (caption, permalink, media_url)' },
  { key: 'ig_post_insights', label: 'Instagram — Insights por post',
    description: 'Reach, saved, likes, comments, shares (lifetime)' },
  { key: 'ig_account_insights', label: 'Instagram — Insights da conta',
    description: 'Alcance e ganho de seguidores por dia (últimos 30d)' },
  { key: 'ig_comments', label: 'Instagram — Comentários',
    description: 'Comentários (header + replies) dos posts recentes — insumo pra classificação IA' },
  { key: 'fb_page', label: 'Facebook — Página',
    description: 'Snapshot diário · fans, info, contato' },
  { key: 'fb_posts', label: 'Facebook — Posts',
    description: 'Posts publicados · header' },
  { key: 'fb_post_insights', label: 'Facebook — Insights por post',
    description: 'Impressões, cliques, reações por post (lifetime)' },
  { key: 'fb_page_insights', label: 'Facebook — Insights da página',
    description: 'Impressões, engajamento, views por dia (últimos 30d)' },
  { key: 'pixel', label: 'Pixel',
    description: 'Detalhes + último disparo (o sync grava o status; pendências do pixel aparecem em /marketing/visao-geral)' },
]


export function MetaSyncPanel() {
  const qc = useQueryClient()
  const statusQ = useQuery({ queryKey: ['meta', 'status'], queryFn: metaService.status })
  const jobsQ = useQuery({
    queryKey: ['sync', 'meta', 'jobs', 'log'],
    queryFn: () => syncService.jobs(50, undefined, undefined, 'meta' as any),
    refetchInterval: 5_000,
  })

  const isConnected = !!statusQ.data?.connected
  const hasRecord = !!statusQ.data?.app_id

  const syncAllMut = useMutation({
    mutationFn: metaService.syncAll,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meta', 'status'] })
      qc.invalidateQueries({ queryKey: ['sync', 'meta'] })
    },
  })

  const runAllMut = useMutation({
    mutationFn: metaService.runAll,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meta'] })
      qc.invalidateQueries({ queryKey: ['sync', 'meta'] })
    },
  })

  const schedulerQ = useQuery({
    queryKey: ['meta', 'scheduler', 'status'],
    queryFn: metaService.schedulerStatus,
    refetchInterval: 60_000,
  })

  return (
    <div className="space-y-4">
      <StatusBanner connected={isConnected} hasRecord={hasRecord} status={statusQ.data} />

      {/* Scheduler + ação manual completa */}
      <SchedulerCard
        scheduler={schedulerQ.data}
        onRunAll={() => runAllMut.mutate()}
        runState={{
          isPending: runAllMut.isPending,
          data: runAllMut.data,
          isError: runAllMut.isError,
          error: runAllMut.error,
        }}
        disabled={!isConnected}
      />

      {/* Sync all + grid de entidades */}
      <section className="bg-white border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-neutral-900">Entidades Meta</h2>
            <p className="text-xs text-neutral-500 mt-0.5">
              Cada card sincroniza uma fonte específica. Use “Sincronizar tudo” pra rodar as 10 em sequência (sem classificar comentários).
            </p>
          </div>
          <button
            onClick={() => syncAllMut.mutate()}
            disabled={!isConnected || syncAllMut.isPending}
            className="text-xs bg-primary-700 hover:bg-primary-800 disabled:bg-neutral-300 text-white font-medium px-3 py-1.5 rounded"
          >
            {syncAllMut.isPending ? 'Sincronizando…' : 'Sincronizar tudo'}
          </button>
        </div>

        <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {ENTITIES.map((e) => (
            <EntityCard key={e.key} entity={e} connected={isConnected} />
          ))}
        </div>

        {syncAllMut.data && (
          <div className="border-t bg-neutral-50 p-4">
            <SyncAllResult result={syncAllMut.data} />
          </div>
        )}
      </section>

      {/* Log de execuções (mesmo padrão CC/CA) */}
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
                <th className="text-left px-4 py-2 font-medium">Status</th>
                <th className="text-right px-4 py-2 font-medium">Fetched</th>
                <th className="text-right px-4 py-2 font-medium">Inserted</th>
                <th className="text-right px-4 py-2 font-medium">Duração</th>
                <th className="text-left px-4 py-2 font-medium">Iniciado</th>
                <th className="text-left px-4 py-2 font-medium">Erro</th>
              </tr>
            </thead>
            <tbody>
              {(jobsQ.data || []).map((j: SyncJob) => (
                <tr key={j.id} className="border-t">
                  <td className="px-4 py-1.5 text-neutral-500 tabular-nums">#{j.id}</td>
                  <td className="px-4 py-1.5 text-neutral-800">{j.entity}</td>
                  <td className="px-4 py-1.5"><StatusBadge status={j.status} /></td>
                  <td className="px-4 py-1.5 text-right tabular-nums">{fmtNum(j.records_fetched)}</td>
                  <td className="px-4 py-1.5 text-right tabular-nums">{fmtNum(j.records_inserted)}</td>
                  <td className="px-4 py-1.5 text-right tabular-nums">{j.duration_ms != null ? `${j.duration_ms}ms` : '—'}</td>
                  <td className="px-4 py-1.5 text-neutral-500">{fmtDate(j.started_at)}</td>
                  <td className="px-4 py-1.5 text-error-text max-w-xs truncate" title={j.error_message || ''}>{j.error_message || '—'}</td>
                </tr>
              ))}
              {(jobsQ.data || []).length === 0 && (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-neutral-400">
                  Nenhuma execução ainda.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Sub-componentes
// ─────────────────────────────────────────────────────────────────

function StatusBanner({
  connected, hasRecord, status,
}: { connected: boolean; hasRecord: boolean; status: any }) {
  if (connected) {
    const pieces: string[] = []
    if (status?.business_name) pieces.push(status.business_name)
    if (status?.fb_page_name) pieces.push(status.fb_page_name)
    if (status?.ig_username) pieces.push(`@${status.ig_username}`)
    return (
      <div className="bg-success-bg border border-success-border rounded-lg px-4 py-2.5 flex items-center justify-between gap-3 text-sm">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-2 h-2 rounded-full bg-success-text shrink-0" aria-hidden />
          <div className="truncate">
            <span className="font-medium text-success-text">Meta conectado:</span>{' '}
            <span className="text-neutral-800">{pieces.join(' · ') || '—'}</span>
            {status?.token_validated_at && (
              <span className="text-neutral-500 ml-2 text-xs">
                validado {fmtDate(status.token_validated_at)}
              </span>
            )}
          </div>
        </div>
        <Link to="/empresa/meta-config" className="text-xs text-neutral-600 hover:text-neutral-900 inline-flex items-center gap-1 shrink-0">
          Editar <ArrowRight size={12} />
        </Link>
      </div>
    )
  }
  return (
    <div className="bg-warning-bg border border-warning-border rounded-lg px-4 py-2.5 flex items-center justify-between gap-3 text-sm">
      <div className="flex items-center gap-2 min-w-0">
        <span className="w-2 h-2 rounded-full bg-warning-text shrink-0" aria-hidden />
        <div className="truncate">
          <span className="font-medium text-warning-text">
            {hasRecord ? 'Token cadastrado mas não validado.' : 'Meta não configurado.'}
          </span>{' '}
          <span className="text-neutral-700">
            {hasRecord ? 'Valide antes de sincronizar.' : 'Cadastre token + IDs em Configuração Meta.'}
          </span>
        </div>
      </div>
      <Link to="/empresa/meta-config" className="text-xs bg-white border border-warning-border text-warning-text px-3 py-1 rounded hover:bg-amber-50 inline-flex items-center gap-1 shrink-0">
        Configurar <ArrowRight size={12} />
      </Link>
    </div>
  )
}


function EntityCard({ entity, connected }: { entity: EntityDef; connected: boolean }) {
  const qc = useQueryClient()
  const mut = useMutation({
    mutationFn: () => metaService.syncEntity(entity.key),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meta', 'status'] })
      qc.invalidateQueries({ queryKey: ['sync', 'meta'] })
    },
  })

  const disabled = !connected || mut.isPending
  const errorMsg = mut.isError ? (mut.error as any)?.response?.data?.detail || String(mut.error) : null

  return (
    <div className="border rounded-lg p-3 bg-white hover:border-neutral-300 transition">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="text-sm font-medium text-neutral-800 truncate">{entity.label}</h4>
          <p className="text-[11px] text-neutral-500 mt-0.5">{entity.description}</p>
        </div>
        {entity.pending && (
          <span className="text-[10px] uppercase tracking-wider bg-warning-bg text-warning-text px-1.5 py-0.5 rounded shrink-0">
            TI pendente
          </span>
        )}
      </div>

      {entity.pending && entity.pendingReason && (
        <p className="text-[10px] text-neutral-500 mt-1 italic">{entity.pendingReason}</p>
      )}

      <div className="mt-3 flex items-center justify-between gap-2">
        <button
          onClick={() => mut.mutate()}
          disabled={disabled}
          className="text-xs bg-white border hover:bg-neutral-50 disabled:opacity-50 disabled:cursor-not-allowed text-neutral-700 px-2.5 py-1 rounded"
        >
          {mut.isPending ? 'Sincronizando…' : 'Sincronizar'}
        </button>
        {mut.data && (
          <span className="text-[11px] text-success-text tabular-nums">
            ✓ {mut.data.records} · #{mut.data.job_id}
          </span>
        )}
      </div>

      {errorMsg && (
        <p className="text-[11px] text-error-text mt-2 break-words">{errorMsg}</p>
      )}
    </div>
  )
}


function SyncAllResult({ result }: { result: MetaSyncAllResult }) {
  const okList = Object.entries(result.ok).filter(([, v]) => v != null) as [string, MetaSyncEntityResult][]
  const errList = Object.entries(result.errors) as [string, string][]
  return (
    <div className="space-y-1.5 text-xs">
      <div className="font-medium text-neutral-700">Último “Sincronizar tudo”</div>
      {okList.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <StatusBadge status="success" />
          <span className="font-mono text-neutral-600 w-28">{k}</span>
          <span className="text-neutral-700">{v.records} registro(s) · job #{v.job_id}</span>
        </div>
      ))}
      {errList.map(([k, v]) => (
        <div key={k} className="flex items-start gap-2">
          <StatusBadge status="error" />
          <span className="font-mono text-neutral-600 w-28 shrink-0">{k}</span>
          <span className="text-error-text break-words">{v}</span>
        </div>
      ))}
    </div>
  )
}


// ─── SchedulerCard ──────────────────────────────────────────────

interface SchedulerJob { id: string; name: string; next_run: string | null }
interface SchedulerStatus {
  running: boolean
  timezone?: string
  jobs: SchedulerJob[]
  server_time?: string
}

function SchedulerCard({
  scheduler,
  onRunAll,
  runState,
  disabled,
}: {
  scheduler?: SchedulerStatus
  onRunAll: () => void
  runState: { isPending: boolean; data: any; isError: boolean; error: unknown }
  disabled: boolean
}) {
  const fmtNext = (iso: string | null) => {
    if (!iso) return '—'
    const d = new Date(iso)
    return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  }
  return (
    <section className="bg-white border rounded-lg overflow-hidden">
      <div className="px-4 py-3 border-b flex items-center justify-between gap-3 flex-wrap">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-neutral-900 inline-flex items-center gap-2">
            <Calendar size={14} className="text-violet-600" />
            Agendamento automático
          </h2>
          <p className="text-xs text-neutral-500 mt-0.5">
            Roda toda madrugada quando a máquina está ligada. Se ficou off, executa 1× ao subir (grace de 1 dia).
          </p>
        </div>
        <button
          onClick={onRunAll}
          disabled={disabled || runState.isPending}
          className="text-xs bg-violet-600 hover:bg-violet-700 disabled:bg-neutral-300 text-white font-medium px-3 py-1.5 rounded inline-flex items-center gap-1.5"
        >
          <Zap size={12} />
          {runState.isPending ? 'Executando…' : 'Atualizar tudo agora'}
        </button>
      </div>

      <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        {scheduler?.jobs?.length ? (
          scheduler.jobs.map((j) => (
            <div key={j.id} className="border rounded-md p-3 bg-neutral-50/50">
              <div className="flex items-center gap-2 text-xs font-medium text-neutral-800">
                <Sparkles size={12} className="text-violet-500" />
                {j.name}
              </div>
              <div className="text-[11px] text-neutral-500 mt-2">
                Próxima execução: <span className="text-neutral-700 font-medium">{fmtNext(j.next_run)}</span>
              </div>
            </div>
          ))
        ) : (
          <div className="col-span-3 text-xs text-neutral-400 italic px-1 py-3">
            Scheduler desligado ou sem jobs configurados.
          </div>
        )}
      </div>

      {runState.data && (
        <div className="border-t bg-neutral-50 px-4 py-3 text-xs text-neutral-700 space-y-1">
          <div className="font-semibold text-neutral-800 mb-1">Execução completa:</div>
          <RunAllResultLine label="sync_all" payload={runState.data.sync_all} errorPayload={runState.data.sync_all_error} />
          <RunAllResultLine label="ig_comments" payload={runState.data.ig_comments} errorPayload={runState.data.ig_comments_error} />
          <RunAllResultLine label="classify" payload={runState.data.classify} errorPayload={runState.data.classify_error} />
        </div>
      )}
      {runState.isError && (
        <div className="border-t bg-error-bg px-4 py-2 text-xs text-error-text">
          Erro: {String((runState.error as any)?.response?.data?.detail || runState.error)}
        </div>
      )}
    </section>
  )
}

function RunAllResultLine({ label, payload, errorPayload }: { label: string; payload: any; errorPayload?: string }) {
  if (errorPayload) {
    return (
      <div className="flex items-start gap-2">
        <StatusBadge status="error" />
        <span className="font-mono text-neutral-600 w-24 shrink-0">{label}</span>
        <span className="text-error-text break-words">{errorPayload}</span>
      </div>
    )
  }
  if (!payload) return null
  // sync_all retorna { ok: {...}, errors: {...} }
  if (payload.ok) {
    const okCount = Object.keys(payload.ok).length
    const errCount = Object.keys(payload.errors || {}).length
    return (
      <div className="flex items-center gap-2">
        <StatusBadge status={errCount ? 'error' : 'success'} />
        <span className="font-mono text-neutral-600 w-24">{label}</span>
        <span className="text-neutral-700">{okCount} ok · {errCount} erro(s)</span>
      </div>
    )
  }
  // classify retorna { processed, fast_path, ia, errors }
  if (typeof payload.processed === 'number') {
    return (
      <div className="flex items-center gap-2">
        <StatusBadge status="success" />
        <span className="font-mono text-neutral-600 w-24">{label}</span>
        <span className="text-neutral-700">
          {payload.processed} processados (fast {payload.fast_path} · IA {payload.ia} · erros {payload.errors})
        </span>
      </div>
    )
  }
  // ig_comments retorna { entity, records, job_id }
  if (typeof payload.records === 'number') {
    return (
      <div className="flex items-center gap-2">
        <StatusBadge status="success" />
        <span className="font-mono text-neutral-600 w-24">{label}</span>
        <span className="text-neutral-700">{payload.records} comentários · job #{payload.job_id}</span>
      </div>
    )
  }
  return null
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
