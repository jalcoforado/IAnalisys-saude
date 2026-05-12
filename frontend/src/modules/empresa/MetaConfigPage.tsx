import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Activity, AlertCircle, CheckCircle2, Camera, Globe, MessageSquare,
  Loader2, Save, Trash2, XCircle,
} from 'lucide-react'

import { metaService } from '@/services/meta.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import type {
  MetaStatus, MetaTokenInput, MetaValidation, MetaValidationCheck,
} from '@/types/meta'

const EMPTY: MetaTokenInput = {
  app_id: '',
  app_name: '',
  business_id: '',
  system_user_token: '',
  fb_page_id: '',
  ig_account_id: '',
  ad_account_id: '',
  pixel_id: '',
}

function fromStatus(s: MetaStatus | undefined): MetaTokenInput {
  if (!s) return EMPTY
  return {
    app_id: s.app_id || '',
    app_name: s.app_name || '',
    business_id: s.business_id || '',
    system_user_token: '',  // nunca preenchido — UI exige re-cole pra trocar
    fb_page_id: s.fb_page_id || '',
    ig_account_id: s.ig_account_id || '',
    ad_account_id: s.ad_account_id || '',
    pixel_id: s.pixel_id || '',
  }
}

export default function MetaConfigPage() {
  usePageTitle('Configuração Meta', 'Instagram + Facebook + Ads + Pixel', 'EMPRESA')
  const qc = useQueryClient()
  const statusQ = useQuery({ queryKey: ['meta', 'status'], queryFn: metaService.status })

  const [form, setForm] = useState<MetaTokenInput>(EMPTY)
  const [lastValidation, setLastValidation] = useState<MetaValidation | null>(null)

  useEffect(() => {
    if (statusQ.data) setForm(fromStatus(statusQ.data))
  }, [statusQ.data])

  const saveMut = useMutation({
    mutationFn: (payload: MetaTokenInput) => metaService.putToken(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meta', 'status'] })
      setLastValidation(null)
    },
  })

  const validateMut = useMutation({
    mutationFn: () => metaService.validate(),
    onSuccess: (data) => {
      setLastValidation(data)
      qc.invalidateQueries({ queryKey: ['meta', 'status'] })
    },
  })

  const disconnectMut = useMutation({
    mutationFn: () => metaService.disconnect(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['meta', 'status'] })
      setForm(EMPTY)
      setLastValidation(null)
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.app_id || !form.system_user_token) return
    saveMut.mutate(form)
  }

  if (statusQ.isLoading) {
    return (
      <PageContainer variant="narrow">
        <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
          Carregando…
        </div>
      </PageContainer>
    )
  }

  const status = statusQ.data
  const isConnected = !!status?.connected
  const hasRecord = !!status?.app_id

  return (
    <PageContainer variant="narrow" gap={6}>
      <PageHeader
        eyebrow="EMPRESA · INTEGRAÇÃO"
        title="Configuração Meta"
        subtitle="System User Token + IDs vinculados (IG · FB · Ads · Pixel)"
        icon={<Activity size={20} />}
      />

      <StatusBanner status={status} />

      <form onSubmit={handleSubmit} className="bg-white border rounded-xl p-6 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-neutral-800 flex items-center gap-2">
          <Globe size={16} /> Credenciais do App Meta
        </h3>

        <Row>
          <Field label="App ID *" required value={form.app_id}
                 onChange={(v) => setForm({ ...form, app_id: v })}
                 placeholder="ex.: 827516216650543" />
          <Field label="App Name" value={form.app_name || ''}
                 onChange={(v) => setForm({ ...form, app_name: v })}
                 placeholder="ex.: IANALISYS" />
        </Row>

        <Field label="System User Token *" required value={form.system_user_token}
               onChange={(v) => setForm({ ...form, system_user_token: v })}
               placeholder={hasRecord ? 'Token já cadastrado — cole novo só pra trocar' : 'EAALwnyIjqy8...'}
               textarea />

        <Field label="Business Manager ID" value={form.business_id || ''}
               onChange={(v) => setForm({ ...form, business_id: v })}
               placeholder="ex.: 1701440180159990" />

        <h3 className="text-sm font-semibold text-neutral-800 flex items-center gap-2 pt-4 border-t">
          <MessageSquare size={16} /> Página Facebook + Instagram vinculado
        </h3>
        <Row>
          <Field label="Facebook Page ID" value={form.fb_page_id || ''}
                 onChange={(v) => setForm({ ...form, fb_page_id: v })}
                 placeholder="ex.: 764771720299927" />
          <Field label="Instagram Account ID" value={form.ig_account_id || ''}
                 onChange={(v) => setForm({ ...form, ig_account_id: v })}
                 placeholder="(auto-descoberto via Page)" />
        </Row>

        <h3 className="text-sm font-semibold text-neutral-800 flex items-center gap-2 pt-4 border-t">
          <Camera size={16} /> Ads + Pixel
        </h3>
        <Row>
          <Field label="Ad Account ID" value={form.ad_account_id || ''}
                 onChange={(v) => setForm({ ...form, ad_account_id: v })}
                 placeholder="ex.: act_781047300441900" />
          <Field label="Pixel ID" value={form.pixel_id || ''}
                 onChange={(v) => setForm({ ...form, pixel_id: v })}
                 placeholder="ex.: 1369627670250088" />
        </Row>

        <div className="flex flex-wrap gap-3 pt-4 border-t">
          <button
            type="submit"
            disabled={saveMut.isPending || !form.app_id || !form.system_user_token}
            className="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-neutral-300 text-white text-sm font-medium px-4 py-2 rounded-lg transition"
          >
            {saveMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            Salvar
          </button>

          <button
            type="button"
            onClick={() => validateMut.mutate()}
            disabled={!hasRecord || validateMut.isPending}
            className="inline-flex items-center gap-2 bg-white border hover:bg-neutral-50 disabled:opacity-50 text-neutral-700 text-sm font-medium px-4 py-2 rounded-lg transition"
          >
            {validateMut.isPending ? <Loader2 size={16} className="animate-spin" /> : <Activity size={16} />}
            Validar via Graph API
          </button>

          {hasRecord && (
            <button
              type="button"
              onClick={() => {
                if (confirm('Remover toda a configuração Meta deste tenant?')) {
                  disconnectMut.mutate()
                }
              }}
              disabled={disconnectMut.isPending}
              className="inline-flex items-center gap-2 bg-white border border-red-200 hover:bg-red-50 text-red-600 text-sm font-medium px-4 py-2 rounded-lg transition ml-auto"
            >
              <Trash2 size={16} />
              Desconectar
            </button>
          )}
        </div>

        {saveMut.isError && (
          <div className="text-xs text-red-600">Erro ao salvar: {String(saveMut.error)}</div>
        )}
      </form>

      <ValidationPanel
        connected={isConnected}
        validation={lastValidation}
        loading={validateMut.isPending}
      />
    </PageContainer>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Sub-componentes
// ─────────────────────────────────────────────────────────────────────

function StatusBanner({ status }: { status: MetaStatus | undefined }) {
  if (!status || !status.app_id) {
    return (
      <div className="bg-neutral-50 border border-neutral-200 rounded-xl p-4 text-sm text-neutral-600 flex items-start gap-3">
        <AlertCircle size={18} className="text-neutral-400 mt-0.5" />
        <div>
          <strong>Nenhuma configuração Meta cadastrada.</strong>{' '}
          Preencha os campos abaixo com os dados do System User Token gerado no Business Manager.
        </div>
      </div>
    )
  }

  const bg = status.connected
    ? 'bg-green-50 border-green-200 text-green-800'
    : 'bg-amber-50 border-amber-200 text-amber-800'
  const icon = status.connected
    ? <CheckCircle2 size={18} className="text-green-600 mt-0.5" />
    : <AlertCircle size={18} className="text-amber-600 mt-0.5" />

  return (
    <div className={`border rounded-xl p-4 text-sm flex items-start gap-3 ${bg}`}>
      {icon}
      <div className="flex-1">
        <div className="font-semibold mb-1">
          {status.connected ? 'Conexão Meta ativa' : 'Token cadastrado, mas não validado'}
        </div>
        <div className="text-xs grid grid-cols-2 gap-x-6 gap-y-1 mt-2">
          {status.business_name && <Info label="Business" value={status.business_name} />}
          {status.fb_page_name && <Info label="Facebook Page" value={status.fb_page_name} />}
          {status.ig_username && <Info label="Instagram" value={`@${status.ig_username}`} />}
          {status.system_user_name && <Info label="System User" value={status.system_user_name} />}
          {status.token_validated_at && (
            <Info label="Validado em" value={new Date(status.token_validated_at).toLocaleString('pt-BR')} />
          )}
          {status.pixel_last_fired_at && (
            <Info label="Pixel último disparo" value={new Date(status.pixel_last_fired_at).toLocaleString('pt-BR')} />
          )}
        </div>
      </div>
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-neutral-500">{label}:</span>{' '}
      <span className="font-medium">{value}</span>
    </div>
  )
}

function ValidationPanel({
  connected, validation, loading,
}: { connected: boolean; validation: MetaValidation | null; loading: boolean }) {
  if (!validation && !loading) return null

  return (
    <div className="bg-white border rounded-xl p-6 shadow-sm space-y-3">
      <h3 className="text-sm font-semibold text-neutral-800 flex items-center gap-2">
        <Activity size={16} />
        Diagnóstico
        {loading && <Loader2 size={14} className="animate-spin text-neutral-400" />}
      </h3>

      {validation && validation.scopes.length > 0 && (
        <div className="text-xs">
          <span className="text-neutral-500">Permissões ativas:</span>{' '}
          <div className="flex flex-wrap gap-1 mt-1">
            {validation.scopes.map((s) => (
              <span key={s} className="bg-blue-50 border border-blue-200 text-blue-700 px-2 py-0.5 rounded text-[11px] font-mono">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="divide-y border rounded-lg">
        {validation?.checks.map((c, i) => <CheckRow key={i} check={c} />)}
      </div>

      {!connected && validation && !validation.token_valid && (
        <p className="text-xs text-red-600 flex items-start gap-2">
          <AlertCircle size={14} className="mt-0.5" />
          Token inválido. Confirme o System User Token no Business Manager e re-cole acima.
        </p>
      )}
    </div>
  )
}

function CheckRow({ check }: { check: MetaValidationCheck }) {
  const Icon = check.ok ? CheckCircle2 : XCircle
  const color = check.ok ? 'text-green-600' : 'text-red-600'
  return (
    <div className="flex items-start gap-3 px-3 py-2 text-sm">
      <Icon size={16} className={`${color} mt-0.5 flex-shrink-0`} />
      <div className="flex-1 min-w-0">
        <div className="font-medium text-neutral-800">{check.label}</div>
        {check.detail && (
          <div className="text-xs text-neutral-500 mt-0.5 break-words">{check.detail}</div>
        )}
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────
// Form helpers
// ─────────────────────────────────────────────────────────────────────

function Row({ children }: { children: React.ReactNode }) {
  return <div className="grid grid-cols-1 md:grid-cols-2 gap-4">{children}</div>
}

function Field({
  label, value, onChange, placeholder, required, textarea,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  placeholder?: string
  required?: boolean
  textarea?: boolean
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-600">{label}</span>
      {textarea ? (
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          rows={3}
          className="mt-1 w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          required={required}
          className="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      )}
    </label>
  )
}
