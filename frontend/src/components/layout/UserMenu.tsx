import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, LogOut, Settings, User as UserIcon } from 'lucide-react'

import { useAuth } from '@/modules/auth/AuthContext'

interface UserMenuProps {
  variant?: 'light' | 'dark' | 'brand'
}

export default function UserMenu({ variant = 'light' }: UserMenuProps) {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  if (!user) return null

  const initials = (user.full_name || user.email)
    .split(/[\s.@]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0]!.toUpperCase())
    .join('')

  const buttonHover = variant === 'light' ? 'hover:bg-neutral-100' : 'hover:bg-white/10'
  const labelColor = variant === 'light' ? 'text-neutral-700' : 'text-white'
  const subColor = variant === 'light' ? 'text-neutral-400' : 'text-white/60'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`flex items-center gap-2 px-2 py-1.5 rounded-lg transition ${buttonHover}`}
      >
        <span className="w-8 h-8 rounded-full bg-gradient-to-br from-primary-500 to-primary-700 text-white flex items-center justify-center font-bold text-xs shadow-sm">
          {initials}
        </span>
        <div className="hidden md:block text-left leading-tight">
          <div className={`text-xs font-semibold ${labelColor}`}>{user.full_name || user.email}</div>
          <div className={`text-[10px] uppercase tracking-wide ${subColor}`}>{user.role}</div>
        </div>
        <ChevronDown size={14} className={labelColor} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-60 bg-white border border-neutral-200 rounded-lg shadow-lg z-50 overflow-hidden">
          <div className="px-4 py-3 border-b bg-neutral-50">
            <div className="text-sm font-semibold text-neutral-900 truncate">{user.full_name}</div>
            <div className="text-xs text-neutral-500 truncate">{user.email}</div>
          </div>
          <nav className="py-1">
            <MenuLink to="/perfil" icon={<UserIcon size={14} />} label="Meu perfil" onClick={() => setOpen(false)} />
            <MenuLink to="/configuracoes" icon={<Settings size={14} />} label="Configurações" onClick={() => setOpen(false)} />
            <div className="border-t my-1" />
            <button
              onClick={() => { setOpen(false); logout() }}
              className="w-full px-4 py-2 text-sm text-left text-error-text hover:bg-error-bg flex items-center gap-2.5"
            >
              <LogOut size={14} />
              Sair
            </button>
          </nav>
        </div>
      )}
    </div>
  )
}

function MenuLink({ to, icon, label, onClick }: {
  to: string; icon: React.ReactNode; label: string; onClick: () => void
}) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className="block px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-50 flex items-center gap-2.5"
    >
      {icon}
      {label}
    </Link>
  )
}
