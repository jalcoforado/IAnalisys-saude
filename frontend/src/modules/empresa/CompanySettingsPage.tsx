import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Building2,
  Image as ImageIcon,
  MapPin,
  Palette,
  Trash2,
  Upload,
} from 'lucide-react'

import { tenantService } from '@/services/tenant.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import type {
  TenantSettings,
  TenantSettingsUpdate,
  UploadKind,
} from '@/types/tenant'

export default function CompanySettingsPage() {
  usePageTitle('Configurações da Empresa', 'Identidade visual e dados operacionais', 'EMPRESA')
  const qc = useQueryClient()

  const settingsQ = useQuery({
    queryKey: ['tenant', 'settings'],
    queryFn: tenantService.getSettings,
  })

  if (settingsQ.isLoading) {
    return (
      <PageContainer variant="narrow">
        <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">Carregando…</div>
      </PageContainer>
    )
  }
  if (settingsQ.isError || !settingsQ.data) {
    return (
      <PageContainer variant="narrow">
        <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
          Erro ao carregar configurações da empresa.
        </div>
      </PageContainer>
    )
  }

  const onUpdated = () => qc.invalidateQueries({ queryKey: ['tenant', 'settings'] })

  return (
    <PageContainer variant="narrow" gap={6}>
      <PageHeader
        eyebrow="EMPRESA"
        title="Configurações da Empresa"
        subtitle="Identidade visual e dados operacionais"
        icon={<Building2 size={20} />}
      />
      <p className="text-xs text-neutral-500">
        Personalize a identidade visual e os dados da clínica. Apenas administradores do tenant podem editar.
      </p>

      <BrandingSection settings={settingsQ.data} onUpdated={onUpdated} />
      <CompanyDataSection settings={settingsQ.data} onUpdated={onUpdated} />
      <AddressSection settings={settingsQ.data} onUpdated={onUpdated} />
    </PageContainer>
  )
}

// ── Branding ──────────────────────────────────────────────────

function BrandingSection({ settings, onUpdated }: { settings: TenantSettings; onUpdated: () => void }) {
  const [primary, setPrimary] = useState(settings.primary_color || '#1D4ED8')
  const [secondary, setSecondary] = useState(settings.secondary_color || '#60A5FA')

  useEffect(() => {
    setPrimary(settings.primary_color || '#1D4ED8')
    setSecondary(settings.secondary_color || '#60A5FA')
  }, [settings.primary_color, settings.secondary_color])

  const colorMut = useMutation({
    mutationFn: (payload: TenantSettingsUpdate) => tenantService.updateSettings(payload),
    onSuccess: onUpdated,
  })

  const saveColors = () => {
    colorMut.mutate({ primary_color: primary, secondary_color: secondary })
  }

  return (
    <Section title="Identidade Visual" subtitle="Logo, favicon, fundo de login e cores da marca" icon={<Palette size={16} />}>
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <ImageUploader
            kind="logo"
            label="Logo principal"
            currentUrl={settings.logo_url}
            description="PNG, SVG, JPEG ou WebP · até 1 MB · ideal 200×60px"
            onUpdated={onUpdated}
            previewBg="bg-white"
          />
          <ImageUploader
            kind="favicon"
            label="Favicon"
            currentUrl={settings.favicon_url}
            description="PNG, ICO ou SVG · até 200 KB · 32×32 ou 64×64"
            onUpdated={onUpdated}
            previewBg="bg-white"
            previewSize="small"
          />
          <ImageUploader
            kind="login_background"
            label="Fundo do login"
            currentUrl={settings.login_background_url}
            description="PNG, JPEG ou WebP · até 3 MB · 1920×1080 recomendado"
            onUpdated={onUpdated}
            previewBg="bg-neutral-100"
          />
        </div>

        <div className="border-t pt-4">
          <div className="text-xs font-semibold text-neutral-700 uppercase tracking-wide mb-3">Cores da marca</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ColorField
              label="Cor primária"
              hint="Botões, destaques, gradiente da topbar"
              value={primary}
              onChange={setPrimary}
            />
            <ColorField
              label="Cor secundária"
              hint="Acentos, hover, complementos"
              value={secondary}
              onChange={setSecondary}
            />
          </div>
          <div className="mt-3 flex justify-end">
            <button
              onClick={saveColors}
              disabled={colorMut.isPending}
              className="text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800 disabled:opacity-50 font-medium"
            >
              {colorMut.isPending ? 'Salvando…' : 'Salvar cores'}
            </button>
          </div>
        </div>
      </div>
    </Section>
  )
}

function ColorField({ label, hint, value, onChange }: { label: string; hint: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-neutral-700 font-medium">{label}</label>
      <div className="mt-1 flex items-center gap-2 border rounded-lg px-2 py-1.5 bg-white">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-9 h-9 rounded cursor-pointer border-0 p-0"
        />
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={7}
          className="flex-1 text-sm font-mono uppercase tabular-nums focus:outline-none bg-transparent"
          placeholder="#1D4ED8"
        />
      </div>
      <div className="text-[11px] text-neutral-400 mt-0.5">{hint}</div>
    </div>
  )
}

function ImageUploader({ kind, label, currentUrl, description, onUpdated, previewBg, previewSize }: {
  kind: UploadKind; label: string; currentUrl: string | null; description: string;
  onUpdated: () => void; previewBg: string; previewSize?: 'small'
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  const uploadMut = useMutation({
    mutationFn: (file: File) => tenantService.uploadAsset(kind, file),
    onSuccess: () => {
      setError(null)
      qc.invalidateQueries({ queryKey: ['tenant', 'settings'] })
      onUpdated()
    },
    onError: (e: any) => {
      setError(e?.message || e?.response?.data?.detail || 'Falha no upload.')
    },
  })

  const deleteMut = useMutation({
    mutationFn: () => tenantService.deleteAsset(kind),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tenant', 'settings'] })
      onUpdated()
    },
  })

  const handleSelect = () => inputRef.current?.click()
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadMut.mutate(file)
    e.target.value = ''
  }

  const previewSizeClass = previewSize === 'small' ? 'h-20' : 'h-32'

  return (
    <div className="border border-neutral-200 rounded-lg overflow-hidden bg-neutral-50/50">
      <div className="px-3 py-2 border-b bg-white flex items-center gap-2">
        <ImageIcon size={14} className="text-neutral-400 shrink-0" />
        <div className="min-w-0">
          <div className="text-xs font-semibold text-neutral-800 truncate">{label}</div>
        </div>
      </div>

      <div className={`${previewSizeClass} ${previewBg} flex items-center justify-center relative`}>
        {currentUrl ? (
          <img src={currentUrl} alt={label} className="max-h-full max-w-full object-contain" />
        ) : (
          <div className="text-[11px] text-neutral-400 text-center px-3">Nenhuma imagem · clique abaixo para enviar</div>
        )}
      </div>

      <div className="px-3 py-2 bg-white border-t flex items-center gap-1.5">
        <input ref={inputRef} type="file" hidden onChange={handleChange} accept="image/*" />
        <button
          onClick={handleSelect}
          disabled={uploadMut.isPending}
          className="flex-1 text-[11px] px-2 py-1.5 rounded bg-primary-50 text-primary-700 hover:bg-primary-100 disabled:opacity-50 font-medium flex items-center justify-center gap-1"
        >
          <Upload size={12} />
          {uploadMut.isPending ? 'Enviando…' : currentUrl ? 'Trocar' : 'Enviar'}
        </button>
        {currentUrl && (
          <button
            onClick={() => deleteMut.mutate()}
            disabled={deleteMut.isPending}
            className="text-[11px] px-2 py-1.5 rounded bg-error-bg text-error-text hover:bg-red-100 disabled:opacity-50 flex items-center justify-center"
            title="Remover"
          >
            <Trash2 size={12} />
          </button>
        )}
      </div>

      <div className="px-3 py-1.5 text-[10px] text-neutral-500 border-t bg-white">{description}</div>
      {error && <div className="px-3 py-1.5 text-[11px] text-error-text bg-error-bg border-t">{error}</div>}
    </div>
  )
}

// ── Dados da Empresa ──────────────────────────────────────────

function CompanyDataSection({ settings, onUpdated }: { settings: TenantSettings; onUpdated: () => void }) {
  const [form, setForm] = useState({
    name: settings.name || '',
    legal_name: settings.legal_name || '',
    tax_id: settings.tax_id || '',
    email: settings.email || '',
    phone: settings.phone || '',
    whatsapp: settings.whatsapp || '',
    website: settings.website || '',
  })

  useEffect(() => {
    setForm({
      name: settings.name || '',
      legal_name: settings.legal_name || '',
      tax_id: settings.tax_id || '',
      email: settings.email || '',
      phone: settings.phone || '',
      whatsapp: settings.whatsapp || '',
      website: settings.website || '',
    })
  }, [settings])

  const mut = useMutation({
    mutationFn: (payload: TenantSettingsUpdate) => tenantService.updateSettings(payload),
    onSuccess: onUpdated,
  })

  return (
    <Section title="Dados da Empresa" subtitle="Identificação fiscal e canais de contato" icon={<Building2 size={16} />}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Field label="Nome fantasia" value={form.name} onChange={(v) => setForm({ ...form, name: v })} required />
        <Field label="Razão social" value={form.legal_name} onChange={(v) => setForm({ ...form, legal_name: v })} />
        <Field label="CNPJ" value={form.tax_id} onChange={(v) => setForm({ ...form, tax_id: v })} placeholder="00.000.000/0000-00" />
        <Field label="E-mail" type="email" value={form.email} onChange={(v) => setForm({ ...form, email: v })} placeholder="contato@clinica.com.br" />
        <Field label="Telefone" value={form.phone} onChange={(v) => setForm({ ...form, phone: v })} placeholder="(00) 0000-0000" />
        <Field label="WhatsApp" value={form.whatsapp} onChange={(v) => setForm({ ...form, whatsapp: v })} placeholder="(00) 90000-0000" />
        <Field label="Site" value={form.website} onChange={(v) => setForm({ ...form, website: v })} placeholder="https://clinica.com.br" className="md:col-span-2" />
      </div>
      <div className="mt-4 flex justify-end items-center gap-3">
        {mut.isError && <span className="text-xs text-error-text">Erro ao salvar. Tente novamente.</span>}
        {mut.isSuccess && <span className="text-xs text-success-text">✓ Salvo</span>}
        <button
          onClick={() => mut.mutate(form)}
          disabled={mut.isPending}
          className="text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800 disabled:opacity-50 font-medium"
        >
          {mut.isPending ? 'Salvando…' : 'Salvar dados'}
        </button>
      </div>
    </Section>
  )
}

// ── Endereço ──────────────────────────────────────────────────

function AddressSection({ settings, onUpdated }: { settings: TenantSettings; onUpdated: () => void }) {
  const [form, setForm] = useState({
    address_zip: settings.address_zip || '',
    address_street: settings.address_street || '',
    address_number: settings.address_number || '',
    address_complement: settings.address_complement || '',
    address_district: settings.address_district || '',
    address_city: settings.address_city || '',
    address_state: settings.address_state || '',
  })

  useEffect(() => {
    setForm({
      address_zip: settings.address_zip || '',
      address_street: settings.address_street || '',
      address_number: settings.address_number || '',
      address_complement: settings.address_complement || '',
      address_district: settings.address_district || '',
      address_city: settings.address_city || '',
      address_state: settings.address_state || '',
    })
  }, [settings])

  const mut = useMutation({
    mutationFn: (payload: TenantSettingsUpdate) => tenantService.updateSettings(payload),
    onSuccess: onUpdated,
  })

  return (
    <Section title="Endereço" subtitle="Localização da clínica" icon={<MapPin size={16} />}>
      <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
        <Field label="CEP" value={form.address_zip} onChange={(v) => setForm({ ...form, address_zip: v })} className="md:col-span-2" placeholder="00000-000" />
        <Field label="Logradouro" value={form.address_street} onChange={(v) => setForm({ ...form, address_street: v })} className="md:col-span-3" />
        <Field label="Número" value={form.address_number} onChange={(v) => setForm({ ...form, address_number: v })} />
        <Field label="Complemento" value={form.address_complement} onChange={(v) => setForm({ ...form, address_complement: v })} className="md:col-span-2" />
        <Field label="Bairro" value={form.address_district} onChange={(v) => setForm({ ...form, address_district: v })} className="md:col-span-2" />
        <Field label="Cidade" value={form.address_city} onChange={(v) => setForm({ ...form, address_city: v })} className="md:col-span-2" />
        <Field label="UF" value={form.address_state} onChange={(v) => setForm({ ...form, address_state: v.toUpperCase() })} maxLength={2} />
      </div>
      <div className="mt-4 flex justify-end items-center gap-3">
        {mut.isError && <span className="text-xs text-error-text">Erro ao salvar.</span>}
        {mut.isSuccess && <span className="text-xs text-success-text">✓ Salvo</span>}
        <button
          onClick={() => mut.mutate(form)}
          disabled={mut.isPending}
          className="text-xs px-4 py-2 rounded bg-primary-700 text-white hover:bg-primary-800 disabled:opacity-50 font-medium"
        >
          {mut.isPending ? 'Salvando…' : 'Salvar endereço'}
        </button>
      </div>
    </Section>
  )
}

// ── helpers ───────────────────────────────────────────────────

function Section({ title, subtitle, icon, children }: { title: string; subtitle?: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-sm p-5">
      <div className="flex items-center gap-2.5 mb-4">
        <span className="w-7 h-7 rounded-lg bg-primary-50 text-primary-700 flex items-center justify-center">{icon}</span>
        <div>
          <h2 className="text-sm font-bold text-neutral-900 leading-tight">{title}</h2>
          {subtitle && <p className="text-xs text-neutral-500">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function Field({ label, value, onChange, type = 'text', placeholder, required, className = '', maxLength }: {
  label: string; value: string; onChange: (v: string) => void;
  type?: string; placeholder?: string; required?: boolean; className?: string; maxLength?: number
}) {
  return (
    <div className={className}>
      <label className="text-xs text-neutral-700 font-medium">
        {label} {required && <span className="text-error-text">*</span>}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        className="mt-1 w-full text-sm px-3 py-2 border border-neutral-200 rounded-lg focus:border-primary-500 focus:ring-1 focus:ring-primary-200 focus:outline-none transition"
      />
    </div>
  )
}
