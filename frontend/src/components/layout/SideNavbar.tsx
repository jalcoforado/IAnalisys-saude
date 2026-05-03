import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { ChevronDown, ChevronRight, Settings as SettingsIcon } from 'lucide-react'

import UserMenu from './UserMenu'
import { MAIN_MENU, type MenuItem } from '@/config/menus'
import { useSettings, type TopbarColor } from '@/contexts/SettingsContext'

interface VariantClasses {
  bar: string
  border: string
  hover: string
  itemHoverText: string
  groupActiveText: string
  itemActiveBg: string
  childBorder: string
  userVariant: 'light' | 'dark' | 'brand'
}

const variants: Record<TopbarColor, VariantClasses> = {
  light: {
    bar: 'bg-white text-neutral-700',
    border: 'border-neutral-200',
    hover: 'hover:bg-neutral-100',
    itemHoverText: 'hover:text-neutral-900',
    groupActiveText: 'text-neutral-900',
    itemActiveBg: 'bg-primary-50 text-primary-700',
    childBorder: 'border-neutral-200/60',
    userVariant: 'light',
  },
  dark: {
    bar: 'bg-neutral-900 text-neutral-200',
    border: 'border-neutral-800',
    hover: 'hover:bg-neutral-800',
    itemHoverText: 'hover:text-white',
    groupActiveText: 'text-white',
    itemActiveBg: 'bg-primary-700 text-white',
    childBorder: 'border-neutral-700/50',
    userVariant: 'dark',
  },
  brand: {
    bar: 'bg-gradient-to-b from-primary-700 to-primary-900 text-white',
    border: 'border-primary-900/50',
    hover: 'hover:bg-white/10',
    itemHoverText: 'hover:text-white',
    groupActiveText: 'text-white',
    itemActiveBg: 'bg-white/15 text-white',
    childBorder: 'border-white/20',
    userVariant: 'brand',
  },
}

export default function SideNavbar() {
  const { settings } = useSettings()
  const v = variants[settings.topbarColor]

  return (
    <aside className={`fixed top-14 left-0 bottom-0 w-60 z-20 flex flex-col border-r ${v.bar} ${v.border}`}>
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {MAIN_MENU.map((item) => (
          <SideItem key={item.label} item={item} v={v} />
        ))}
      </nav>

      <div className={`border-t ${v.border} px-3 py-3 flex items-center justify-between`}>
        <UserMenu variant={v.userVariant} />
        <Link
          to="/configuracoes"
          className={`w-8 h-8 rounded-lg flex items-center justify-center ${v.hover} transition`}
          title="Configurações"
        >
          <SettingsIcon size={14} />
        </Link>
      </div>
    </aside>
  )
}

function SideItem({ item, v }: { item: MenuItem; v: VariantClasses }) {
  const location = useLocation()
  const Icon = item.icon
  const [expanded, setExpanded] = useState(true)

  const isActive = item.path && location.pathname === item.path
  const hasChildren = !!item.children?.length

  const baseClass = `w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition ${
    item.comingSoon ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
  }`

  if (!hasChildren) {
    if (item.comingSoon) {
      return (
        <span className={`${baseClass} opacity-60`}>
          <Icon size={16} />
          <span className="flex-1 text-left">{item.label}</span>
          <span className="text-[9px] uppercase px-1.5 py-0.5 rounded bg-warning-bg text-warning-text">soon</span>
        </span>
      )
    }
    return (
      <Link
        to={item.path!}
        className={`${baseClass} ${isActive ? v.itemActiveBg : `${v.hover} ${v.itemHoverText}`}`}
      >
        <Icon size={16} />
        <span className="flex-1 text-left">{item.label}</span>
      </Link>
    )
  }

  const anyChildActive = item.children?.some((c) => c.path && location.pathname === c.path)
  return (
    <div>
      <button
        onClick={() => !item.comingSoon && setExpanded((s) => !s)}
        className={`${baseClass} ${anyChildActive ? v.groupActiveText : `${v.hover} ${v.itemHoverText}`}`}
      >
        <Icon size={16} />
        <span className="flex-1 text-left">{item.label}</span>
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>
      {expanded && (
        <div className={`ml-3 mt-0.5 space-y-0.5 border-l ${v.childBorder} pl-2`}>
          {item.children!.map((sub) => (
            <SideItem key={sub.label} item={sub} v={v} />
          ))}
        </div>
      )}
    </div>
  )
}
