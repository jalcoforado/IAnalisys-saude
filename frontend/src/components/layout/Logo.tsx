/**
 * Logo Ianalisys — placeholder SVG inline.
 *
 * Quando tivermos o SVG oficial da empresa, troca esse arquivo por completo.
 * Aceita prop `variant` para ajustar contraste em fundos claros/escuros/brand.
 */
interface LogoProps {
  variant?: 'light' | 'dark'
  showTagline?: boolean
  className?: string
}

export default function Logo({ variant = 'dark', showTagline = false, className = '' }: LogoProps) {
  const text = variant === 'light' ? '#FFFFFF' : '#0F172A'
  const accent = variant === 'light' ? '#60A5FA' : '#1D4ED8'
  const tagline = variant === 'light' ? '#BFDBFE' : '#64748B'

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Símbolo: A estilizado em cubo */}
      <svg width="32" height="32" viewBox="0 0 32 32" fill="none" className="shrink-0">
        <rect width="32" height="32" rx="8" fill={accent} />
        <path d="M16 6 L25 24 L21 24 L19 19 L13 19 L11 24 L7 24 Z M14.5 16 L17.5 16 L16 12.5 Z" fill="#FFFFFF" />
      </svg>
      <div className="leading-tight">
        <div className="font-bold tracking-tight text-base" style={{ color: text }}>
          IAnalisys <span className="font-light" style={{ color: accent }}>Saúde</span>
        </div>
        {showTagline && (
          <div className="text-[10px] uppercase tracking-wide" style={{ color: tagline }}>
            Inteligência analítica odontológica
          </div>
        )}
      </div>
    </div>
  )
}
