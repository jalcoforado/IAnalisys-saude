import { Link } from 'react-router-dom'
import { Grid3x3, Maximize2, Settings as SettingsIcon, Sparkles } from 'lucide-react'

import Logo from './Logo'
import UserMenu from './UserMenu'
import { usePageTitleValue } from '@/contexts/PageTitleContext'
import { useSettings } from '@/contexts/SettingsContext'

/**
 * Top bar de identidade + utilitários do usuário.
 * Sempre branca, sempre sticky. Mostra o título da página atual no centro
 * para que sobreviva ao scroll.
 */
export default function BrandBar() {
  const page = usePageTitleValue()
  const { settings } = useSettings()
  const containerClass = settings.layoutMode === 'boxed' ? 'max-w-7xl mx-auto' : ''

  const handleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen()
    } else {
      document.documentElement.requestFullscreen()
    }
  }

  return (
    <header className="bg-white border-b border-neutral-200 sticky top-0 z-40">
      <div className={`${containerClass} px-6 h-14 flex items-center gap-4`}>
        {/* Esquerda: Logo */}
        <Link to="/" className="shrink-0">
          <Logo variant="dark" />
        </Link>

        {/* Centro: título da página */}
        <div className="flex-1 min-w-0 hidden md:block px-4 border-l border-neutral-200">
          {page.eyebrow && (
            <div className="text-[10px] uppercase tracking-wider text-primary-600 font-bold">{page.eyebrow}</div>
          )}
          <div className="flex items-baseline gap-2 truncate">
            <h1 className="text-base font-bold text-neutral-900 truncate">{page.title}</h1>
            {page.subtitle && (
              <span className="text-xs text-neutral-500 truncate hidden lg:inline">— {page.subtitle}</span>
            )}
          </div>
        </div>

        {/* Direita: ações utilitárias + IA + avatar */}
        <div className="flex items-center gap-1.5 shrink-0">
          <IconButton title="Aplicações" icon={<Grid3x3 size={16} />} disabled />
          <IconButton title="Configurações" icon={<SettingsIcon size={16} />} to="/configuracoes" />
          <IconButton title="Tela cheia" icon={<Maximize2 size={16} />} onClick={handleFullscreen} />

          <button
            disabled
            className="hidden md:flex items-center gap-2 px-3 h-9 rounded-lg bg-gradient-to-r from-neutral-900 to-neutral-800 text-white opacity-60 cursor-not-allowed ml-1"
            title="IA Assistente — em breve"
          >
            <Sparkles size={14} className="text-primary-300" />
            <div className="text-left leading-tight">
              <div className="text-[11px] font-bold">IAnalisys</div>
              <div className="text-[9px] uppercase tracking-wide text-primary-300">Assistente</div>
            </div>
          </button>

          <div className="ml-1 pl-2 border-l border-neutral-200">
            <UserMenu variant="light" />
          </div>
        </div>
      </div>
    </header>
  )
}

function IconButton({ icon, title, to, onClick, disabled }: {
  icon: React.ReactNode; title: string; to?: string; onClick?: () => void; disabled?: boolean
}) {
  const cls = `w-9 h-9 rounded-lg flex items-center justify-center transition ${
    disabled ? 'text-neutral-300 cursor-not-allowed' : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'
  }`
  if (to && !disabled) return <Link to={to} title={title} className={cls}>{icon}</Link>
  return <button title={title} onClick={onClick} disabled={disabled} className={cls}>{icon}</button>
}
