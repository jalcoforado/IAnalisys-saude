/**
 * Helpers compartilhados pela página de Agenda.
 * Movidos da HomePage para reuso entre matriz e cards de resumo.
 */
import { Baby, User, UserCog } from 'lucide-react'
import type { AgendaItem, CategoryGroup, StatusType, TagClass } from '@/types/home'

// Status do appointment (Clinicorp). Quando vazio = Agendado (default).
export const STATUS_LABEL: Record<StatusType, string> = {
  CONFIRMED: 'Confirmado',
  ARRIVED: 'Chegou',
  IN_SESSION: 'Em atendimento',
  CHECKOUT: 'Atendido',
  MISSED: 'Faltou',
  LATE: 'Atrasado',
  CALL: 'Ligar',
  PENDING_MATERIAL: 'Prótese pendente',
}

// Cor visual de cada status — usa a paleta Clinicorp como referência mas
// aproxima pra Tailwind p/ consistência com o resto do app.
export const STATUS_RING: Record<StatusType, string> = {
  CONFIRMED: 'ring-emerald-400',
  ARRIVED: 'ring-yellow-400',
  IN_SESSION: 'ring-blue-500',
  CHECKOUT: 'ring-green-500',
  MISSED: 'ring-neutral-500',
  LATE: 'ring-red-500',
  CALL: 'ring-orange-500',
  PENDING_MATERIAL: 'ring-purple-500',
}

export const STATUS_DOT: Record<StatusType, string> = {
  CONFIRMED: 'bg-emerald-500',
  ARRIVED: 'bg-yellow-400',
  IN_SESSION: 'bg-blue-500',
  CHECKOUT: 'bg-green-500',
  MISSED: 'bg-neutral-500',
  LATE: 'bg-red-500',
  CALL: 'bg-orange-500',
  PENDING_MATERIAL: 'bg-purple-500',
}

export const CATEGORY_GROUP_LABEL: Record<CategoryGroup, string> = {
  consulta: 'Consulta',
  retorno: 'Retorno',
  manutencao: 'Manutenção',
  procedimento: 'Procedimento',
  reabilitacao: 'Reabilitação',
  ortodontia: 'Ortodontia',
  bloqueio: 'Bloqueio',
  outro: 'Outro',
}

// Tags operacionais do Clinicorp. Bolinha pequena no canto do chip; usa
// tag_class (semântica) em vez do nome cru porque a clínica usa nomes
// inconsistentes ("Aguardado vaga" vs "AGUARDANDO VAGA" etc).
export const TAG_LABEL: Record<TagClass, string> = {
  waitlist: 'Aguardando vaga',
  encaixe: 'Encaixe',
  remarcar: 'Remarcar',
  lembrete: 'Lembrete',
  orcamento_pendente: 'Orçamento pendente',
  retorno_pendente: 'Retorno pendente',
  financeiro_conferido: 'Financeiro conferido',
  outro: 'Tag',
}

export const TAG_DOT: Record<TagClass, string> = {
  waitlist: 'bg-green-500',
  encaixe: 'bg-fuchsia-500',
  remarcar: 'bg-rose-500',
  lembrete: 'bg-yellow-500',
  orcamento_pendente: 'bg-cyan-600',
  retorno_pendente: 'bg-indigo-500',
  financeiro_conferido: 'bg-emerald-600',
  outro: 'bg-neutral-400',
}

export const PROF_COLORS = [
  { header: 'bg-blue-50 text-blue-700 ring-blue-200', avatar: 'bg-blue-100 text-blue-700', accent: 'border-blue-300' },
  { header: 'bg-emerald-50 text-emerald-700 ring-emerald-200', avatar: 'bg-emerald-100 text-emerald-700', accent: 'border-emerald-300' },
  { header: 'bg-amber-50 text-amber-700 ring-amber-200', avatar: 'bg-amber-100 text-amber-700', accent: 'border-amber-300' },
  { header: 'bg-purple-50 text-purple-700 ring-purple-200', avatar: 'bg-purple-100 text-purple-700', accent: 'border-purple-300' },
  { header: 'bg-rose-50 text-rose-700 ring-rose-200', avatar: 'bg-rose-100 text-rose-700', accent: 'border-rose-300' },
  { header: 'bg-cyan-50 text-cyan-700 ring-cyan-200', avatar: 'bg-cyan-100 text-cyan-700', accent: 'border-cyan-300' },
  { header: 'bg-indigo-50 text-indigo-700 ring-indigo-200', avatar: 'bg-indigo-100 text-indigo-700', accent: 'border-indigo-300' },
  { header: 'bg-orange-50 text-orange-700 ring-orange-200', avatar: 'bg-orange-100 text-orange-700', accent: 'border-orange-300' },
] as const

export type ProfColor = typeof PROF_COLORS[number]

export const initials = (name: string): string => {
  const parts = name.replace(/\*/g, '').trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0][0].toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export const calcAge = (birthIso: string | null): number | null => {
  if (!birthIso) return null
  const b = new Date(birthIso + 'T00:00:00')
  if (Number.isNaN(b.getTime())) return null
  const now = new Date()
  let age = now.getFullYear() - b.getFullYear()
  const m = now.getMonth() - b.getMonth()
  if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--
  return age >= 0 && age < 130 ? age : null
}

export const ageIcon = (age: number | null) => {
  if (age === null) return User
  if (age < 12) return Baby
  if (age >= 60) return UserCog
  return User
}

export const genderColor = (g: 'M' | 'F' | null | undefined): string => {
  if (g === 'F') return 'text-pink-600'
  if (g === 'M') return 'text-sky-600'
  return 'text-neutral-500'
}

export function buildSlots(items: AgendaItem[]): string[] {
  const horarios = items.filter((it) => it.horario).map((it) => it.horario!)
  if (horarios.length === 0) return []
  const minutes = horarios.map((h) => {
    const [hh, mm] = h.split(':').map(Number)
    return hh * 60 + mm
  })
  const mn = Math.floor(Math.min(...minutes) / 30) * 30
  const maxDuration = Math.max(...items.map((it) => it.duration_minutes ?? 30), 30)
  const mx = Math.ceil((Math.max(...minutes) + maxDuration) / 30) * 30
  const slots: string[] = []
  for (let m = mn; m < mx; m += 30) {
    slots.push(`${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`)
  }
  return slots
}

export function slotMinutes(slot: string): number {
  const [h, m] = slot.split(':').map(Number)
  return h * 60 + m
}

/** Slot normal a renderizar (1 linha de 30min). */
export type AgendaRowSlot = { type: 'slot'; slot: string }

/** Faixa de slots vazios consecutivos colapsada (ex: almoço 12:00–13:30). */
export type AgendaRowGap = {
  type: 'gap'
  startSlot: string
  endSlot: string                // último slot vazio (exclusive na exibição)
  minutes: number                // duração total do gap em minutos
  slotCount: number              // qtd de slots originalmente colapsados
}

export type AgendaRow = AgendaRowSlot | AgendaRowGap

/**
 * Processa a lista de slots + items e retorna uma sequência otimizada de linhas:
 * - Remove gap inicial se ≥1h antes da 1ª consulta
 * - Colapsa gaps internos (≥1h sem agendamentos em nenhum prof)
 * - Mantém último slot mesmo se vazio (preserva término natural do dia)
 *
 * `MIN_GAP_SLOTS_TO_COLLAPSE` = mínimo de slots vazios consecutivos pra colapsar.
 * 2 slots = 1h. Abaixo disso (30min) renderiza linhas normais — não vale o overhead visual.
 */
const MIN_GAP_SLOTS_TO_COLLAPSE = 2

export function buildAgendaRows(
  slots: string[],
  items: AgendaItem[],
): AgendaRow[] {
  if (slots.length === 0) return []

  // 1. Para cada slot, marca se há ALGUM item ocupando-o
  // (item ocupa o slot s se start_minutes <= s < start_minutes + duration)
  const isOccupied = (slotIdx: number): boolean => {
    const slotMin = slotMinutes(slots[slotIdx])
    return items.some((it) => {
      if (!it.horario) return false
      const [h, m] = it.horario.split(':').map(Number)
      const start = h * 60 + m
      const dur = it.duration_minutes ?? 30
      return start < slotMin + 30 && start + dur > slotMin
    })
  }
  const occupied = slots.map((_, i) => isOccupied(i))

  // 2. Determina índice da 1ª e última ocupação
  const firstOcc = occupied.findIndex((o) => o)
  const lastOcc = occupied.lastIndexOf(true)
  if (firstOcc === -1) {
    // dia totalmente vazio: devolve slots originais (caller decide)
    return slots.map((s) => ({ type: 'slot' as const, slot: s }))
  }

  // 3. Cortes: começa em firstOcc; vai até lastOcc + 1 slot extra (acomoda fim)
  const startIdx = firstOcc
  const endIdx = Math.min(slots.length - 1, lastOcc + 1)

  // 4. Itera no range, agrupando gaps consecutivos
  const rows: AgendaRow[] = []
  let i = startIdx
  while (i <= endIdx) {
    if (occupied[i]) {
      rows.push({ type: 'slot', slot: slots[i] })
      i++
      continue
    }
    // achou vazio: vê quantos consecutivos vazios há (sem ultrapassar endIdx)
    let j = i
    while (j <= endIdx && !occupied[j]) j++
    const gapCount = j - i
    if (gapCount >= MIN_GAP_SLOTS_TO_COLLAPSE) {
      const startSlot = slots[i]
      const endSlot = slots[j - 1]            // último slot vazio
      // exibição: end = início do próximo ocupado (ou último vazio + 30min)
      const endShownMin = j <= endIdx ? slotMinutes(slots[j]) : slotMinutes(endSlot) + 30
      const endShown = `${String(Math.floor(endShownMin / 60)).padStart(2, '0')}:${String(endShownMin % 60).padStart(2, '0')}`
      rows.push({
        type: 'gap',
        startSlot,
        endSlot: endShown,
        minutes: gapCount * 30,
        slotCount: gapCount,
      })
    } else {
      // gap pequeno (1 slot só): mantém como linha normal
      for (let k = i; k < j; k++) rows.push({ type: 'slot', slot: slots[k] })
    }
    i = j
  }
  return rows
}
