/**
 * Seletor de mês/ano padrão para os dashboards de Análise.
 * Botões << (mês anterior) e >> (próximo, bloqueado se futuro).
 */
import { ChevronLeft, ChevronRight } from 'lucide-react'

const MONTHS_PT = [
  'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
  'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]

type Props = {
  year: number
  month: number
  onChange: (year: number, month: number) => void
}

export function PeriodSelector({ year, month, onChange }: Props) {
  const today = new Date()
  const isFuture =
    year > today.getFullYear() ||
    (year === today.getFullYear() && month > today.getMonth() + 1)
  const canGoBack = year > 2020 || (year === 2020 && month > 1)

  const goPrev = () => {
    if (!canGoBack) return
    if (month === 1) onChange(year - 1, 12)
    else onChange(year, month - 1)
  }

  const goNext = () => {
    if (isFuture) return
    if (month === 12) onChange(year + 1, 1)
    else onChange(year, month + 1)
  }

  // Bloqueia next quando o próximo mês seria futuro
  const nextWouldBeFuture =
    (year === today.getFullYear() && month >= today.getMonth() + 1) ||
    year > today.getFullYear()

  return (
    <div className="inline-flex items-center gap-1 bg-white border border-neutral-200 rounded-lg shadow-sm p-1">
      <button
        onClick={goPrev}
        disabled={!canGoBack}
        className="w-8 h-8 rounded flex items-center justify-center text-neutral-600 hover:bg-neutral-100 disabled:opacity-40 disabled:cursor-not-allowed"
        title="Mês anterior"
      >
        <ChevronLeft size={16} />
      </button>
      <span className="px-3 text-sm font-semibold text-neutral-800 min-w-[140px] text-center capitalize">
        {MONTHS_PT[month - 1]} / {year}
      </span>
      <button
        onClick={goNext}
        disabled={nextWouldBeFuture}
        className="w-8 h-8 rounded flex items-center justify-center text-neutral-600 hover:bg-neutral-100 disabled:opacity-40 disabled:cursor-not-allowed"
        title="Próximo mês"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  )
}
