import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

import { MAIN_MENU, type MenuItem } from '@/config/menus'
import { useSettings, type TopbarColor } from '@/contexts/SettingsContext'

/**
 * Menu bar de navegação principal. Fica sticky logo abaixo da BrandBar.
 * A cor é configurável (claro/escuro/marca) via SettingsContext.
 */
const colorClasses: Record<TopbarColor, { bar: string; text: string; itemHover: string; activeBg: string; chevron: string }> = {
  light: {
    bar: 'bg-white border-b border-neutral-200',
    text: 'text-neutral-700',
    itemHover: 'hover:bg-neutral-100 hover:text-neutral-900',
    activeBg: 'border-primary-700 text-primary-700',
    chevron: 'text-neutral-400',
  },
  dark: {
    bar: 'bg-neutral-900 border-b border-neutral-800',
    text: 'text-neutral-200',
    itemHover: 'hover:bg-neutral-800 hover:text-white',
    activeBg: 'border-primary-400 text-white',
    chevron: 'text-neutral-500',
  },
  brand: {
    bar: 'bg-gradient-to-r from-primary-700 to-primary-900 border-b border-primary-900',
    text: 'text-white',
    itemHover: 'hover:bg-white/10 hover:text-white',
    activeBg: 'border-white text-white',
    chevron: 'text-white/70',
  },
}

export default function MenuBar() {
  const { settings } = useSettings()
  const c = colorClasses[settings.topbarColor]
  const containerClass = settings.layoutMode === 'boxed' ? 'max-w-7xl mx-auto' : ''

  return (
    <nav className={`${c.bar} sticky top-14 z-30 backdrop-blur-sm`}>
      <div className={`${containerClass} px-6 h-11 flex items-center gap-1`}>
        {MAIN_MENU.map((item) => (
          <NavbarItem key={item.label} item={item} colors={c} />
        ))}
      </div>
    </nav>
  )
}

function NavbarItem({ item, colors }: {
  item: MenuItem
  colors: typeof colorClasses[TopbarColor]
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const location = useLocation()
  const Icon = item.icon

  const isActive = item.path
    ? location.pathname === item.path
    : (item.children?.some((c) => c.path && location.pathname === c.path) ?? false)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const baseClass = `flex items-center gap-1.5 px-3 h-11 text-sm font-medium border-b-2 transition shrink-0 ${
    isActive ? colors.activeBg : 'border-transparent ' + colors.text + ' ' + colors.itemHover
  } ${item.comingSoon ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`

  if (!item.children) {
    if (item.comingSoon) {
      return (
        <span className={baseClass} title="Em breve">
          <Icon size={14} />
          {item.label}
          <ChevronRight size={12} className={colors.chevron} />
        </span>
      )
    }
    return (
      <Link to={item.path!} className={baseClass}>
        <Icon size={14} />
        {item.label}
        <ChevronRight size={12} className={colors.chevron} />
      </Link>
    )
  }

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => !item.comingSoon && setOpen((v) => !v)} className={baseClass}>
        <Icon size={14} />
        {item.label}
        <ChevronRight size={12} className={colors.chevron} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-0 w-60 bg-white border border-neutral-200 rounded-b-lg shadow-lg z-50 overflow-hidden">
          {item.children.map((sub) => (
            <DropdownItem key={sub.label} item={sub} onClose={() => setOpen(false)} />
          ))}
        </div>
      )}
    </div>
  )
}

function DropdownItem({ item, onClose }: { item: MenuItem; onClose: () => void }) {
  const Icon = item.icon
  const location = useLocation()
  const isActive = item.path && location.pathname === item.path

  if (item.comingSoon) {
    return (
      <div className="px-4 py-2.5 text-sm text-neutral-400 flex items-center gap-2.5 cursor-not-allowed">
        <Icon size={14} />
        <span className="flex-1">{item.label}</span>
        <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-warning-bg text-warning-text">soon</span>
      </div>
    )
  }
  return (
    <Link
      to={item.path!}
      onClick={onClose}
      className={`px-4 py-2.5 text-sm flex items-center gap-2.5 transition ${
        isActive ? 'bg-primary-50 text-primary-700' : 'text-neutral-700 hover:bg-neutral-50'
      }`}
    >
      <Icon size={14} />
      {item.label}
    </Link>
  )
}
