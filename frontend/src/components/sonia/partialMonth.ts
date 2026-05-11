/**
 * Detecta se um (ano, mês) corresponde ao mês corrente em andamento.
 * Usado pela SonIA pra não comparar MoM% de mês parcial com mês anterior
 * fechado — vira "alerta enganoso" do tipo "Faturamento caiu 70%!" quando
 * na verdade só estamos no dia 10 do mês.
 *
 * Páginas que JÁ recebem `is_partial` do backend (analise/financeiro,
 * comercial, pacientes) devem usar essa flag — é autoritativa porque
 * usa a data de referência do tenant. Esse helper aqui é fallback pra
 * páginas que não recebem (Fluxo de Caixa, DRE, etc.).
 */
export interface MonthProgress {
  partial: boolean
  days: number
  totalDays: number
  progressPct: number
}

export function isCurrentMonthPartial(year: number, month: number): MonthProgress {
  const now = new Date()
  const sameMonth = year === now.getFullYear() && month === now.getMonth() + 1
  if (!sameMonth) {
    return { partial: false, days: 0, totalDays: 0, progressPct: 0 }
  }
  const days = now.getDate()
  const totalDays = new Date(year, month, 0).getDate()
  const partial = days < totalDays
  return { partial, days, totalDays, progressPct: (days / totalDays) * 100 }
}

/** Sufixo curto pra usar em frases: "até dia 10 de 31 (32%)". */
export function partialSuffix(p: MonthProgress): string {
  if (!p.partial) return ''
  return `Dia ${p.days} de ${p.totalDays} (${p.progressPct.toFixed(0)}% do mês).`
}
