type Size = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl'

interface SonIABrandProps {
  size?: Size
  className?: string
}

const sizeMap: Record<Size, string> = {
  xs: 'text-xs',
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg',
  xl: 'text-xl',
  '2xl': 'text-2xl',
}

export default function SonIABrand({ size = 'md', className = '' }: SonIABrandProps) {
  return (
    <span className={`font-medium text-neutral-900 ${sizeMap[size]} ${className}`}>
      Sôn<span className="font-bold tracking-wider text-primary-700">IA</span>
    </span>
  )
}
