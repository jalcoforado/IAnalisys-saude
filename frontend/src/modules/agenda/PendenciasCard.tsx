/**
 * Card de Pendências Operacionais — agrega tags do Clinicorp por classe
 * (orçamentos a contatar, retornos pendentes, remarcações, lembretes).
 *
 * Card "ouro" pro DONO: ele lia a agenda procurando essas tags na mão.
 * Aqui já vem agregado e ordenado pelos mais antigos (pendências esquecidas).
 */
import { ListChecks, Clock, Phone } from 'lucide-react'
import type { PendenciasOperacionaisSection, PendenciaBucket, PendenciaItem } from '@/types/home'
import { initials } from './helpers'

const BUCKET_COLORS: Record<string, { dot: string; bg: string; text: string; ring: string }> = {
  orcamento_pendente: {
    dot: 'bg-cyan-600', bg: 'bg-cyan-50', text: 'text-cyan-700', ring: 'ring-cyan-200',
  },
  retorno_pendente: {
    dot: 'bg-indigo-500', bg: 'bg-indigo-50', text: 'text-indigo-700', ring: 'ring-indigo-200',
  },
  remarcar: {
    dot: 'bg-rose-500', bg: 'bg-rose-50', text: 'text-rose-700', ring: 'ring-rose-200',
  },
  lembrete: {
    dot: 'bg-yellow-500', bg: 'bg-yellow-50', text: 'text-yellow-700', ring: 'ring-yellow-200',
  },
}

const colorsFor = (cls: string) => BUCKET_COLORS[cls] ?? BUCKET_COLORS.lembrete

const fmtDateShort = (iso: string | null) => {
  if (!iso) return null
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

export function PendenciasCard({ data }: { data: PendenciasOperacionaisSection }) {
  if (data.total === 0) return null

  return (
    <section className="bg-white border border-neutral-200 rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden lg:col-span-3">
      <header className="px-5 py-4 border-b border-neutral-100 flex items-center gap-3">
        <span className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center shrink-0 shadow-sm">
          <ListChecks size={18} className="text-white" />
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-neutral-900">Pendências operacionais</h3>
            <span className="text-[10px] uppercase px-1.5 py-0.5 rounded font-bold bg-orange-100 text-orange-800">
              Ação requerida
            </span>
          </div>
          <div className="text-xs text-neutral-500 mt-0.5">
            {data.total} pendências sinalizadas no Clinicorp · {data.buckets.length} categorias
          </div>
        </div>
      </header>

      {/* Grid de buckets — 2 colunas em telas grandes */}
      <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-neutral-100">
        {data.buckets.map((bucket) => (
          <BucketColumn key={bucket.tag_class} bucket={bucket} />
        ))}
      </div>
    </section>
  )
}

function BucketColumn({ bucket }: { bucket: PendenciaBucket }) {
  const c = colorsFor(bucket.tag_class)
  const restantes = Math.max(0, bucket.total - bucket.items.length)

  return (
    <div className="px-5 py-4">
      <div className="flex items-center gap-2 mb-3">
        <span className={`w-2 h-2 rounded-full ${c.dot}`} />
        <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500">
          {bucket.label}
        </span>
        <span className={`ml-auto text-xs font-bold px-2 py-0.5 rounded-full ${c.bg} ${c.text} ring-1 ${c.ring}`}>
          {bucket.total}
        </span>
      </div>

      <ul className="space-y-1.5">
        {bucket.items.map((item) => (
          <PendenciaRow key={`${item.appointment_external_id}-${item.tag_name}`} item={item} cls={bucket.tag_class} />
        ))}
      </ul>

      {restantes > 0 && (
        <div className="mt-2 pt-2 border-t border-neutral-100 text-[11px] text-neutral-500 flex items-center gap-1.5">
          <Phone size={11} />
          + {restantes} {bucket.label.toLowerCase()} aguardando contato
        </div>
      )}
    </div>
  )
}

function PendenciaRow({ item, cls }: { item: PendenciaItem; cls: string }) {
  const c = colorsFor(cls)
  // Idade da pendência: "muito antiga" (>= 90d) é alerta extra. Pedro vai
  // ver tags com 800+ dias na Parente — provavelmente nunca foram limpas.
  const isAntiga = item.dias_aplicada >= 90
  const dt = fmtDateShort(item.appointment_date_iso)

  return (
    <li className="flex items-center gap-2.5 py-1.5 px-2 rounded hover:bg-neutral-50 transition-colors">
      <span className={`w-7 h-7 rounded-full ${c.bg} ${c.text} flex items-center justify-center text-[10px] font-bold shrink-0 ring-1 ${c.ring}`}>
        {initials(item.paciente_nome)}
      </span>
      <div className="flex-1 min-w-0">
        <div className="text-[12px] font-semibold text-neutral-800 truncate">
          {item.paciente_nome.replace(/\*/g, '').trim()}
        </div>
        <div className="text-[10px] text-neutral-500 truncate flex items-center gap-1.5">
          <span className="truncate">{item.tag_name}</span>
          {dt && (
            <>
              <span>·</span>
              <span>{dt}</span>
            </>
          )}
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className={`text-[10px] font-bold tabular-nums inline-flex items-center gap-1 ${isAntiga ? 'text-rose-600' : 'text-neutral-500'}`}>
          <Clock size={9} />
          {item.dias_aplicada}d
        </div>
      </div>
    </li>
  )
}
