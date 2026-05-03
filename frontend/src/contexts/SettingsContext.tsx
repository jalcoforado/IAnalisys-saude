import { createContext, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

export type NavMode = 'top' | 'side'
export type TopbarColor = 'light' | 'dark' | 'brand'
export type LayoutMode = 'fluid' | 'boxed'

export interface AppSettings {
  navMode: NavMode
  topbarColor: TopbarColor
  layoutMode: LayoutMode
}

const DEFAULT_SETTINGS: AppSettings = {
  navMode: 'top',
  topbarColor: 'brand',
  layoutMode: 'boxed',
}

const STORAGE_KEY = 'ianalisys.settings'

function loadFromStorage(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return DEFAULT_SETTINGS
    const parsed = JSON.parse(raw) as Partial<AppSettings>
    return { ...DEFAULT_SETTINGS, ...parsed }
  } catch {
    return DEFAULT_SETTINGS
  }
}

interface SettingsContextValue {
  settings: AppSettings
  setNavMode: (m: NavMode) => void
  setTopbarColor: (c: TopbarColor) => void
  setLayoutMode: (l: LayoutMode) => void
  reset: () => void
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(() => loadFromStorage())

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  }, [settings])

  const value: SettingsContextValue = {
    settings,
    setNavMode: (navMode) => setSettings((s) => ({ ...s, navMode })),
    setTopbarColor: (topbarColor) => setSettings((s) => ({ ...s, topbarColor })),
    setLayoutMode: (layoutMode) => setSettings((s) => ({ ...s, layoutMode })),
    reset: () => setSettings(DEFAULT_SETTINGS),
  }

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings deve ser usado dentro de SettingsProvider')
  return ctx
}
