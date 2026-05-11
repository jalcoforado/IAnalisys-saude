import soniaDefault from '@/assets/sonia/sonia-default.png'
import soniaThinking from '@/assets/sonia/sonia-thinking.png'
import soniaAlert from '@/assets/sonia/sonia-alert.png'
import soniaHappy from '@/assets/sonia/sonia-happy.png'
import soniaCurious from '@/assets/sonia/sonia-curious.png'

export type SonIAMood = 'default' | 'thinking' | 'alert' | 'happy' | 'curious'
export type SonIASize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'

interface SonIAAvatarProps {
  mood?: SonIAMood
  size?: SonIASize
  /** Mostra um anel colorido sutil ao redor — dá destaque. */
  ring?: boolean
  /** Anima (pulse) — usar em estado loading com mood="thinking". */
  pulse?: boolean
  className?: string
  alt?: string
}

const moodMap: Record<SonIAMood, string> = {
  default: soniaDefault,
  thinking: soniaThinking,
  alert: soniaAlert,
  happy: soniaHappy,
  curious: soniaCurious,
}

const sizeMap: Record<SonIASize, string> = {
  xs: 'w-6 h-6',
  sm: 'w-8 h-8',
  md: 'w-10 h-10',
  lg: 'w-14 h-14',
  xl: 'w-20 h-20',
  '2xl': 'w-32 h-32',
}

const ringColorMap: Record<SonIAMood, string> = {
  default: 'ring-primary-200',
  thinking: 'ring-primary-300',
  alert: 'ring-rose-300',
  happy: 'ring-emerald-300',
  curious: 'ring-amber-300',
}

export default function SonIAAvatar({
  mood = 'default',
  size = 'md',
  ring = false,
  pulse = false,
  className = '',
  alt = 'SonIA',
}: SonIAAvatarProps) {
  const ringCls = ring ? `ring-2 ring-offset-2 ring-offset-white ${ringColorMap[mood]}` : ''
  const pulseCls = pulse ? 'animate-pulse' : ''
  return (
    <img
      src={moodMap[mood]}
      alt={alt}
      className={`rounded-full object-cover shrink-0 ${sizeMap[size]} ${ringCls} ${pulseCls} ${className}`}
      loading="lazy"
    />
  )
}
