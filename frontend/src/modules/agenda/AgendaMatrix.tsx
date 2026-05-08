/**
 * Matriz hora × profissional da agenda do dia.
 * Cada célula mostra apenas ícone idade + iniciais do paciente.
 * Hover abre tooltip rico com nome, idade, gênero, profissional, categoria.
 *
 * Otimizações de visualização:
 * - Gaps vazios consecutivos (almoço, fim de tarde) colapsam em linha única
 * - Scroll automático na linha "agora" no mount + botão flutuante "Ir para agora"
 * - Linha do horário atual destacada com faixa vermelha
 */
import { useEffect, useRef, useState } from 'react'
import { Clock } from 'lucide-react'
import type { AgendaItem, AgendaSection } from '@/types/home'
import {
  PROF_COLORS,
  buildAgendaRows,
  buildSlots,
  calcAge,
  ageIcon,
  genderColor,
  initials,
  slotMinutes,
  STATUS_LABEL,
  STATUS_RING,
  STATUS_DOT,
  CATEGORY_GROUP_LABEL,
  TAG_LABEL,
  TAG_DOT,
  type ProfColor,
} from './helpers'

const fmtNum = (n: number) => new Intl.NumberFormat('pt-BR').format(n)
const fmtDateShort = (iso: string) => {
  const d = new Date(iso + 'T00:00:00')
  return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' })
}

export function AgendaMatrix({ data }: { data: AgendaSection }) {
  const profsMap = new Map<number, string>()
  for (const it of data.items) {
    if (it.profissional_external_id != null) {
      profsMap.set(
        it.profissional_external_id,
        it.profissional_nome || `Prof. #${it.profissional_external_id}`,
      )
    }
  }
  const profs = Array.from(profsMap.entries()).map(([id, nome], idx) => ({
    id, nome, color: PROF_COLORS[idx % PROF_COLORS.length],
  }))

  const slots = buildSlots(data.items)
  const rows = buildAgendaRows(slots, data.items)
  const subtitle = data.is_today
    ? `${fmtNum(data.total)} ${data.total === 1 ? 'consulta' : 'consultas'} · ${profs.length} ${profs.length === 1 ? 'profissional' : 'profissionais'}`
    : `Hoje sem consultas — exibindo ${fmtDateShort(data.date_iso)}`

  const now = new Date()
  const nowMin = data.is_today ? now.getHours() * 60 + now.getMinutes() : -1

  // Refs pra scroll automático na linha "agora"
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const nowRowRef = useRef<HTMLTableRowElement | null>(null)
  const [showJumpBtn, setShowJumpBtn] = useState(false)

  const scrollToNow = () => {
    if (!nowRowRef.current || !scrollRef.current) return
    const container = scrollRef.current
    const row = nowRowRef.current
    const containerRect = container.getBoundingClientRect()
    const rowRect = row.getBoundingClientRect()
    // Posiciona no centro do container
    const targetScroll =
      container.scrollTop + (rowRect.top - containerRect.top) - container.clientHeight / 2 + rowRect.height / 2
    container.scrollTo({ top: targetScroll, behavior: 'smooth' })
  }

  // Mount: scrolla para "agora" automaticamente (sem animação no primeiro paint)
  useEffect(() => {
    if (!data.is_today || !nowRowRef.current || !scrollRef.current) return
    const container = scrollRef.current
    const row = nowRowRef.current
    const targetScroll =
      row.offsetTop - container.clientHeight / 2 + row.clientHeight / 2
    container.scrollTo({ top: Math.max(0, targetScroll), behavior: 'auto' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.date_iso])

  // Mostra botão "Ir para agora" se a linha "agora" sair da viewport
  useEffect(() => {
    if (!data.is_today || !nowRowRef.current || !scrollRef.current) return
    const container = scrollRef.current
    const row = nowRowRef.current
    const onScroll = () => {
      const cRect = container.getBoundingClientRect()
      const rRect = row.getBoundingClientRect()
      const visible = rRect.bottom > cRect.top + 40 && rRect.top < cRect.bottom - 40
      setShowJumpBtn(!visible)
    }
    container.addEventListener('scroll', onScroll)
    onScroll()
    return () => container.removeEventListener('scroll', onScroll)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.date_iso, rows.length])

  if (data.items.length === 0 || profs.length === 0) {
    return (
      <div className="rounded-xl border border-neutral-200 bg-white p-12 text-center text-neutral-400">
        Sem consultas agendadas.
      </div>
    )
  }

  return (
    <div className="rounded-xl border border-neutral-200 bg-white relative">
      <div className="px-4 py-3 border-b border-neutral-200 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-neutral-800">Agenda do dia</div>
          <div className="text-xs text-neutral-500 mt-0.5">{subtitle}</div>
        </div>
        <span className={`text-[10px] font-bold px-2 py-1 rounded ${data.is_today ? 'bg-info-bg text-info-text' : 'bg-warning-bg text-warning-text'}`}>
          {data.is_today ? 'HOJE' : 'PRÓXIMO DIA'}
        </span>
      </div>

      <div ref={scrollRef} className="overflow-auto max-h-[calc(100vh-220px)]">
        <table className="border-separate border-spacing-0 text-xs w-full">
          <thead className="sticky top-0 z-20">
            <tr>
              <th className="sticky left-0 top-0 z-30 bg-white border-b border-r border-neutral-200 w-[54px] py-2 text-[10px] uppercase tracking-wide text-neutral-400 font-bold">
                Hora
              </th>
              {profs.map((p) => (
                <th
                  key={p.id}
                  className="border-b border-r border-neutral-100 px-1.5 py-2 min-w-[72px] bg-white relative"
                >
                  <div className="group/prof flex items-center justify-center cursor-default">
                    <span className={`w-9 h-9 rounded-full ${p.color.avatar} flex items-center justify-center text-[12px] font-bold ring-2 ring-white shadow-sm`}>
                      {initials(p.nome)}
                    </span>
                    <div className="invisible opacity-0 group-hover/prof:visible group-hover/prof:opacity-100 transition-opacity duration-150 absolute top-full left-1/2 -translate-x-1/2 mt-1 z-50 pointer-events-none">
                      <div className="bg-neutral-900 text-white rounded-lg shadow-xl px-3 py-2 text-[11px] whitespace-nowrap">
                        <div className="font-semibold">{p.nome}</div>
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 -mb-px border-4 border-transparent border-b-neutral-900" />
                      </div>
                    </div>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rIdx) => {
              if (row.type === 'gap') {
                return (
                  <tr key={`gap-${row.startSlot}`}>
                    <td
                      colSpan={profs.length + 1}
                      className="border-b border-neutral-100 bg-neutral-50/40 text-center text-[10px] text-neutral-400 italic py-1.5 font-mono tabular-nums"
                    >
                      <span className="font-semibold text-neutral-500">{row.startSlot}</span>
                      <span className="mx-1.5">—</span>
                      <span className="font-semibold text-neutral-500">{row.endSlot}</span>
                      <span className="ml-2 not-italic">·</span>
                      <span className="ml-1.5 not-italic">sem agenda ({Math.floor(row.minutes / 60)}h{row.minutes % 60 ? `${String(row.minutes % 60).padStart(2, '0')}` : ''})</span>
                    </td>
                  </tr>
                )
              }
              const slot = row.slot
              const slotMin = slotMinutes(slot)
              const isPastSlot = nowMin >= 0 && nowMin >= slotMin + 30
              const isCurrentSlot = nowMin >= 0 && nowMin >= slotMin && nowMin < slotMin + 30
              const zebraIdx = rIdx
              return (
                <tr
                  key={slot}
                  ref={isCurrentSlot ? nowRowRef : undefined}
                  className={`${zebraIdx % 2 === 0 ? 'bg-neutral-50/30' : ''} ${
                    isCurrentSlot ? 'relative' : ''
                  }`}
                >
                  <td
                    className={`sticky left-0 z-10 border-r border-neutral-100 px-2 py-1 text-center font-mono tabular-nums text-[10px] font-semibold ${
                      isCurrentSlot
                        ? 'bg-rose-50 text-rose-700 border-t-2 border-t-rose-500'
                        : zebraIdx % 2 === 0
                          ? 'bg-neutral-50/80 text-neutral-500'
                          : 'bg-white text-neutral-500'
                    }`}
                  >
                    {slot}
                  </td>
                  {profs.map((p) => {
                    const cellItems = data.items.filter((it) => {
                      if (it.profissional_external_id !== p.id || !it.horario) return false
                      const [h, m] = it.horario.split(':').map(Number)
                      const itMin = h * 60 + m
                      return itMin >= slotMin && itMin < slotMin + 30
                    })
                    return (
                      <td
                        key={p.id}
                        className={`border-r border-b border-neutral-100 align-top p-0.5 ${
                          isCurrentSlot ? 'border-t-2 border-t-rose-500' : ''
                        }`}
                      >
                        {cellItems.length === 0 ? (
                          <div className="h-7" />
                        ) : (
                          <div className="flex flex-col gap-0.5">
                            {cellItems.map((it) => (
                              <AgendaChip
                                key={it.external_id}
                                item={it}
                                profColor={p.color}
                                isPast={isPastSlot}
                              />
                            ))}
                          </div>
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Botão flutuante "Ir para agora" — aparece quando a linha atual está fora da viewport */}
      {data.is_today && showJumpBtn && nowMin >= 0 && (
        <button
          onClick={scrollToNow}
          className="absolute bottom-4 right-4 z-30 inline-flex items-center gap-1.5 px-3 py-2 rounded-full bg-rose-600 hover:bg-rose-700 text-white text-[12px] font-semibold shadow-lg transition-colors"
          title="Centralizar na linha atual"
        >
          <Clock size={13} />
          Ir para agora
        </button>
      )}
    </div>
  )
}

function AgendaChip({
  item, isPast,
}: {
  item: AgendaItem
  profColor: ProfColor
  isPast: boolean
}) {
  const age = calcAge(item.paciente_birth_date)
  const Icon = ageIcon(age)
  const iconColor = genderColor(item.paciente_gender)
  const generoLabel =
    item.paciente_gender === 'F' ? 'Feminino' :
    item.paciente_gender === 'M' ? 'Masculino' : ''

  const statusLabel = item.status_type ? STATUS_LABEL[item.status_type] : 'Agendado'
  const statusRing = item.status_type ? STATUS_RING[item.status_type] : 'ring-neutral-300'
  const statusDot = item.status_type ? STATUS_DOT[item.status_type] : 'bg-neutral-300'
  const categoryLabel = item.category_group ? CATEGORY_GROUP_LABEL[item.category_group] : null

  // Badge de risco quando >= 30%. Sobrescreve cor do anel pra dar destaque
  // visual em pacientes que merecem atenção operacional.
  const risco = item.risco_pct ?? 0
  const isRiscoAlto = risco >= 50
  const isRiscoMedio = risco >= 30 && risco < 50
  const riscoRing =
    isRiscoAlto ? 'ring-red-500' :
    isRiscoMedio ? 'ring-amber-500' : null
  const finalRing = riscoRing ?? statusRing

  // Tags operacionais (Aguardado vaga, Encaixe, Lembrete...) — bolinhas
  // pequenas no rodapé do chip. Limitado a 3 pra não estourar largura.
  const tags = (item.tags ?? []).filter((t) => t.tag_class && t.tag_class !== 'outro')
  const tagsToShow = tags.slice(0, 3)
  const tagsExtra = Math.max(0, tags.length - tagsToShow.length)

  return (
    <div className="group/chip relative">
      <div
        className={`rounded-md ring-[1.5px] ${finalRing} bg-white hover:bg-neutral-50 hover:shadow-md transition-all py-1 flex flex-col items-center justify-center gap-0.5 cursor-default ${
          isPast ? 'opacity-40' : ''
        }`}
      >
        {/* Dot de status no canto superior direito */}
        <span
          className={`absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full ${statusDot} ring-1 ring-white`}
          aria-hidden
        />
        {/* Badge de risco no canto superior esquerdo */}
        {(isRiscoAlto || isRiscoMedio) && (
          <span
            className={`absolute top-0.5 left-0.5 text-[7px] font-bold px-1 rounded leading-tight ${
              isRiscoAlto ? 'bg-red-500 text-white' : 'bg-amber-500 text-white'
            }`}
            title={`Risco ${risco}% — ${item.risco_razao ?? ''}`}
          >
            {risco}%
          </span>
        )}
        <Icon size={20} className={`${iconColor} shrink-0`} strokeWidth={2} />
        <span className="text-[10px] font-bold tabular-nums tracking-tight text-neutral-800 leading-none">
          {initials(item.paciente_nome)}
        </span>
        {/* Bolinhas das tags operacionais no rodapé do chip */}
        {tagsToShow.length > 0 && (
          <div className="flex items-center gap-0.5 mt-0.5" aria-hidden>
            {tagsToShow.map((t, i) => (
              <span
                key={i}
                className={`w-1.5 h-1.5 rounded-full ${t.tag_class ? TAG_DOT[t.tag_class] : 'bg-neutral-400'} ring-1 ring-white`}
              />
            ))}
            {tagsExtra > 0 && (
              <span className="text-[7px] font-semibold text-neutral-500 leading-none">
                +{tagsExtra}
              </span>
            )}
          </div>
        )}
      </div>

      <div className="invisible opacity-0 group-hover/chip:visible group-hover/chip:opacity-100 transition-opacity duration-150 absolute top-full left-1/2 -translate-x-1/2 mt-2 z-50 pointer-events-none">
        <div className="bg-neutral-900 text-white rounded-lg shadow-xl px-3 py-2 text-[11px] leading-snug whitespace-nowrap">
          <div className="absolute bottom-full left-1/2 -translate-x-1/2 -mb-px border-4 border-transparent border-b-neutral-900" />
          <div className="font-semibold text-white">{item.paciente_nome}</div>
          <div className="text-neutral-300 mt-0.5 flex items-center gap-2">
            <span>🕐 {item.horario || '—'}{item.duration_minutes ? ` · ${item.duration_minutes}min` : ''}</span>
            {age !== null && <span>· {age} anos</span>}
            {generoLabel && <span>· {generoLabel}</span>}
          </div>
          {item.profissional_nome && (
            <div className="text-neutral-300 mt-0.5">👤 {item.profissional_nome}</div>
          )}
          <div className="text-neutral-400 mt-0.5 flex items-center gap-2">
            <span className={`inline-block w-1.5 h-1.5 rounded-full ${statusDot}`} />
            <span>{statusLabel}</span>
            <span>·</span>
            <span>📋 {categoryLabel ? `${categoryLabel} · ${item.categoria}` : item.categoria}</span>
          </div>
          {(isRiscoAlto || isRiscoMedio) && (
            <div className={`mt-0.5 ${isRiscoAlto ? 'text-red-300' : 'text-amber-300'}`}>
              ⚠ Risco {risco}% — {item.risco_razao ?? '—'}
            </div>
          )}
          {tags.length > 0 && (
            <div className="mt-1 pt-1 border-t border-white/10 space-y-0.5">
              {tags.map((t, i) => (
                <div key={i} className="flex items-center gap-1.5 text-neutral-200">
                  <span className={`w-1.5 h-1.5 rounded-full ${t.tag_class ? TAG_DOT[t.tag_class] : 'bg-neutral-400'}`} />
                  <span>{t.tag_class ? TAG_LABEL[t.tag_class] : t.name}</span>
                  {t.name && t.tag_class && t.tag_class !== 'outro' && (
                    <span className="text-neutral-500">· {t.name}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
