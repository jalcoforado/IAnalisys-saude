/**
 * Sparkline minimalista — SVG inline, sem libs.
 * Usado dentro dos KpiCardEnriched. 12 pontos = 12 meses.
 */
type Props = {
  values: number[]
  width?: number
  height?: number
  className?: string
  /** Quando true, vermelho representa "subiu" (caso de inadimplência etc). */
  inverse?: boolean
}

export function Sparkline({
  values, width = 80, height = 24, className = '', inverse = false,
}: Props) {
  if (!values.length) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  // Mapeia para coordenadas SVG. Y invertido (SVG cresce pra baixo).
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width
    const y = height - ((v - min) / range) * height
    return [x, y] as const
  })

  const path = points
    .map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`)
    .join(' ')

  // Cor baseada em tendência da série inteira (último vs primeiro)
  const isUp = values[values.length - 1] > values[0]
  // is_inverse=true → "menor é melhor", inverter cores
  const colorClass = (inverse ? !isUp : isUp) ? 'stroke-emerald-500' : 'stroke-rose-500'

  // Último ponto destacado
  const last = points[points.length - 1]

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      preserveAspectRatio="none"
    >
      <path
        d={path}
        fill="none"
        strokeWidth={1.5}
        className={colorClass}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
      <circle cx={last[0]} cy={last[1]} r={2} className={`fill-current ${colorClass}`} />
    </svg>
  )
}
