import { initials } from './_utils'

export function CardBase({
  children, span = 1, className = '',
}: { children: React.ReactNode; span?: 1 | 2 | 3; className?: string }) {
  const colClass = span === 3 ? 'lg:col-span-3' : span === 2 ? 'lg:col-span-2' : 'lg:col-span-1'
  return (
    <div className={`bg-white border border-neutral-200 rounded-xl shadow-md hover:shadow-lg transition-shadow overflow-hidden flex flex-col ${colClass} ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({
  icon, iconBg, title, subtitle, badge, badgeColor,
}: {
  icon: React.ReactNode
  iconBg: string
  title: string
  subtitle?: string
  badge?: string
  badgeColor?: string
}) {
  return (
    <div className="px-5 py-4 border-b border-neutral-100 flex items-center gap-3">
      <span className={`w-10 h-10 rounded-lg ${iconBg} flex items-center justify-center shrink-0 shadow-sm`}>
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="text-sm font-bold text-neutral-900 truncate">{title}</h3>
          {badge && (
            <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded font-bold ${badgeColor || 'bg-primary-50 text-primary-700'}`}>
              {badge}
            </span>
          )}
        </div>
        {subtitle && <div className="text-xs text-neutral-500 mt-0.5 truncate">{subtitle}</div>}
      </div>
    </div>
  )
}

export function EmptyState({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center py-10 px-4 text-center">
      <div className="w-12 h-12 rounded-full bg-neutral-100 text-neutral-400 flex items-center justify-center mb-3">
        {icon}
      </div>
      <div className="text-sm text-neutral-500">{label}</div>
    </div>
  )
}

export function Avatar({ name, color = 'bg-primary-50 text-primary-700' }: { name: string; color?: string }) {
  return (
    <span className={`w-9 h-9 rounded-full ${color} flex items-center justify-center text-xs font-bold shrink-0 ring-2 ring-white shadow-sm`}>
      {initials(name)}
    </span>
  )
}
