/**
 * Visão Geral Meta (/marketing/visao-geral) — Sub-PR 21d.
 *
 * Página de "primeira impressão" do módulo Marketing. Usa os snapshots
 * mais recentes (perfil IG, página FB, pixel) já gravados por sync e
 * mostra:
 *   1. 3 cards grandes (IG, FB, Pixel) com números reais
 *   2. Checklist de pendências da TI (preenchido pelo backend)
 *   3. Placeholders das seções que vão aparecer quando TI destravar
 *
 * Conforme syncs forem rodando, os blocos preenchidos vão crescendo
 * automaticamente — sem mexer no código.
 */
import { useQuery } from '@tanstack/react-query'
import {
  AlertTriangle, ArrowRight, Camera, CheckCircle2, ExternalLink,
  Globe, Image as ImageIcon, MessageSquare, TrendingUp, Users,
  XCircle,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { metaService } from '@/services/meta.service'
import { usePageTitle } from '@/contexts/PageTitleContext'
import { PageContainer } from '@/components/layout/PageContainer'
import { PageHeader } from '@/components/layout/PageHeader'
import type { MetaDashboardCard, MetaPendingItem } from '@/types/meta'

const fmtNum = (n: number | null | undefined) =>
  n == null ? '—' : new Intl.NumberFormat('pt-BR').format(n)

const fmtDate = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '—'

export default function VisaoGeralPage() {
  usePageTitle('Visão Geral', 'Instagram · Facebook · Pixel — snapshot atual', 'MARKETING')
  const q = useQuery({ queryKey: ['meta', 'dashboard'], queryFn: metaService.dashboard })

  if (q.isLoading) {
    return (
      <PageContainer>
        <div className="bg-white border rounded-xl p-12 text-center text-neutral-500 text-sm shadow-sm">
          Carregando…
        </div>
      </PageContainer>
    )
  }
  if (q.isError || !q.data) {
    return (
      <PageContainer>
        <div className="bg-error-bg border border-error-border rounded-xl p-6 text-error-text text-sm">
          Erro ao carregar dashboard Meta.
        </div>
      </PageContainer>
    )
  }

  const d = q.data
  return (
    <PageContainer gap={6}>
      <PageHeader
        eyebrow="MARKETING"
        title="Visão Geral"
        subtitle={
          d.business_name
            ? `${d.business_name} · snapshot atual das redes`
            : 'Snapshot atual das redes sociais'
        }
        icon={<TrendingUp size={20} />}
      />

      {!d.has_connection && <ConnectionWarning />}

      {/* Top 3 cards grandes */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InstagramCard card={d.instagram} />
        <FacebookCard card={d.facebook} />
        <PixelCard card={d.pixel} />
      </div>

      {/* Pendências TI */}
      {d.pending.length > 0 && <PendingTI items={d.pending} />}

      {/* Placeholders do que vem */}
      <ComingSoon hasPending={d.pending.length > 0} />
    </PageContainer>
  )
}

// ─────────────────────────────────────────────────────────────────
// Banner sem conexão
// ─────────────────────────────────────────────────────────────────

function ConnectionWarning() {
  return (
    <div className="bg-warning-bg border border-warning-border rounded-xl p-4 flex items-start gap-3 text-sm">
      <AlertTriangle size={18} className="text-warning-text mt-0.5 shrink-0" />
      <div className="flex-1">
        <strong className="text-warning-text">Sem conexão Meta ativa.</strong>{' '}
        <span className="text-neutral-700">
          Os dados abaixo podem estar desatualizados ou ausentes. Configure o token e valide
          em <Link to="/empresa/meta-config" className="underline">/empresa/meta-config</Link>.
        </span>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Cards principais
// ─────────────────────────────────────────────────────────────────

function InstagramCard({ card }: { card: MetaDashboardCard }) {
  if (!card.available) {
    return <EmptyCard title="Instagram" icon={<ImageIcon size={20} />} hint="Sem snapshot — rode o sync IG Perfil" />
  }
  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3 text-xs font-medium text-neutral-500 uppercase tracking-wider">
        <ImageIcon size={14} /> Instagram
      </div>

      <div className="flex items-start gap-3 mb-4">
        {card.profile_picture_url ? (
          <img
            src={card.profile_picture_url}
            alt={card.username || ''}
            className="w-14 h-14 rounded-full object-cover border"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="w-14 h-14 rounded-full bg-neutral-100 flex items-center justify-center">
            <ImageIcon size={20} className="text-neutral-400" />
          </div>
        )}
        <div className="min-w-0">
          {card.username && (
            <div className="text-base font-semibold text-neutral-800 truncate">@{card.username}</div>
          )}
          {card.display_name && (
            <div className="text-xs text-neutral-500 truncate">{card.display_name}</div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-4">
        <Stat label="Seguidores" value={fmtNum(card.followers)} highlight />
        <Stat label="Seguindo" value={fmtNum(card.follows)} />
        <Stat label="Posts" value={fmtNum(card.total_posts)} />
      </div>

      {card.biografia && (
        <p className="text-xs text-neutral-600 line-clamp-3 mb-3">{card.biografia}</p>
      )}

      {card.website && (
        <a
          href={card.website}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1"
        >
          {card.website.replace(/^https?:\/\//, '').slice(0, 40)} <ExternalLink size={11} />
        </a>
      )}

      <SnapshotFooter date={card.snapshot_date} />
    </div>
  )
}

function FacebookCard({ card }: { card: MetaDashboardCard }) {
  if (!card.available) {
    return <EmptyCard title="Facebook" icon={<Globe size={20} />} hint="Sem snapshot — rode o sync FB Page" />
  }
  return (
    <div className="bg-white border rounded-xl p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-3 text-xs font-medium text-neutral-500 uppercase tracking-wider">
        <Globe size={14} /> Facebook
      </div>

      <div className="mb-4">
        <div className="text-base font-semibold text-neutral-800 truncate">
          {card.display_name || '—'}
        </div>
        <div className="flex items-center gap-2 mt-0.5 text-xs text-neutral-500">
          {card.username && <span>@{card.username}</span>}
          {card.category && <span className="px-1.5 py-0.5 bg-neutral-100 rounded text-[10px]">{card.category}</span>}
          {card.verification_status === 'verified' && (
            <span className="text-success-text inline-flex items-center gap-0.5 text-[10px]">
              <CheckCircle2 size={10} /> verificada
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <Stat label="Fãs" value={fmtNum(card.fan_count)} highlight />
        <Stat label="Seguidores" value={fmtNum(card.followers)} />
      </div>

      {card.biografia && (
        <p className="text-xs text-neutral-600 line-clamp-3 mb-3">{card.biografia}</p>
      )}

      {card.website && (
        <a
          href={card.website}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-blue-600 hover:underline inline-flex items-center gap-1"
        >
          {card.website.replace(/^https?:\/\//, '').slice(0, 40)} <ExternalLink size={11} />
        </a>
      )}

      <SnapshotFooter date={card.snapshot_date} />
    </div>
  )
}

function PixelCard({ card }: { card: MetaDashboardCard }) {
  if (!card.available) {
    return <EmptyCard title="Pixel" icon={<Camera size={20} />} hint="Sem snapshot — rode o sync Pixel" />
  }
  const isStale = (card.pixel_days_idle || 0) > 30
  const isDead = (card.pixel_days_idle || 0) > 365

  return (
    <div className={`border rounded-xl p-5 shadow-sm ${isDead ? 'bg-error-bg border-error-border' : isStale ? 'bg-warning-bg border-warning-border' : 'bg-white'}`}>
      <div className="flex items-center gap-2 mb-3 text-xs font-medium text-neutral-500 uppercase tracking-wider">
        <Camera size={14} /> Pixel
      </div>

      <div className="mb-4">
        <div className="text-base font-semibold text-neutral-800 truncate">
          {card.pixel_name || '—'}
        </div>
      </div>

      <div className="space-y-2 mb-4">
        <Stat label="Último disparo" value={fmtDate(card.pixel_last_fired_at)} />
        {card.pixel_days_idle != null && (
          <Stat
            label="Dias sem disparar"
            value={fmtNum(card.pixel_days_idle)}
            highlight={isStale}
            severe={isDead}
          />
        )}
      </div>

      {isDead && (
        <div className="text-xs text-error-text flex items-start gap-1.5 bg-white border border-error-border rounded-lg p-2">
          <XCircle size={13} className="mt-0.5 shrink-0" />
          <span>Pixel inativo há mais de 1 ano. Conversões zeradas — pedir reinstalação à TI.</span>
        </div>
      )}
      {isStale && !isDead && (
        <div className="text-xs text-warning-text flex items-start gap-1.5 bg-white border border-warning-border rounded-lg p-2">
          <AlertTriangle size={13} className="mt-0.5 shrink-0" />
          <span>Pixel parou de disparar recentemente. Verificar tag no site.</span>
        </div>
      )}

      <SnapshotFooter date={card.snapshot_date} />
    </div>
  )
}

function EmptyCard({ title, icon, hint }: { title: string; icon: React.ReactNode; hint: string }) {
  return (
    <div className="bg-neutral-50 border border-dashed border-neutral-300 rounded-xl p-5 flex flex-col items-center text-center text-neutral-400">
      <div className="mb-2">{icon}</div>
      <div className="text-sm font-medium text-neutral-600">{title}</div>
      <div className="text-xs mt-1">{hint}</div>
      <Link to="/admin/sync" className="text-[11px] text-blue-600 hover:underline mt-3 inline-flex items-center gap-1">
        Ir para Sincronização <ArrowRight size={11} />
      </Link>
    </div>
  )
}

function Stat({
  label, value, highlight, severe,
}: { label: string; value: string; highlight?: boolean; severe?: boolean }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-neutral-500">{label}</div>
      <div className={`tabular-nums font-semibold ${severe ? 'text-error-text text-xl' : highlight ? 'text-neutral-900 text-xl' : 'text-neutral-700 text-base'}`}>
        {value}
      </div>
    </div>
  )
}

function SnapshotFooter({ date }: { date: string | null }) {
  if (!date) return null
  return (
    <div className="mt-4 pt-3 border-t text-[10px] text-neutral-400">
      Atualizado em {new Date(date).toLocaleString('pt-BR')}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Pendências TI
// ─────────────────────────────────────────────────────────────────

function PendingTI({ items }: { items: MetaPendingItem[] }) {
  return (
    <section className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <div className="px-5 py-3 border-b bg-warning-bg flex items-center gap-2">
        <AlertTriangle size={16} className="text-warning-text" />
        <h2 className="text-sm font-semibold text-warning-text">
          Pendente da TI da clínica ({items.length})
        </h2>
      </div>
      <ul className="divide-y">
        {items.map((p) => (
          <li key={p.key} className="px-5 py-3 flex items-start gap-3">
            <XCircle size={16} className="text-error-text mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-neutral-800">{p.label}</div>
              <div className="text-xs text-neutral-600 mt-0.5">{p.detail}</div>
              {p.blocked_features.length > 0 && (
                <div className="text-[11px] mt-1.5 flex flex-wrap gap-1">
                  <span className="text-neutral-500">Bloqueia:</span>
                  {p.blocked_features.map((f) => (
                    <span key={f} className="bg-neutral-100 text-neutral-600 px-1.5 py-0.5 rounded text-[10px]">{f}</span>
                  ))}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
      <div className="px-5 py-3 bg-neutral-50 border-t text-[11px] text-neutral-500">
        Conforme essas pendências forem resolvidas, novos blocos aparecem automaticamente nesta página.
      </div>
    </section>
  )
}

// ─────────────────────────────────────────────────────────────────
// Coming soon
// ─────────────────────────────────────────────────────────────────

function ComingSoon({ hasPending }: { hasPending: boolean }) {
  return (
    <section className="bg-white border rounded-xl p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-neutral-700 mb-3">
        Próximas seções (ativam quando a TI destravar)
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <ComingSoonItem icon={<TrendingUp size={16} />} title="Alcance & Engajamento" desc="Reach, impressões, profile views — orgânico IG/FB" />
        <ComingSoonItem icon={<MessageSquare size={16} />} title="Comentários & IA" desc="Leads quentes, depoimentos, dúvidas clínicas — classificação automática" />
        <ComingSoonItem icon={<Users size={16} />} title="Funil Ads → Consulta" desc="Anúncios → leads → WhatsApp → agenda → realizada" />
      </div>
      {hasPending && (
        <p className="text-[11px] text-neutral-500 mt-4">
          Use a checklist acima para cobrar a TI da clínica.
        </p>
      )}
    </section>
  )
}

function ComingSoonItem({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="border border-dashed border-neutral-300 rounded-lg p-3 bg-neutral-50/50">
      <div className="flex items-center gap-2 text-neutral-500 mb-1">
        {icon}
        <span className="text-xs font-medium uppercase tracking-wider">{title}</span>
      </div>
      <p className="text-xs text-neutral-600">{desc}</p>
    </div>
  )
}
