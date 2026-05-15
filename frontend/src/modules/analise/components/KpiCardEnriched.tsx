/**
 * KPI Card rico — valor grande + MoM + YoY + sparkline + insight narrativo.
 * Estrutura padronizada para todos os dashboards segmentados (Sub-PR 20).
 */
import { HelpCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import type { ReactNode } from 'react'
import type { KpiCard } from '@/types/analise'
import { Sparkline } from './Sparkline'

type Props = {
  data: KpiCard
  label: string
  icon?: ReactNode
  iconBg?: string  // tailwind class pra fundo do ícone
  /** Quando true, sublinha a importância visual (KPI principal). */
  emphasized?: boolean
  /** Conteúdo extra colado na base do card (ex: breakdown bruto/taxas). */
  footer?: ReactNode
  /** Conteúdo do tooltip de ajuda — exibido ao passar o mouse no ícone "?" ao lado do label. */
  helpTooltip?: ReactNode
  /** Classes extras pro container externo. Usado no MY-Analisys pra `h-full flex flex-col`. */
  className?: string
}

const fmtPct = (v: number | null) => {
  if (v === null || v === undefined) return null
  const sign = v > 0 ? '+' : ''
  return `${sign}${v.toFixed(1)}%`
}

const trendIcon = (trend: 'up' | 'down' | 'flat', isInverse: boolean) => {
  if (trend === 'flat') return <Minus size={12} className="text-neutral-400" />
  // Quando is_inverse, "up" é ruim e vice-versa.
  const isGood = isInverse ? trend === 'down' : trend === 'up'
  const colorClass = isGood ? 'text-emerald-500' : 'text-rose-500'
  return trend === 'up'
    ? <TrendingUp size={12} className={colorClass} />
    : <TrendingDown size={12} className={colorClass} />
}

const deltaColor = (pct: number | null, isInverse: boolean) => {
  if (pct === null || pct === undefined) return 'text-neutral-400'
  const isGood = isInverse ? pct < 0 : pct > 0
  return isGood ? 'text-emerald-600' : 'text-rose-600'
}

export function KpiCardEnriched({
  data, label, icon, iconBg = 'bg-primary-50', emphasized = false, footer, helpTooltip, className = '',
}: Props) {
  const mom = fmtPct(data.mom_pct)
  const yoy = fmtPct(data.yoy_pct)

  return (
    <div className={`bg-white border rounded-xl p-4 hover:shadow-md transition-shadow ${
      emphasized ? 'border-primary-200 shadow-sm' : 'border-neutral-200'
    } ${className}`}>
      {/* Header: ícone + label + sparkline */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          {icon && (
            <span className={`w-7 h-7 rounded-lg ${iconBg} flex items-center justify-center shrink-0`}>
              {icon}
            </span>
          )}
          <span className="text-[11px] uppercase tracking-wider font-bold text-neutral-500 truncate">
            {label}
          </span>
          {helpTooltip && (
            <span className="relative group/tip shrink-0">
              <HelpCircle
                size={13}
                className="text-neutral-400 hover:text-neutral-600 cursor-help"
                aria-label="Mais informações"
              />
              <div className="hidden group-hover/tip:block absolute z-20 left-1/2 -translate-x-1/2 top-full mt-1 w-72 bg-neutral-900 text-white text-[11px] leading-snug rounded-lg shadow-xl p-3 normal-case tracking-normal font-normal">
                {helpTooltip}
              </div>
            </span>
          )}
        </div>
        {data.sparkline_12m.length > 1 && (
          <Sparkline values={data.sparkline_12m} inverse={data.is_inverse} className="shrink-0" />
        )}
      </div>

      {/* Valor principal + tendência */}
      <div className="flex items-baseline gap-2 mb-1">
        <span className="text-2xl font-bold text-neutral-900 tabular-nums">
          {data.value_label}
        </span>
        {trendIcon(data.trend, data.is_inverse)}
      </div>

      {/* Projeção quando mês parcial */}
      {data.is_partial && data.projected_label && (
        <div className="text-[11px] text-primary-700 font-semibold mb-2 tabular-nums">
          → {data.projected_label}
        </div>
      )}

      {/* MoM e YoY */}
      <div className="flex items-center gap-3 text-[11px] mb-2">
        {mom !== null && (
          <span className={`font-semibold tabular-nums ${deltaColor(data.mom_pct, data.is_inverse)}`}>
            {mom} <span className="font-normal text-neutral-400">MoM</span>
          </span>
        )}
        {yoy !== null && (
          <span className={`font-semibold tabular-nums ${deltaColor(data.yoy_pct, data.is_inverse)}`}>
            {yoy} <span className="font-normal text-neutral-400">YoY</span>
          </span>
        )}
        {mom === null && yoy === null && (
          <span className="text-neutral-400">Sem comparativo histórico</span>
        )}
      </div>

      {/* Insight narrativo (gerado por regras no backend). `mt-auto` só tem
          efeito quando o pai é `flex flex-col h-full` (caso MY-Analisys) —
          em CSS Grid normal não afeta. */}
      {data.insight && (
        <div className="text-[11px] text-neutral-500 leading-snug border-t border-neutral-100 pt-2 mt-auto">
          {data.insight}
        </div>
      )}

      {footer && (
        <div className="mt-2 pt-2 border-t border-neutral-100 text-[11px] text-neutral-600">
          {footer}
        </div>
      )}
    </div>
  )
}
