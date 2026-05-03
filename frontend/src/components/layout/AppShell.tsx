import type { ReactNode } from 'react'

import BrandBar from './BrandBar'
import MenuBar from './MenuBar'
import SideNavbar from './SideNavbar'
import { useSettings } from '@/contexts/SettingsContext'

interface AppShellProps {
  children: ReactNode
}

/**
 * Shell global das rotas privadas.
 *
 * Estrutura visual:
 *   ┌──────────────────────────────────────┐
 *   │ BrandBar (branca, sticky)            │  ← logo + título da página + ações + user
 *   ├──────────────────────────────────────┤
 *   │ MenuBar (configurável, sticky)       │  ← navegação principal — só no modo top
 *   ├──────────┬───────────────────────────┤
 *   │ SideNav  │ conteúdo da página        │  ← sidebar só no modo side (substitui MenuBar)
 *   └──────────┴───────────────────────────┘
 */
export default function AppShell({ children }: AppShellProps) {
  const { settings } = useSettings()
  const isSide = settings.navMode === 'side'

  return (
    <div className="min-h-screen bg-neutral-50">
      <BrandBar />
      {isSide ? (
        <div className="flex">
          <SideNavbar />
          <div className="flex-1 ml-60 min-h-[calc(100vh-3.5rem)]">{children}</div>
        </div>
      ) : (
        <>
          <MenuBar />
          {children}
        </>
      )}
    </div>
  )
}
